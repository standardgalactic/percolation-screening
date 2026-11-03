"""Static possible-call graph for pinned Python distributions, and witness analysis.

Usage: python3 -I pycallgraph.py OUT.json APP_DIST DEP_DIST[,DEP_DIST...] SRC_ROOT

SRC_ROOT holds one extracted-wheel directory per distribution, named
<dist>-<version>. Source files are parsed with ast and never executed.

Edges are possible calls between functions. Imports are used only to resolve
names and are not propagation edges. Calls that cannot be resolved are counted
and listed. Two graphs are built: 'strict' (resolved calls only) and
'matched' (strict plus calls on receivers of unknown type linked to every
analyzed method of that name, when there are at most MATCH_LIMIT such methods).
Module-level code is kept as a separate import-time vertex that nothing calls.
"""
import ast
import builtins
import json
import os
import sys
from collections import defaultdict, deque

MATCH_LIMIT = 10
SINKS = {
    "subprocess": {"Popen", "run", "call", "check_call", "check_output",
                   "getoutput", "getstatusoutput"},
    "os": {"system", "popen", "execv", "execve", "execvp", "execvpe", "execl",
           "execle", "execlp", "execlpe", "spawnv", "spawnve", "spawnvp",
           "spawnvpe", "spawnl", "spawnle", "spawnlp", "spawnlpe",
           "posix_spawn", "posix_spawnp", "startfile"},
    "pty": {"spawn"},
    "asyncio": {"create_subprocess_exec", "create_subprocess_shell"},
}
BUILTIN_NAMES = set(dir(builtins))
COMMON_ATTRS = set()
for _t in (str, list, dict, set, frozenset, tuple, bytes, bytearray, int, float, object, type):
    COMMON_ATTRS.update(dir(_t))
COMMON_ATTRS.update({"read", "write", "close", "flush", "seek", "tell", "readline", "readlines",
                     "open", "debug", "info", "warning", "error", "exception", "log", "critical",
                     "match", "search", "sub", "group", "groups", "findall", "finditer", "compile",
                     "put", "acquire", "release", "wait", "start", "run", "send", "recv", "connect"})


def is_sink(q):
    mod, _, name = q.rpartition(".")
    return mod in SINKS and name in SINKS[mod]


class Module:
    def __init__(self, name, dist, path, is_pkg):
        self.name, self.dist, self.path, self.is_pkg = name, dist, path, is_pkg
        self.tree = None
        self.defs = {}
        self.imports = {}
        self.stars = []


class Func:
    def __init__(self, qn, module, qual, node, class_qn, parent):
        self.qn, self.module, self.qual, self.node = qn, module, qual, node
        self.class_qn, self.parent = class_qn, parent
        self.local_defs, self.local_imports = {}, {}
        self.first_param = None


class Cls:
    def __init__(self, qn, module, node):
        self.qn, self.module, self.node = qn, module, node
        self.methods = {}
        self._bases = None


modules, funcs, classes = {}, {}, {}
parse_failures = []


def discover(src_root, dist_dir):
    dist = dist_dir.split("-")[0].lower()
    base = os.path.join(src_root, dist_dir)
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.endswith((".dist-info", ".data")) and d != "__pycache__"]
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            parts = os.path.relpath(path, base)[:-3].split(os.sep)
            is_pkg = parts[-1] == "__init__"
            if is_pkg:
                parts = parts[:-1]
            if parts:
                name = ".".join(parts)
                modules[name] = Module(name, dist, path, is_pkg)


def collect_imports(body, table, module, stars):
    for st in body:
        if isinstance(st, ast.Import):
            for a in st.names:
                if a.asname:
                    table[a.asname] = ("modref", a.name)
                else:
                    table[a.name.split(".")[0]] = ("modref", a.name.split(".")[0])
        elif isinstance(st, ast.ImportFrom):
            if st.level:
                pkg = module.name if module.is_pkg else module.name.rpartition(".")[0]
                parts = pkg.split(".") if pkg else []
                parts = parts[: len(parts) - (st.level - 1)] if st.level > 1 else parts
                target = ".".join(parts + ([st.module] if st.module else []))
            else:
                target = st.module or ""
            for a in st.names:
                if a.name == "*":
                    stars.append(target)
                    continue
                nm = a.asname or a.name
                if f"{target}.{a.name}" in modules:
                    table[nm] = ("modref", f"{target}.{a.name}")
                else:
                    table[nm] = ("symref", target, a.name)
        elif isinstance(st, (ast.If, ast.Try, ast.With, ast.For, ast.While, ast.AsyncWith, ast.AsyncFor)):
            for fld in ("body", "orelse", "finalbody"):
                collect_imports(getattr(st, fld, []) or [], table, module, stars)
            for h in getattr(st, "handlers", []) or []:
                collect_imports(h.body, table, module, stars)


