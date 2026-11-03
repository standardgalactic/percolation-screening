"""Shadow graph tools: generator, constrained swap sampler, statistics.

Plain Python only. Graph = list of directed edges (u, v) over vertices 0..n-1,
with a package label per vertex. The shadow graph keeps edges whose endpoints
lie in different packages.
"""
import random
from collections import deque


def generate(n, n_pkg, mean_out, q_internal, alpha, rng):
    """Directed Chung-Lu style graph with heavy-tailed weights and package bias.

    Returns (pkg, edges) where edges are all edges (internal and crossing).
    """
    pkg = [rng.randrange(n_pkg) for _ in range(n)]
    w_out = [rng.paretovariate(alpha) for _ in range(n)]
    w_in = [rng.paretovariate(alpha) for _ in range(n)]
    members = [[] for _ in range(n_pkg)]
    for v in range(n):
        members[pkg[v]].append(v)
    all_v = list(range(n))
    m_target = int(mean_out * n)
    edges, seen = [], set()
    tries = 0
    while len(edges) < m_target and tries < 50 * m_target:
        tries += 1
        u = rng.choices(all_v, weights=w_out)[0]
        if rng.random() < q_internal:
            pool = members[pkg[u]]
            v = rng.choices(pool, weights=[w_in[x] for x in pool])[0]
        else:
            v = rng.choices(all_v, weights=w_in)[0]
        if u == v or (u, v) in seen:
            continue
        seen.add((u, v))
        edges.append((u, v))
    return pkg, edges


def shadow(pkg, edges):
    return [(u, v) for (u, v) in edges if pkg[u] != pkg[v]]


def degree_stats(n, edges):
    """Return mean degree, K on the undirected projection, K_dir on the digraph."""
    kin, kout = [0] * n, [0] * n
    und = set()
    for u, v in edges:
        kout[u] += 1
        kin[v] += 1
        und.add((min(u, v), max(u, v)))
    deg = [0] * n
    for a, b in und:
        deg[a] += 1
        deg[b] += 1
    s1 = sum(deg)
    s2 = sum(d * d for d in deg)
    k_und = s2 / s1 if s1 else float("nan")
    mean_deg = s1 / n
    sm = sum(kout)
    k_dir = sum(a * b for a, b in zip(kin, kout)) / sm if sm else float("nan")
    return mean_deg, k_und, k_dir


class Sampler:
    """Directed double-edge swap chain on shadow graphs with fixed package labels.

    mode 'A': any swap keeping every edge crossing a package boundary.
    mode 'B': only swaps between edge pairs with the same package pair at
              their endpoints.
    Proposals pick an unordered pair of edges uniformly, so the proposal is
    symmetric and the stationary law is uniform on the reachable component.
    """

    def __init__(self, pkg, edges, mode, rng):
        self.pkg = pkg
        self.edges = list(edges)
        self.set = set(self.edges)
        self.mode = mode
        self.rng = rng
        self.accepted = 0
        self.attempted = 0

    def copy_from(self, other):
        self.edges = list(other.edges)
        self.set = set(self.edges)

    def run(self, steps):
        pkg, E, S, rnd = self.pkg, self.edges, self.set, self.rng
        m = len(E)
        mode_b = self.mode == "B"
        acc = 0
        for _ in range(steps):
            i = rnd.randrange(m)
            j = rnd.randrange(m)
            if i == j:
                continue
            a, b = E[i]
            c, d = E[j]
            if a == d or c == b:
                continue
            if mode_b:
                if pkg[a] != pkg[c] or pkg[b] != pkg[d]:
                    continue
            else:
                if pkg[a] == pkg[d] or pkg[c] == pkg[b]:
                    continue
            if (a, d) in S or (c, b) in S:
                continue
            S.discard((a, b))
            S.discard((c, d))
            S.add((a, d))
            S.add((c, b))
            E[i] = (a, d)
            E[j] = (c, b)
            acc += 1
        self.accepted += acc
        self.attempted += steps


def adjacency(n, edges):
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
    return adj


def bfs_dist(adj, src):
    dist = {src: 0}
    dq = deque([src])
    while dq:
        x = dq.popleft()
        for y in adj[x]:
            if y not in dist:
                dist[y] = dist[x] + 1
                dq.append(y)
    return dist


def mc_pvalue(obs, samples, tail):
    """Rank-based Monte Carlo p-value. tail 'upper': large statistic extreme."""
    if tail == "upper":
        k = sum(1 for s in samples if s >= obs)
    else:
        k = sum(1 for s in samples if s <= obs)
    return (1 + k) / (1 + len(samples))
