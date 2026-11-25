#!/usr/bin/env python3
"""Structural portraits of the import graph: k-core and longest chain.

Reads the source tree directly (import lines), computes
  - k-core decomposition (undirected import graph)
  - longest import chain from --root (directed DAG DP)
and renders both over the cached force layout.

Usage:
  module-graph-structure.py [--repo PATH] [--npz PATH] [--meta PATH]
                            [--out-dir DIR] [--root Main]
"""
import argparse
import heapq
import json
import os
import re
from collections import deque

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

IMPORT_RE = re.compile(r"^\s*(?:public\s+)?import\s+(\S+)")


def parse(repo):
    src = os.path.join(repo, "src")
    mods, imports = {}, {}
    for dp, _, fs in os.walk(src):
        for f in fs:
            if not f.endswith(".lean"):
                continue
            p = os.path.join(dp, f)
            m = os.path.relpath(p, src)[:-5].replace("/", ".")
            mods[m] = p
            imps = []
            with open(p, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    hit = IMPORT_RE.match(line)
                    if hit:
                        imps.append(hit.group(1))
            imports[m] = imps
    return mods, imports


def build(names, imports):
    idx = {m: i for i, m in enumerate(names)}
    out = [[] for _ in names]
    und = [set() for _ in names]
    for m, imps in imports.items():
        a = idx[m]
        for i in imps:
            b = idx.get(i)
            if b is None or b == a:
                continue
            out[a].append(b)
            und[a].add(b)
            und[b].add(a)
    return idx, out, und


def kcore(und):
    n = len(und)
    deg = [len(s) for s in und]
    heap = [(deg[v], v) for v in range(n)]
    heapq.heapify(heap)
    removed = [False] * n
    core = [0] * n
    while heap:
        d, v = heapq.heappop(heap)
        if removed[v] or d != deg[v]:
            continue
        removed[v] = True
        core[v] = d
        for u in und[v]:
            if not removed[u]:
                deg[u] -= 1
                und[u].discard(v)
                heapq.heappush(heap, (deg[u], u))
    return core


def longest_chain(out, idx, root):
    n = len(out)
    indeg = [0] * n
    for u in range(n):
        for v in out[u]:
            indeg[v] += 1
    q = deque([v for v in range(n) if indeg[v] == 0])
    topo = []
    while q:
        u = q.popleft()
        topo.append(u)
        for v in out[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if len(topo) != n:
        print(f"warning: {n - len(topo)} nodes in cycles; longest chain is partial")
    dist = [-1] * n
    parent = [-1] * n
    r = idx.get(root)
    if r is None:
        return [], 0
    dist[r] = 0
    for u in topo:
        if dist[u] < 0:
            continue
        for v in out[u]:
            if dist[u] + 1 > dist[v]:
                dist[v] = dist[u] + 1
                parent[v] = u
    end = max(range(n), key=lambda v: dist[v])
    chain = []
    v = end
    while v >= 0 and dist[v] >= 0:
        chain.append(v)
        if v == r:
            break
        v = parent[v]
    chain.reverse()
    return chain, dist[end]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--npz", default="/tmp/rh-module-layout.npz")
    ap.add_argument("--meta", default="/tmp/rh-module-layout.json")
    ap.add_argument("--out-dir", default="dashboard")
    ap.add_argument("--root", default="Main")
    args = ap.parse_args()

    mods, imports = parse(args.repo)
    names = sorted(mods)
    idx, out, und = build(names, imports)
    print(f"modules={len(names)} edges={sum(len(v) for v in out)}")

    core = kcore(und)
    maxc = max(core)
    print(f"k-core max={maxc}; 46-core size={sum(1 for c in core if c >= 46)}")

    chain, depth = longest_chain(out, idx, args.root)
    print(f"longest chain from {args.root}: {len(chain)} modules")

    d = np.load(args.npz)
    xy = d["xy"]
    edges = d["edges"]

    # ---- k-core portrait ----
    fig, ax = plt.subplots(figsize=(12, 12), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    ax.add_collection(LineCollection(np.stack([xy[edges[:, 0]], xy[edges[:, 1]]], axis=1),
                                     colors="#2c2350", linewidths=0.12, alpha=0.08, zorder=1))
    core_arr = np.array(core)
    sc = ax.scatter(xy[:, 0], xy[:, 1], c=core_arr,
                    s=0.5 + 0.9 * core_arr, cmap="turbo", alpha=0.85,
                    linewidths=0, zorder=2)
    cb = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label("k-core (max 46)", color="#dbe7f5")
    cb.ax.tick_params(colors="#a99bc4")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"k-core portrait — {len(names):,} modules · deepest core {maxc}",
                 color="#f2eaff", fontsize=15, pad=14)
    out1 = os.path.join(args.out_dir, "rh-module-kcore.png")
    fig.savefig(out1, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print("wrote", out1)

    # ---- critical-path spine ----
    fig, ax = plt.subplots(figsize=(12, 12), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    ax.add_collection(LineCollection(np.stack([xy[edges[:, 0]], xy[edges[:, 1]]], axis=1),
                                     colors="#2c2350", linewidths=0.12, alpha=0.08, zorder=1))
    ax.scatter(xy[:, 0], xy[:, 1], s=0.4, c="#6b5a8f", alpha=0.25,
               linewidths=0, zorder=2)
    if chain:
        cx = xy[chain, 0]
        cy = xy[chain, 1]
        for lw, alpha in ((8.0, 0.06), (3.0, 0.18), (1.2, 0.9)):
            ax.plot(cx, cy, color="#ffd166", linewidth=lw, alpha=alpha,
                    solid_capstyle="round", zorder=3)
        ax.scatter(cx, cy, s=14, c="#fff1b8", edgecolors="#ffb703",
                   linewidths=0.5, zorder=4)
        step = max(1, len(chain) // 12)
        for i in range(0, len(chain), step):
            ax.annotate(names[chain[i]].split(".")[-1][:26], (cx[i], cy[i]),
                        xytext=(5, 5), textcoords="offset points",
                        fontsize=5.5, color="#ffe9a8", zorder=5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Critical path — longest import chain: {len(chain)} modules from {args.root}",
                 color="#f2eaff", fontsize=15, pad=14)
    out2 = os.path.join(args.out_dir, "rh-module-critical-path.png")
    fig.savefig(out2, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    print("wrote", out2)


if __name__ == "__main__":
    main()
