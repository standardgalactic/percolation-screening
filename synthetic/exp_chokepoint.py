"""Vertex-disjoint path count and essential vertices versus edge-disjoint count.

Plants: narrow (one path), wide (three vertex-disjoint paths), funnel (three
routes that all pass through one hub vertex). Edge-disjoint count sees the
funnel as three routes; the vertex-disjoint count and the essential-vertex
list see the hub.
"""
import random
import statistics
import sys
from collections import deque

from exp_mincut import (max_edge_disjoint, multi_dist, null_edge_lists,
                        pick_sets)
from shadowlib import generate, mc_pvalue, shadow


def max_vertex_disjoint(n, edges, X, S, limit=10):
    """Vertex-disjoint paths from X to S (every vertex capacity one)."""
    src, snk = 2 * n, 2 * n + 1
    to, cap, head = [], [], [[] for _ in range(2 * n + 2)]

    def add(u, v, c):
        head[u].append(len(to))
        to.append(v)
        cap.append(c)
        head[v].append(len(to))
        to.append(u)
        cap.append(0)

    for v in range(n):
        add(v, v + n, 1)
    for u, v in edges:
        add(u + n, v, 1)
    for x in X:
        add(src, x, 1)
    for s in S:
        add(s + n, snk, 1)
    flow = 0
    while flow < limit:
        prev = {src: -1}
        dq = deque([src])
        while dq and snk not in prev:
            a = dq.popleft()
            for e in head[a]:
                if cap[e] > 0 and to[e] not in prev:
                    prev[to[e]] = e
                    dq.append(to[e])
        if snk not in prev:
            break
        v = snk
        while v != src:
            e = prev[v]
            cap[e] -= 1
            cap[e ^ 1] += 1
            v = to[e ^ 1]
        flow += 1
    return flow


def reach_set(adj, starts, banned=None):
    seen = set(x for x in starts if x != banned)
    dq = deque(seen)
    while dq:
        a = dq.popleft()
        for b in adj[a]:
            if b != banned and b not in seen:
                seen.add(b)
                dq.append(b)
    return seen


def essential_vertices(n, edges, X, S):
    """Vertices outside X and S that every X to S path must pass through."""
    adj = [[] for _ in range(n)]
    radj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        radj[v].append(u)
    fwd = reach_set(adj, X)
    if not any(s in fwd for s in S):
        return None
    bwd = reach_set(radj, S)
    cand = [v for v in fwd & bwd if v not in set(X) and v not in set(S)]
    out = []
    for v in cand:
        r = reach_set(adj, X, banned=v)
        if not any(s in r for s in S):
            out.append(v)
    return out


def all_stats(n, edges, X, S):
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
    return (multi_dist(n, adj, X, S), max_edge_disjoint(n, edges, X, S),
            max_vertex_disjoint(n, edges, X, S))


def plant(pkg, n, X, S, kind, rng):
    used = set(X) | set(S)

    def fresh(avoid_pkg=()):
        while True:
            v = rng.randrange(n)
            if v not in used and pkg[v] not in avoid_pkg:
                used.add(v)
                return v

    new = []
    if kind in ("narrow", "wide"):
        for i in range(1 if kind == "narrow" else 3):
            while True:
                a, b = fresh(), fresh()
                if (pkg[X[i]] != pkg[a] and pkg[a] != pkg[b] and pkg[b] != pkg[S[i]]):
                    break
            new += [(X[i], a), (a, b), (b, S[i])]
        return new, None
    h = fresh()
    for i in range(3):
        while True:
            a, b = fresh(), fresh()
            if (pkg[X[i]] != pkg[a] and pkg[a] != pkg[h] and pkg[h] != pkg[b]
                    and pkg[b] != pkg[S[i]]):
                break
        new += [(X[i], a), (a, h), (h, b), (b, S[i])]
    return new, h


def main(graphs, B, seed, n, n_pkg, n_pairs, mean_out):
    rng = random.Random(seed)
    names = ("distance", "edge-disjoint", "vertex-disjoint")
    tails = ("lower", "upper", "upper")
    rej = {k: [0, 0, 0, 0] for k in ("unplanted", "narrow", "wide", "funnel")}
    obs_vals = {k: [] for k in rej}
    hub_found = 0
    for g in range(graphs):
        pkg, full = generate(n, n_pkg, mean_out, 0.4, 2.5, rng)
        sh = shadow(pkg, full)
        samples = null_edge_lists(pkg, sh, B, 5 * len(sh), rng)
        for _ in range(n_pairs):
            X, S = pick_sets(pkg, n_pkg, rng)
            o = all_stats(n, sh, X, S)
            res = [all_stats(n, e, X, S) for e in samples]
            r = rej["unplanted"]
            r[0] += 1
            for j in range(3):
                r[1 + j] += mc_pvalue(o[j], [x[j] for x in res], tails[j]) <= 0.05
            obs_vals["unplanted"].append(o)
        for kind in ("narrow", "wide", "funnel"):
            X, S = pick_sets(pkg, n_pkg, rng)
            new, h = plant(pkg, n, X, S, kind, rng)
            obs = sh + new
            samples_p = null_edge_lists(pkg, obs, B, 5 * len(obs), rng)
            o = all_stats(n, obs, X, S)
            res = [all_stats(n, e, X, S) for e in samples_p]
            r = rej[kind]
            r[0] += 1
            for j in range(3):
                r[1 + j] += mc_pvalue(o[j], [x[j] for x in res], tails[j]) <= 0.05
            obs_vals[kind].append(o)
            if kind == "funnel":
                ev = essential_vertices(n, obs, X, S)
                hub_found += ev is not None and h in ev
        print("graph", g, "done", flush=True)
    print("case        trials  " + "  ".join("%15s" % x for x in names))
    for kind, r in rej.items():
        print("%-10s %6d  " % (kind, r[0]) + "  ".join("%15.3f" % (r[1 + j] / r[0]) for j in range(3)))
    for kind in ("narrow", "wide", "funnel"):
        e = [v[1] for v in obs_vals[kind]]
        w = [v[2] for v in obs_vals[kind]]
        print(kind, "observed edge-disjoint", sorted(set(e)), "vertex-disjoint", sorted(set(w)),
              "means %.2f %.2f" % (statistics.mean(e), statistics.mean(w)))
    print("funnel: hub listed among essential vertices in", hub_found, "of", rej["funnel"][0])


if __name__ == "__main__":
    main(*[int(a) for a in sys.argv[1:7]], float(sys.argv[7]))
