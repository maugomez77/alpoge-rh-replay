#!/usr/bin/env python3
"""Render the full-graph Ollivier-Ricci curvature map from shard artifacts."""
import argparse
import glob
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
    ap.add_argument("--shards", default="/tmp/ricci-shards")
    ap.add_argument("--graph", default="/tmp/current-graph")
    ap.add_argument("--out", default="dashboard/rh-module-ricci.png")
    args = ap.parse_args()

    names = [l.strip() for l in open(os.path.join(args.graph, "names.txt"),
                                    encoding="utf-8") if l.strip()]
    idx = {m: i for i, m in enumerate(names)}
    rows = []
    for path in glob.glob(os.path.join(args.shards, "**", "ricci-[0-9]*.json"),
                          recursive=True):
        if "report" in path:
            continue
        d = json.load(open(path, encoding="utf-8"))
        rows.extend(d.get("edges", []))
    print("edges", len(rows), flush=True)

    a = np.array([idx[r["u"]] for r in rows])
    b = np.array([idx[r["v"]] for r in rows])
    k = np.array([r["kappa"] for r in rows])

    d = np.load(os.path.join(args.graph, "layout.npz"))
    xy = d["xy"]
    seg = np.stack([xy[a], xy[b]], axis=1)

    lo, hi = np.percentile(k, 1), np.percentile(k, 99)
    norm = TwoSlopeNorm(vmin=min(lo, -1e-9), vcenter=0.0, vmax=max(hi, 1e-9))

    fig, ax = plt.subplots(figsize=(12, 12), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    lc = LineCollection(seg, cmap=CMAP, norm=norm, linewidths=0.3, alpha=0.3)
    lc.set_array(k)
    ax.add_collection(lc)
    ax.scatter(xy[:, 0], xy[:, 1], s=0.3, c="#6b5a8f", alpha=0.18,
               linewidths=0, zorder=2)
    cb = fig.colorbar(lc, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label("Ollivier–Ricci curvature κ", color="#dbe7f5")
    cb.ax.tick_params(colors="#a99bc4")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Ollivier–Ricci curvature — all {len(k):,} imports  ·  "
                 f"{100*(k<0).mean():.1f}% negative  ·  mean {k.mean():.3f}",
                 color="#f2eaff", fontsize=14, pad=14)
    fig.savefig(args.out, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    print("wrote", args.out)


if __name__ == "__main__":
    main()