def collect_defs(body, module, prefix, class_qn, parent):
    for st in body:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qual = prefix + st.name
            qn = f"{module.dist}:{module.name}.{qual}"
            fn = Func(qn, module, qual, st, class_qn, parent)
            funcs[qn] = fn
            if class_qn:
                classes[class_qn].methods[st.name] = qn
                decos = [getattr(d, "id", None) for d in st.decorator_list]
                params = st.args.posonlyargs + st.args.args
                if params and "staticmethod" not in decos:
                    fn.first_param = params[0].arg
            elif parent is None:
                module.defs[st.name] = ("func", qn)
            else:
                parent.local_defs[st.name] = ("func", qn)
            collect_imports(st.body, fn.local_imports, module, [])
            collect_defs(st.body, module, qual + ".<locals>.", None, fn)
        elif isinstance(st, ast.ClassDef):
            cq = prefix + st.name
            cqn = f"{module.dist}:{module.name}.{cq}"
            classes[cqn] = Cls(cqn, module, st)
            if parent is None and class_qn is None:
                module.defs[st.name] = ("class", cqn)
            elif parent is not None:
                parent.local_defs[st.name] = ("class", cqn)
            collect_defs(st.body, module, cq + ".", cqn, None)
        elif isinstance(st, (ast.If, ast.Try, ast.With, ast.For, ast.While, ast.AsyncWith, ast.AsyncFor)):
            for fld in ("body", "orelse", "finalbody"):
                collect_defs(getattr(st, fld, []) or [], module, prefix, class_qn, parent)
            for h in getattr(st, "handlers", []) or []:
                collect_defs(h.body, module, prefix, class_qn, parent)


def import_entity(entry, depth=0):
    if entry[0] == "modref":
        return ("module", entry[1]) if entry[1] in modules else ("ext", entry[1])
    _, m, s = entry
    if m in modules:
        return lookup_symbol(m, s, depth + 1)
    return ("ext", f"{m}.{s}")


def lookup_symbol(m, s, depth=0):
    if depth > 8:
        return None
    mod = modules[m]
    if s in mod.defs:
        return mod.defs[s]
    if s in mod.imports:
        return import_entity(mod.imports[s], depth)
    for st in mod.stars:
        if st in modules:
            r = lookup_symbol(st, s, depth + 1)
            if r:
                return r
    if f"{m}.{s}" in modules:
        return ("module", f"{m}.{s}")
    return None


def scope_lookup(name, fn, module):
    f = fn
    while f is not None:
        if name in f.local_defs:
            return f.local_defs[name]
        if name in f.local_imports:
            return import_entity(f.local_imports[name])
        f = f.parent
    if name in module.defs:
        return module.defs[name]
    if name in module.imports:
        return import_entity(module.imports[name])
    for st in module.stars:
        if st in modules:
            r = lookup_symbol(st, name, 1)
            if r:
                return r
    return None


def walk_chain(ent, parts):
    cur = ent
    for p in parts:
        if cur[0] == "module":
            nxt = f"{cur[1]}.{p}"
            if nxt in modules:
                cur = ("module", nxt)
                continue
            r = lookup_symbol(cur[1], p)
            if r is None:
                return None
            cur = r
        elif cur[0] == "class":
            m = find_method(cur[1], p)
            if not m:
                return None
            cur = ("func", m)
        elif cur[0] == "ext":
            cur = ("ext", f"{cur[1]}.{p}")
        else:
            return None
    return cur


def class_bases(cqn):
    c = classes[cqn]
    if c._bases is None:
        c._bases = []
        for b in c.node.bases:
            parts = flatten(b)
            if not parts:
                continue
            ent = scope_lookup(parts[0], None, c.module)
            if ent is None:
                continue
            r = walk_chain(ent, parts[1:])
            if r and r[0] == "class":
                c._bases.append(r[1])
    return c._bases


def find_method(cqn, name, seen=None):
    seen = seen or set()
    if cqn in seen:
        return None
    seen.add(cqn)
    c = classes[cqn]
    if name in c.methods:
        return c.methods[name]
    for b in class_bases(cqn):
        r = find_method(b, name, seen)
        if r:
            return r
    return None


def flatten(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return parts[::-1]
    return None


def resolve_call(call, fn, module):
    f = call.func
    cls_qn = fn.class_qn if fn else None
    if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Call)
            and isinstance(f.value.func, ast.Name) and f.value.func.id == "super" and cls_qn):
        for b in class_bases(cls_qn):
            m = find_method(b, f.attr)
            if m:
                return ("func", m)
        return ("unres", "super", f.attr)
    parts = flatten(f)
    attr = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
    if not parts:
        return ("unres", "recv", attr)
    head = parts[0]
    if fn and cls_qn and fn.first_param == head and len(parts) > 1:
        if len(parts) == 2:
            m = find_method(cls_qn, parts[1])
            return ("func", m) if m else ("unres", "method", parts[1])
        return ("unres", "recv", parts[-1])
    ent = scope_lookup(head, fn, module)
    if ent is None:
        if len(parts) == 1 and head in BUILTIN_NAMES:
            return ("ext", "builtins." + head)
        return ("unres", "name" if len(parts) == 1 else "recv", parts[-1])
    r = walk_chain(ent, parts[1:])
    if r is None:
        return ("unres", "attr", parts[-1])
    return r


