"""Calibration of Monte Carlo p-values for the constrained swap chain.

The observed graph is a stationary draw from the chain (after burn-in), so
the null hypothesis is true by construction and the rejection rate at level
0.05 should be about 0.05 for a valid procedure.

Two procedures are compared:
  naive   each of B samples is L steps from the observed graph;
  pivot   (Besag and Clifford) the observed graph is run L steps to a pivot Y,
          then B samples are L steps from Y; valid for a reversible chain
          started at stationarity.
"""
import random
import sys

from shadowlib import (Sampler, adjacency, bfs_dist, generate, mc_pvalue,
                       shadow)


def reach_size(n, edges, v0):
    return len(bfs_dist(adjacency(n, edges), v0))


def fork(base_pkg, edges, mode, seed):
    s = Sampler(base_pkg, edges, mode, random.Random(seed))
    return s


def main(trials, B, seed, mode):
    rng = random.Random(seed)
    n, n_pkg = 200, 8
    pkg, full = generate(n, n_pkg, 3.0, 0.4, 2.5, rng)
    edges = shadow(pkg, full)
    m = len(edges)
    chain = Sampler(pkg, edges, mode, random.Random(seed + 1))
    chain.run(30 * m)
    print("n", n, "shadow edges", m, "mode", mode, "acceptance",
          round(chain.accepted / chain.attempted, 3))
    Ls = [m // 4, m, 5 * m]
    rej = {("naive", L): 0 for L in Ls}
    rej.update({("pivot", L): 0 for L in Ls})
    for t in range(trials):
        chain.run(5 * m)
        obs_edges = list(chain.edges)
        out_deg = {}
        for u, _ in obs_edges:
            out_deg[u] = out_deg.get(u, 0) + 1
        v0 = rng.choice(sorted(out_deg))
        t_obs = reach_size(n, obs_edges, v0)
        for L in Ls:
            # naive
            sm = []
            for b in range(B):
                s = fork(pkg, obs_edges, mode, rng.randrange(10 ** 9))
                s.run(L)
                sm.append(reach_size(n, s.edges, v0))
            if mc_pvalue(t_obs, sm, "upper") <= 0.05:
                rej[("naive", L)] += 1
            # pivot
            y = fork(pkg, obs_edges, mode, rng.randrange(10 ** 9))
            y.run(L)
            sm = []
            for b in range(B):
                s = fork(pkg, y.edges, mode, rng.randrange(10 ** 9))
                s.run(L)
                sm.append(reach_size(n, s.edges, v0))
            if mc_pvalue(t_obs, sm, "upper") <= 0.05:
                rej[("pivot", L)] += 1
    se = (0.05 * 0.95 / trials) ** 0.5
    print("trials", trials, "B", B, "binomial s.e. at 0.05:", round(se, 4))
    for (proc, L), r in sorted(rej.items()):
        print(proc, "L =", L, "(%.2f m)" % (L / m), "rejection rate", round(r / trials, 3))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
