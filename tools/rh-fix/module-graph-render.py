#!/usr/bin/env python3
"""Render the full module import graph in a glowing 'neuron' style."""
import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

PALETTE = ["#b388ff", "#7c4dff", "#e040fb", "#536dfe", "#18ffff",
           "#ff80ab", "#ea80fc", "#8c9eff", "#d500f9", "#64b5f6",
           "#f06292", "#b2ff59"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="/tmp/rh-module-layout.npz")
    ap.add_argument("--meta", default="/tmp/rh-module-layout.json")
    ap.add_argument("--out", default="dashboard/rh-module-graph.png")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--size", type=float, default=13)
    args = ap.parse_args()

    d = np.load(args.npz)
    xy = d["xy"]
    edges = d["edges"]
    with open(args.meta, encoding="utf-8") as f:
        meta = json.load(f)
    roots = np.array([c.split(".")[0] for c in meta["clusters"]])
    uniq = sorted(set(roots.tolist()))
    color_of = {r: PALETTE[i % len(PALETTE)] for i, r in enumerate(uniq)}
    edge_colors = np.array([color_of[r] for r in roots])

    # robust bounds
    lo = np.percentile(xy, 0.2, axis=0)
    hi = np.percentile(xy, 99.8, axis=0)
    pad = 0.05 * (hi - lo)
    lo -= pad
    hi += pad

    fig, ax = plt.subplots(figsize=(args.size, args.size), facecolor="#05030a")
    ax.set_facecolor("#05030a")

    segs = np.stack([xy[edges[:, 0]], xy[edges[:, 1]]], axis=1)
    seg_colors = edge_colors[edges[:, 0]]

    # soft bloom passes
    for lw, alpha in ((2.2, 0.010), (0.9, 0.035), (0.35, 0.085)):
        lc = LineCollection(segs, colors=seg_colors, linewidths=lw,
                            alpha=alpha, zorder=1, capstyle="round")
        ax.add_collection(lc)

    ax.scatter(xy[:, 0], xy[:, 1], s=0.8, c="#efe6ff", alpha=0.35,
               linewidths=0, zorder=2)

    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        f"Riemann Hypothesis formalization — import graph  ·  "
        f"{len(xy):,} modules  ·  {len(edges):,} imports",
        color="#f2eaff", fontsize=15, pad=18)
    ax.text(0.5, 0.012, "every node is a .lean module · every filament an import",
            transform=ax.transAxes, ha="center", color="#a99bc4", fontsize=9)

    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