def calls_in(stmts, include_defs_header):
    """Call nodes executed when stmts run; nested defs contribute only headers."""
    stack = list(stmts)
    out = []
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.extend(n.decorator_list)
            stack.extend(n.args.defaults)
            stack.extend(d for d in n.args.kw_defaults if d is not None)
            continue
        if isinstance(n, ast.Call):
            out.append(n)
        stack.extend(ast.iter_child_nodes(n))
    return out


def build(app_dists, dep_dists, src_root):
    for d in sorted(os.listdir(src_root)):
        discover(src_root, d)
    for m in modules.values():
        try:
            with open(m.path, "rb") as fh:
                m.tree = ast.parse(fh.read())
        except (SyntaxError, ValueError):
            parse_failures.append(m.name)
    for m in list(modules.values()):
        if m.tree is None:
            continue
        collect_imports(m.tree.body, m.imports, m, m.stars)
        collect_defs(m.tree.body, m, "", None, None)
    method_index = defaultdict(list)
    for c in classes.values():
        for n, q in c.methods.items():
            method_index[n].append(q)

    edges = {"strict": set(), "matched": set(), "matched_filtered": set()}
    stats = defaultdict(lambda: defaultdict(int))
    unres_names = defaultdict(int)
    import_time_sinks = []
    contexts = [(fn, fn.module, fn.node.body, fn.qn) for fn in funcs.values()]
    for m in modules.values():
        if m.tree is not None:
            contexts.append((None, m, m.tree.body, f"{m.dist}:{m.name}.<module>"))
    vertices = {}
    for fn, m, body, qn in contexts:
        vertices[qn] = m.dist
        for call in calls_in(body, True):
            r = resolve_call(call, fn, m)
            st = stats[m.dist]
            if r[0] in ("func", "class"):
                tgt = r[1] if r[0] == "func" else find_method(r[1], "__init__")
                if tgt is None:
                    st["class_without_init"] += 1
                    continue
                kind = "internal" if funcs[tgt].module.dist == m.dist else "cross_package"
                st[kind] += 1
                for g in edges:
                    edges[g].add((qn, tgt))
            elif r[0] == "ext":
                if is_sink(r[1]):
                    sk = "sink:" + r[1]
                    vertices[sk] = "stdlib"
                    st["to_sink"] += 1
                    for g in edges:
                        edges[g].add((qn, sk))
                    if fn is None:
                        import_time_sinks.append((qn, r[1]))
                elif r[1].startswith("builtins."):
                    st["builtin"] += 1
                else:
                    st["external_other"] += 1
            elif r[0] == "unres":
                st["unresolved_" + r[1]] += 1
                unres_names[r[2]] += 1
                cands = method_index.get(r[2], []) if r[1] in ("recv", "attr", "method", "super") else []
                if cands and len(cands) <= MATCH_LIMIT:
                    for t in cands:
                        edges["matched"].add((qn, t))
                    st["matched_links"] += len(cands)
                if r[2] not in COMMON_ATTRS and r[1] in ("recv", "attr", "method", "super"):
                    local = [t for t in method_index.get(r[2], []) if funcs[t].module.dist == m.dist]
                    if local and len(local) <= MATCH_LIMIT:
                        for t in local:
                            edges["matched_filtered"].add((qn, t))
                        st["filtered_links"] += len(local)
            else:
                st["other"] += 1
    return edges, vertices, stats, unres_names, import_time_sinks


def adjacency(edges):
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
    return adj


def reach(adj, src, banned=None):
    seen = {src}
    dq = deque([src])
    while dq:
        a = dq.popleft()
        for b in adj.get(a, ()):
            if b != banned and b not in seen:
                seen.add(b)
                dq.append(b)
    return seen


def shortest_path(adj, src):
    prev = {src: None}
    dq = deque([src])
    while dq:
        a = dq.popleft()
        if a.startswith("sink:"):
            path = []
            while a is not None:
                path.append(a)
                a = prev[a]
            return path[::-1]
        for b in sorted(adj.get(a, ())):
            if b not in prev:
                prev[b] = a
                dq.append(b)
    return None


