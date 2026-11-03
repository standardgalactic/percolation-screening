"""Minimum-cut (edge-disjoint path count) versus distance as witness statistics.

Entry set X (3 vertices of one package) and sensitive set S (3 vertices of
another package). Observed graphs: unplanted, one planted three-edge path
(narrow), and three planted vertex-disjoint paths (wide). Null: pivot
construction on the constrained swap chain, variant A.
"""
import random
import statistics
import sys
from collections import deque

from shadowlib import Sampler, generate, mc_pvalue, shadow


def multi_dist(n, adj, X, S):
    Sset = set(S)
    dist = {x: 0 for x in X}
    dq = deque(X)
    while dq:
        a = dq.popleft()
        if a in Sset:
            return dist[a]
        for b in adj[a]:
            if b not in dist:
                dist[b] = dist[a] + 1
                dq.append(b)
    return n + 1


def max_edge_disjoint(n, edges, X, S, limit=10):
    """Unit-capacity max flow from set X to set S by BFS augmentation."""
    src, snk = n, n + 1
    to, cap, head = [], [], [[] for _ in range(n + 2)]

    def add(u, v, c):
        head[u].append(len(to))
        to.append(v)
        cap.append(c)
        head[v].append(len(to))
        to.append(u)
        cap.append(0)

    for u, v in edges:
        add(u, v, 1)
    for x in X:
        add(src, x, limit)
    for s in S:
        add(s, snk, limit)
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


def stats(n, edges, X, S):
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
    return multi_dist(n, adj, X, S), max_edge_disjoint(n, edges, X, S)


def null_edge_lists(pkg, edges, B, L, rng):
    y = Sampler(pkg, edges, "A", random.Random(rng.randrange(10 ** 9)))
    y.run(L)
    out = []
    for _ in range(B):
        s = Sampler(pkg, y.edges, "A", random.Random(rng.randrange(10 ** 9)))
        s.run(L)
        out.append(s.edges)
    return out


def pick_sets(pkg, n_pkg, rng):
    members = {}
    for v, p in enumerate(pkg):
        members.setdefault(p, []).append(v)
    ok = [p for p, m in members.items() if len(m) >= 3]
    pa, pb = rng.sample(ok, 2)
    return rng.sample(members[pa], 3), rng.sample(members[pb], 3)


def plant(pkg, n, X, S, k, rng):
    used = set(X) | set(S)
    new = []
    for i in range(k):
        while True:
            a, b = rng.randrange(n), rng.randrange(n)
            if (a not in used and b not in used and a != b and pkg[X[i]] != pkg[a]
                    and pkg[a] != pkg[b] and pkg[b] != pkg[S[i]]):
                break
        used |= {a, b}
        new += [(X[i], a), (a, b), (b, S[i])]
    return new


def main(graphs, B, seed, n, n_pkg, n_pairs, mean_out):
    rng = random.Random(seed)
    tot = {"unplanted": [0, 0, 0], "narrow": [0, 0, 0], "wide": [0, 0, 0]}
    lam_obs = {"unplanted": [], "narrow": [], "wide": []}
    lam_null = {"unplanted": [], "narrow": [], "wide": []}
    for g in range(graphs):
        pkg, full = generate(n, n_pkg, mean_out, 0.4, 2.5, rng)
        sh = shadow(pkg, full)
        L = 5 * len(sh)
        # unplanted pairs share one null sample set
        samples = null_edge_lists(pkg, sh, B, L, rng)
        for _ in range(n_pairs):
            X, S = pick_sets(pkg, n_pkg, rng)
            d0, l0 = stats(n, sh, X, S)
            res = [stats(n, e, X, S) for e in samples]
            pd_ = mc_pvalue(d0, [r[0] for r in res], "lower")
            pl = mc_pvalue(l0, [r[1] for r in res], "upper")
            t = tot["unplanted"]
            t[0] += 1
            t[1] += pd_ <= 0.05
            t[2] += pl <= 0.05
            lam_obs["unplanted"].append(l0)
            lam_null["unplanted"].append(statistics.median(r[1] for r in res))
        for kind, k in (("narrow", 1), ("wide", 3)):
            X, S = pick_sets(pkg, n_pkg, rng)
            obs = sh + plant(pkg, n, X, S, k, rng)
            samples = null_edge_lists(pkg, obs, B, 5 * len(obs), rng)
            d0, l0 = stats(n, obs, X, S)
            res = [stats(n, e, X, S) for e in samples]
            pd_ = mc_pvalue(d0, [r[0] for r in res], "lower")
            pl = mc_pvalue(l0, [r[1] for r in res], "upper")
            t = tot[kind]
            t[0] += 1
            t[1] += pd_ <= 0.05
            t[2] += pl <= 0.05
            lam_obs[kind].append(l0)
            lam_null[kind].append(statistics.median(r[1] for r in res))
        print("graph", g, "done", flush=True)
    for kind in ("narrow", "wide"):
        print(kind, "observed min-cut counts", {v: lam_obs[kind].count(v) for v in sorted(set(lam_obs[kind]))})
    print("case  trials  distance_reject  mincut_reject  mean_obs_mincut  mean_null_median_mincut")
    for kind in ("unplanted", "narrow", "wide"):
        t = tot[kind]
        print("%-9s %5d %10.3f %14.3f %14.2f %16.2f" % (
            kind, t[0], t[1] / t[0], t[2] / t[0],
            statistics.mean(lam_obs[kind]), statistics.mean(lam_null[kind])))


if __name__ == "__main__":
    main(*[int(a) for a in sys.argv[1:7]], float(sys.argv[7]))
