"""Exhaustive irreducibility check of constrained swap chains on tiny shadow graphs.

Six vertices in three packages of two. Every realization of a fixed in/out
degree sequence using only crossing arcs is enumerated, and the connected
components of the move graph are computed for three move sets.
"""
import itertools
import random
import sys
from collections import defaultdict

PKG = [0, 0, 1, 1, 2, 2]
N = 6
ARCS = [(u, v) for u in range(N) for v in range(N) if PKG[u] != PKG[v]]
IDX = {a: i for i, a in enumerate(ARCS)}


def signature(sub):
    kin, kout = [0] * N, [0] * N
    for i in sub:
        u, v = ARCS[i]
        kout[u] += 1
        kin[v] += 1
    return tuple(kout + kin)


def neighbours(state, move_set):
    arcs = [ARCS[i] for i in state]
    S = set(arcs)
    out = set()
    pairs = itertools.combinations(arcs, 2)
    for (a, b), (c, d) in pairs:
        if a == d or c == b:
            continue
        if PKG[a] == PKG[d] or PKG[c] == PKG[b]:
            continue
        if (a, d) in S or (c, b) in S:
            continue
        if move_set == "B" and (PKG[a] != PKG[c] or PKG[b] != PKG[d]):
            continue
        new = (S - {(a, b), (c, d)}) | {(a, d), (c, b)}
        out.add(frozenset(IDX[x] for x in new))
    if move_set == "A+C3":
        for a, b in arcs:
            for c in range(N):
                if (b, c) in S and (c, a) in S and len({a, b, c}) == 3:
                    new_arcs = [(a, c), (c, b), (b, a)]
                    if any(x in S for x in new_arcs):
                        continue
                    if any(PKG[x] == PKG[y] for x, y in new_arcs):
                        continue
                    new = (S - {(a, b), (b, c), (c, a)}) | set(new_arcs)
                    out.add(frozenset(IDX[x] for x in new))
    return out


def components(states, move_set):
    seen, comps = set(), []
    for s in states:
        if s in seen:
            continue
        comp, stack = {s}, [s]
        seen.add(s)
        while stack:
            x = stack.pop()
            for y in neighbours(x, move_set):
                if y not in seen:
                    seen.add(y)
                    comp.add(y)
                    stack.append(y)
        comps.append(len(comp))
    return comps


def main(m, n_buckets, seed):
    rng = random.Random(seed)
    buckets = defaultdict(list)
    for sub in itertools.combinations(range(len(ARCS)), m):
        buckets[signature(sub)].append(frozenset(sub))
    usable = [v for v in buckets.values() if 2 <= len(v) <= 3000]
    rng.shuffle(usable)
    usable = usable[:n_buckets]
    res = {k: 0 for k in ("A", "B", "A+C3")}
    multi = {k: 0 for k in ("A", "B", "A+C3")}
    for states in usable:
        for ms in res:
            comps = components(states, ms)
            if len(comps) == 1:
                res[ms] += 1
            else:
                multi[ms] += 1
    print("arcs available", len(ARCS), "edges m", m, "degree classes tested", len(usable))
    for ms in res:
        print(ms, "connected", res[ms], "disconnected", multi[ms])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))
