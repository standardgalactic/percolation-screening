"""Detection of a planted three-edge cross-package path against the swap null.

For each synthetic graph: (1) unplanted pairs give the false-positive rate,
(2) one planted path v0 -> x1 -> x2 -> s through four distinct packages gives
power. Null samples use the pivot construction. Statistics: shortest-path
distance v0 to s in the shadow graph (lower tail) and forward reach of v0
(upper tail).
"""
import random
import statistics
import sys

from shadowlib import (Sampler, adjacency, bfs_dist, degree_stats, generate,
                       mc_pvalue, shadow)


def dist_and_reach(n, adj, v0, s):
    d = bfs_dist(adj, v0)
    return d.get(s, n + 1), len(d)


def null_samples(pkg, edges, mode, B, L, rng):
    y = Sampler(pkg, edges, mode, random.Random(rng.randrange(10 ** 9)))
    y.run(L)
    out = []
    for _ in range(B):
        s = Sampler(pkg, y.edges, mode, random.Random(rng.randrange(10 ** 9)))
        s.run(L)
        out.append(s.edges)
    return out


def main(graphs, B, seed, mode, n, n_pkg):
    rng = random.Random(seed)
    fp = {"dist": 0, "reach": 0}
    n_fp = 0
    pw = {"dist": 0, "reach": 0}
    n_pw = 0
    rows = []
    kdir_checked = False
    for g in range(graphs):
        pkg, full = generate(n, n_pkg, 3.0, 0.4, 2.5, rng)
        sh = shadow(pkg, full)
        m = len(sh)
        L = 5 * m
        # unplanted pairs
        pairs = []
        while len(pairs) < 25:
            v0, s = rng.randrange(n), rng.randrange(n)
            if pkg[v0] != pkg[s]:
                pairs.append((v0, s))
        samples = null_samples(pkg, sh, mode, B, L, rng)
        adjs = [adjacency(n, e) for e in samples]
        adj_obs = adjacency(n, sh)
        if not kdir_checked:
            c, k_und, k_dir = degree_stats(n, sh)
            ks = [degree_stats(n, e) for e in samples[:5]]
            print("observed mean degree %.3f K %.3f Kdir %.3f" % (c, k_und, k_dir))
            print("null  K_dir values:", [round(x[2], 6) for x in ks],
                  " K values:", [round(x[1], 3) for x in ks])
            kdir_checked = True
        for v0, s in pairs:
            do, ro = dist_and_reach(n, adj_obs, v0, s)
            ds, rs = zip(*[dist_and_reach(n, a, v0, s) for a in adjs])
            fp["dist"] += mc_pvalue(do, ds, "lower") <= 0.05
            fp["reach"] += mc_pvalue(ro, rs, "upper") <= 0.05
            n_fp += 1
        # planted
        while True:
            v0, x1, x2, s = [rng.randrange(n) for _ in range(4)]
            if len({pkg[v0], pkg[x1], pkg[x2], pkg[s]}) == 4:
                break
        planted = sh + [e for e in [(v0, x1), (x1, x2), (x2, s)] if e not in set(sh)]
        samples = null_samples(pkg, planted, mode, B, 5 * len(planted), rng)
        adj_obs = adjacency(n, planted)
        do, ro = dist_and_reach(n, adj_obs, v0, s)
        stats = [dist_and_reach(n, adjacency(n, e), v0, s) for e in samples]
        ds, rs = zip(*stats)
        pd_, pr_ = mc_pvalue(do, ds, "lower"), mc_pvalue(ro, rs, "upper")
        pw["dist"] += pd_ <= 0.05
        pw["reach"] += pr_ <= 0.05
        n_pw += 1
        rows.append((g, m, do, statistics.median(ds), ro, statistics.median(rs), pd_, pr_))
        print("graph", g, "shadow edges", m, "obs dist", do, "null median dist",
              statistics.median(ds), "obs reach", ro, "null median reach",
              statistics.median(rs), "p_dist %.3f p_reach %.3f" % (pd_, pr_), flush=True)
    print("unplanted pairs", n_fp, "false-positive rate dist %.3f reach %.3f" %
          (fp["dist"] / n_fp, fp["reach"] / n_fp))
    print("planted instances", n_pw, "power dist %.3f reach %.3f" %
          (pw["dist"] / n_pw, pw["reach"] / n_pw))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4],
         int(sys.argv[5]), int(sys.argv[6]))
