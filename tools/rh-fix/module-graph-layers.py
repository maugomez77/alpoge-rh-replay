#!/usr/bin/env python3
"""Layered BFS render of the module import graph (depth vs barycentric order).

Builds the import graph directly from source, so it needs no layout cache.

Usage:
  module-graph-layers.py [--repo PATH] [--out PNG] [--root Main]
"""
import argparse
import os
import re
from collections import deque

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

IMPORT_RE = re.compile(r"^\s*(?:public\s+)?import\s+(\S+)")
PALETTE = ["#b388ff", "#7c4dff", "#e040fb", "#536dfe", "#18ffff",
           "#ff80ab", "#ea80fc", "#8c9eff", "#d500f9", "#64b5f6",
           "#f06292", "#b2ff59"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--out", default="dashboard/rh-module-layers.png")
    ap.add_argument("--root", default="Main")
    args = ap.parse_args()

    src = os.path.join(args.repo, "src")
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

    names = sorted(mods)
    idx = {m: i for i, m in enumerate(names)}
    edges = []
    adj = [[] for _ in names]
    for m, imps in imports.items():
        a = idx[m]
        for i in imps:
            b = idx.get(i)
            if b is not None and b != a:
                edges.append((a, b))
                adj[a].append(b)
    edges = np.array(edges, dtype=np.int32)

    root = idx.get(args.root, 0)
    parent = np.full(len(names), -1, dtype=np.int32)
    depth = np.full(len(names), -1, dtype=np.int32)
    parent[root] = root
    depth[root] = 0
    dq = deque([root])
    while dq:
        u = dq.popleft()
        for v in adj[u]:
            if depth[v] < 0:
                depth[v] = depth[u] + 1
                parent[v] = u
                dq.append(v)
    depth[depth < 0] = depth.max() + 1
    print("nodes", len(names), "edges", len(edges), "maxdepth", depth.max())

    x = np.zeros(len(names), dtype=np.float64)
    for d in range(1, int(depth.max()) + 1):
        layer = np.where(depth == d)[0]
        if len(layer) == 0:
            continue
        layer = sorted(layer, key=lambda v: (x[parent[v]] if parent[v] >= 0 else 0.0,
                                             names[v]))
        xs = (np.arange(len(layer)) + 0.5) / len(layer) - 0.5
        x[layer] = xs

    y = -depth.astype(np.float64) / max(1, depth.max())
    roots = np.array([c.split(".")[0] for c in
                      [".".join(m.split(".")[:2]) if "." in m else m for m in names]])
    uniq = sorted(set(roots.tolist()))
    color_of = {r: PALETTE[i % len(PALETTE)] for i, r in enumerate(uniq)}
    edge_colors = np.array([color_of[r] for r in roots])

    fig, ax = plt.subplots(figsize=(11, 14), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    segs = np.stack([np.column_stack([x[edges[:, 0]], y[edges[:, 0]]]),
                     np.column_stack([x[edges[:, 1]], y[edges[:, 1]]])], axis=1)
    for lw, alpha in ((2.0, 0.008), (0.8, 0.025), (0.3, 0.06)):
        ax.add_collection(LineCollection(segs, colors=edge_colors[edges[:, 0]],
                                         linewidths=lw, alpha=alpha, zorder=1))
    ax.scatter(x, y, s=1.0, c="#efe6ff", alpha=0.35, linewidths=0, zorder=2)
    ax.set_xlim(-0.55, 0.55)
    ax.set_ylim(y.min() - 0.02, 0.04)
    ax.axis("off")
    ax.set_title(f"Riemann Hypothesis formalization — import layers  ·  "
                 f"{len(names):,} modules  ·  depth {int(depth.max())}",
                 color="#f2eaff", fontsize=15, pad=14)
    fig.savefig(args.out, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    print("wrote", args.out)


if __name__ == "__main__":
    main()
