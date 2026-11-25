#!/usr/bin/env python3
"""Density-normalized render of the module import graph.

Consumes the .npz/.json produced by module-graph-layout.py and renders a
log-scaled, cluster-coloured edge-density image (reveals the core instead of
saturating it with overdraw).

Usage:
  module-graph-density.py [--npz PATH] [--meta PATH] [--out PNG]
                          [--bins 2200] [--samples 8]
"""
import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb

PALETTE = ["#b388ff", "#7c4dff", "#e040fb", "#536dfe", "#18ffff",
           "#ff80ab", "#ea80fc", "#8c9eff", "#d500f9", "#64b5f6",
           "#f06292", "#b2ff59"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="/tmp/rh-module-layout.npz")
    ap.add_argument("--meta", default="/tmp/rh-module-layout.json")
    ap.add_argument("--out", default="dashboard/rh-module-graph-density.png")
    ap.add_argument("--bins", type=int, default=2200)
    ap.add_argument("--samples", type=int, default=8)
    args = ap.parse_args()

    d = np.load(args.npz)
    xy = d["xy"].astype(np.float64)
    edges = d["edges"].astype(np.int64)
    with open(args.meta, encoding="utf-8") as f:
        meta = json.load(f)
    roots = np.array([c.split(".")[0] for c in meta["clusters"]])
    uniq = sorted(set(roots.tolist()))
    root_rgb = np.array([to_rgb(PALETTE[i % len(PALETTE)]) for i in range(len(uniq))])
    root_idx = np.array([uniq.index(r) for r in roots])
    src_rgb = root_rgb[root_idx[edges[:, 0]]]

    lo = np.percentile(xy, 0.1, axis=0)
    hi = np.percentile(xy, 99.9, axis=0)
    pad = 0.03 * (hi - lo)
    lo -= pad
    hi += pad

    t = np.linspace(0.0, 1.0, args.samples)
    x0, y0 = xy[edges[:, 0], 0], xy[edges[:, 0], 1]
    x1, y1 = xy[edges[:, 1], 0], xy[edges[:, 1], 1]
    sx = (x0[:, None] + t[None, :] * (x1 - x0)[:, None]).ravel()
    sy = (y0[:, None] + t[None, :] * (y1 - y0)[:, None]).ravel()

    bins = args.bins
    ix = np.clip(((sx - lo[0]) / (hi[0] - lo[0]) * bins).astype(np.int64), 0, bins - 1)
    iy = np.clip(((sy - lo[1]) / (hi[1] - lo[1]) * bins).astype(np.int64), 0, bins - 1)
    flat = iy * bins + ix

    count = np.bincount(flat, minlength=bins * bins).astype(np.float64)
    src_rep = np.repeat(edges[:, 0], args.samples)
    rgb = np.empty((bins * bins, 3), dtype=np.float64)
    for c in range(3):
        rgb[:, c] = np.bincount(flat, weights=src_rgb[:, c][src_rep],
                                minlength=bins * bins)
    nz = count > 0
    rgb[nz] /= count[nz, None]

    bright = np.log1p(count).reshape(bins, bins)
    bright /= bright.max()
    img = rgb.reshape(bins, bins, 3) * (bright ** 0.55)[..., None]
    img = np.clip(img * 1.6, 0, 1)

    fig, ax = plt.subplots(figsize=(12, 12), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    ax.imshow(img, origin="lower", extent=[lo[0], hi[0], lo[1], hi[1]],
              interpolation="bilinear", zorder=1)
    ax.scatter(xy[:, 0], xy[:, 1], s=0.35, c="#f4ecff", alpha=0.18,
               linewidths=0, zorder=2)
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Riemann Hypothesis formalization — edge density  ·  "
                 f"{len(xy):,} modules  ·  {len(edges):,} imports",
                 color="#f2eaff", fontsize=15, pad=16)
    ax.text(0.5, 0.012, "log-scaled edge density · colour = top-level cluster",
            transform=ax.transAxes, ha="center", color="#a99bc4", fontsize=9)
    fig.savefig(args.out, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    print("wrote", args.out)


if __name__ == "__main__":
    main()