def max_flow(adj, radj, src, vertex_disjoint, limit=10):
    fwd = reach(adj, src)
    sinks = [v for v in fwd if v.startswith("sink:")]
    if not sinks:
        return 0
    bwd = set()
    dq = deque(sinks)
    bwd.update(sinks)
    while dq:
        a = dq.popleft()
        for b in radj.get(a, ()):
            if b not in bwd:
                bwd.add(b)
                dq.append(b)
    rel = fwd & bwd
    idx = {v: i for i, v in enumerate(sorted(rel))}
    n = len(idx)
    T = 2 * n  # super sink
    to, cap, head = [], [], [[] for _ in range(2 * n + 1)]

    def add(u, v, c):
        head[u].append(len(to)); to.append(v); cap.append(c)
        head[v].append(len(to)); to.append(u); cap.append(0)

    INF = 10 ** 6
    s_i = idx[src]
    for v, i in idx.items():
        if vertex_disjoint:
            c = 1 if (v != src and not v.startswith("sink:")) else INF
            add(i, i + n, c)
        for w in adj.get(v, ()):
            if w in idx:
                add(i + n if vertex_disjoint else i, idx[w], 1)
        if v.startswith("sink:"):
            add(i + n if vertex_disjoint else i, T, INF)
    source = s_i + n if vertex_disjoint else s_i
    flow = 0
    while flow < limit:
        prev = {source: -1}
        dq = deque([source])
        while dq and T not in prev:
            a = dq.popleft()
            for e in head[a]:
                if cap[e] > 0 and to[e] not in prev:
                    prev[to[e]] = e
                    dq.append(to[e])
        if T not in prev:
            break
        v = T
        while v != source:
            e = prev[v]
            cap[e] -= 1
            cap[e ^ 1] += 1
            v = to[e ^ 1]
        flow += 1
    return flow


def essential(adj, radj, src):
    fwd = reach(adj, src)
    sinks = [v for v in fwd if v.startswith("sink:")]
    if not sinks:
        return None
    bwd = set(sinks)
    dq = deque(sinks)
    while dq:
        a = dq.popleft()
        for b in radj.get(a, ()):
            if b not in bwd:
                bwd.add(b)
                dq.append(b)
    out = []
    for v in sorted((fwd & bwd) - {src} - set(sinks)):
        r = reach(adj, src, banned=v)
        if not any(x.startswith("sink:") for x in r):
            out.append(v)
    return out


def public_entry(fn):
    comps = fn.module.name.split(".") + fn.qual.split(".")
    if "<locals>" in comps:
        return False
    for c in comps:
        if c.startswith("_") and c != "__init__":
            return False
    return True


def main(out, app, deps, src_root):
    app_dists = [app.lower()]
    dep_dists = [d.lower() for d in deps.split(",")]
    edges, vertices, stats, unres_names, import_sinks = build(app_dists, dep_dists, src_root)
    result = {"parse_failures": parse_failures, "modules": len(modules),
              "functions": len(funcs), "classes": len(classes),
              "import_time_sink_calls": import_sinks, "per_dist_calls": {k: dict(v) for k, v in stats.items()},
              "top_unresolved_names": sorted(unres_names.items(), key=lambda x: -x[1])[:20], "graphs": {}}
    entries = [fn for fn in funcs.values() if fn.module.dist in dep_dists and public_entry(fn)]
    result["entries"] = len(entries)
    for gname, E in edges.items():
        adj, radj = adjacency(E), adjacency({(b, a) for a, b in E})
        shadow = [(a, b) for a, b in E if vertices[a] != vertices[b]]
        und = {(min(a, b), max(a, b)) for a, b in shadow}
        deg = defaultdict(int)
        for a, b in und:
            deg[a] += 1
            deg[b] += 1
        kin, kout = defaultdict(int), defaultdict(int)
        for a, b in shadow:
            kout[a] += 1
            kin[b] += 1
        verts = set(deg)
        s1 = sum(deg.values())
        K = sum(d * d for d in deg.values()) / s1 if s1 else 0
        Kd = sum(kin[v] * kout[v] for v in verts) / sum(kout.values()) if shadow else 0
        rows = []
        for fn in entries:
            if not any(x.startswith("sink:") for x in reach(adj, fn.qn)):
                continue
            path = shortest_path(adj, fn.qn)
            rows.append({"entry": fn.qn, "dist": fn.module.dist, "path": path,
                         "edge_disjoint": max_flow(adj, radj, fn.qn, False),
                         "vertex_disjoint": max_flow(adj, radj, fn.qn, True),
                         "essential": essential(adj, radj, fn.qn)})
        result["graphs"][gname] = {
            "vertices": len(vertices), "edges": len(E), "shadow_edges": len(shadow),
            "shadow_vertices": len(verts), "mean_degree": s1 / len(verts) if verts else 0, "K": K, "K_dir": Kd,
            "entries_with_witness": len(rows), "rows": rows}
    with open(out, "w") as fh:
        json.dump(result, fh, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:5])
