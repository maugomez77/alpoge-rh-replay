#!/usr/bin/env python3
"""Full-graph Forman-Ricci curvature map (fast proxy for edge bottlenecks).

For an unweighted edge (u,v):
    F(e) = 4 - deg(u) - deg(v) + 3 * triangles(e)

Negative values are tree-like bridges / bottlenecks; positive values sit in
dense communities. This is the full 495k-edge pass; Ollivier-Ricci is computed
separately at the namespace-cluster level because per-edge OT is too slow at
module scale.

Usage:
  module-graph-forman.py [--graph-dir DIR] [--out-dir DIR]
"""
import argparse
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

CMAP = LinearSegmentedColormap.from_list(
    "ricci", ["#2b6cff", "#7c4dff", "#b388ff", "#e8e6f2", "#ffb703", "#ff5d5d"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph-dir", default="/tmp/current-graph")
    ap.add_argument("--out-dir", default="dashboard")
    ap.add_argument("--report-dir", default="evidence/curvature")
    args = ap.parse_args()

    names = [l.strip() for l in open(os.path.join(args.graph_dir, "names.txt"),
                                    encoding="utf-8") if l.strip()]
    idx = {m: i for i, m in enumerate(names)}
    edges = []
    with open(os.path.join(args.graph_dir, "edges.tsv"), encoding="utf-8") as fh:
        for line in fh:
            a, b = line.rstrip("\n").split("\t")
            edges.append((idx[a], idx[b]))
    n = len(names)
    adj = [set() for _ in range(n)]
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    deg = np.array([len(s) for s in adj])
    print(f"nodes={n} edges={len(edges)}", flush=True)

    curv = np.empty(len(edges), dtype=np.float64)
    for k, (a, b) in enumerate(edges):
        t = len(adj[a] & adj[b])
        curv[k] = 4 - deg[a] - deg[b] + 3 * t
        if k % 100000 == 0:
            print(f"  {k}/{len(edges)}", flush=True)

    order = np.argsort(curv)
    denom = deg[np.array([e[0] for e in edges])] + deg[np.array([e[1] for e in edges])]
    curv_n = curv / np.clip(denom, 1, None)
    stats = {
        "edges": len(edges),
        "mean": round(float(curv.mean()), 4),
        "median": round(float(np.median(curv)), 4),
        "min": round(float(curv.min()), 4),
        "max": round(float(curv.max()), 4),
        "negative_fraction": round(float((curv < 0).mean()), 4),
        "zero_fraction": round(float((curv == 0).mean()), 4),
        "positive_fraction": round(float((curv > 0).mean()), 4),
        "normalized_mean": round(float(curv_n.mean()), 4),
        "normalized_median": round(float(np.median(curv_n)), 4),
        "normalized_min": round(float(curv_n.min()), 4),
        "normalized_max": round(float(curv_n.max()), 4),
        "normalized_negative_fraction": round(float((curv_n < 0).mean()), 4),
        "most_negative": [
            {"edge": f"{names[edges[k][0]]} -- {names[edges[k][1]]}",
             "curvature": round(float(curv[k]), 3),
             "normalized": round(float(curv_n[k]), 3),
             "degrees": [int(deg[edges[k][0]]), int(deg[edges[k][1]])]}
            for k in order[:20]
        ],
        "most_positive": [
            {"edge": f"{names[edges[k][0]]} -- {names[edges[k][1]]}",
             "curvature": round(float(curv[k]), 3),
             "normalized": round(float(curv_n[k]), 3),
             "degrees": [int(deg[edges[k][0]]), int(deg[edges[k][1]])]}
            for k in order[-20:][::-1]
        ],
    }
    os.makedirs(args.report_dir, exist_ok=True)
    with open(os.path.join(args.report_dir, "forman.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1)

    d = np.load(os.path.join(args.graph_dir, "layout.npz"))
    xy = d["xy"]
    lo, hi = np.percentile(curv_n, 1), np.percentile(curv_n, 99)
    norm = TwoSlopeNorm(vmin=min(lo, -1e-9), vcenter=0.0, vmax=max(hi, 1e-9))

    fig, ax = plt.subplots(figsize=(12, 12), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    seg = np.stack([xy[np.array([e[0] for e in edges])],
                    xy[np.array([e[1] for e in edges])]], axis=1)
    lc = LineCollection(seg, cmap=CMAP, norm=norm, linewidths=0.35, alpha=0.35)
    lc.set_array(curv_n)
    ax.add_collection(lc)
    ax.scatter(xy[:, 0], xy[:, 1], s=0.3, c="#6b5a8f", alpha=0.2,
               linewidths=0, zorder=2)
    cb = fig.colorbar(lc, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label("normalized Forman–Ricci F(e)/(deg u + deg v)", color="#dbe7f5")
    cb.ax.tick_params(colors="#a99bc4")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Forman–Ricci curvature (degree-normalized) — {len(edges):,} imports",
                 color="#f2eaff", fontsize=15, pad=14)
    fig.savefig(os.path.join(args.out_dir, "rh-module-forman.png"), dpi=200,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    print("wrote", os.path.join(args.out_dir, "rh-module-forman.png"))
    print(json.dumps({k: stats[k] for k in
                      ("mean", "median", "min", "max",
                       "negative_fraction", "positive_fraction",
                       "normalized_mean", "normalized_median",
                       "normalized_negative_fraction")}, indent=1))


if __name__ == "__main__":
    main()
