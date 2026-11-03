"""Degree-moment ratios against observed giant components on the shadow graph."""
import random
import sys

from shadowlib import degree_stats, generate, shadow


def wcc_largest(n, edges):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for u, v in edges:
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
    sizes = {}
    for x in range(n):
        r = find(x)
        sizes[r] = sizes.get(r, 0) + 1
    return max(sizes.values())


def scc_largest(n, edges):
    adj = [[] for _ in range(n)]
    radj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        radj[v].append(u)
    seen, order = [False] * n, []
    for s in range(n):
        if seen[s]:
            continue
        seen[s] = True
        stack = [(s, 0)]
        while stack:
            x, i = stack.pop()
            if i < len(adj[x]):
                stack.append((x, i + 1))
                y = adj[x][i]
                if not seen[y]:
                    seen[y] = True
                    stack.append((y, 0))
            else:
                order.append(x)
    comp, best = [-1] * n, 0
    for s in reversed(order):
        if comp[s] != -1:
            continue
        comp[s] = s
        size, stack = 0, [s]
        while stack:
            x = stack.pop()
            size += 1
            for y in radj[x]:
                if comp[y] == -1:
                    comp[y] = s
                    stack.append(y)
        best = max(best, size)
    return best


def main(n, seed):
    rng = random.Random(seed)
    print("mean_out  mean_deg      K   K_dir  WCC_frac  SCC_frac")
    for mo in (0.4, 0.8, 1.2, 1.6, 2.0, 3.0, 4.0):
        pkg, full = generate(n, 20, mo, 0.4, 2.5, rng)
        sh = shadow(pkg, full)
        c, k, kd = degree_stats(n, sh)
        print("%8.1f %9.3f %6.3f %7.3f %9.3f %9.3f" % (
            mo, c, k, kd, wcc_largest(n, sh) / n, scc_largest(n, sh) / n))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
