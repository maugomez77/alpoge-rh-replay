#!/usr/bin/env python3
"""Render the layout coloured by measured compile cost (historical medians)."""
import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import LogNorm

DEFAULT_TIMES = "/Users/mauriciogomez/.rh-fix/times-rich.txt"


def load_times(path):
    times = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            p = line.split()
            if len(p) >= 4:
                try:
                    times[p[0]] = (float(p[1]), float(p[2]), int(p[3]))
                except ValueError:
                    pass
    return times


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="/tmp/rh-module-layout.npz")
    ap.add_argument("--meta", default="/tmp/rh-module-layout.json")
    ap.add_argument("--times", default=DEFAULT_TIMES)
    ap.add_argument("--out", default="dashboard/rh-module-buildtime.png")
    args = ap.parse_args()

    d = np.load(args.npz)
    xy = d["xy"]
    edges = d["edges"]
    with open(args.meta, encoding="utf-8") as f:
        meta = json.load(f)
    names = meta["nodes"]
    times = load_times(args.times)
    med = np.array([times[n][1] if n in times else np.nan for n in names])
    fallback = float(np.nanmedian(med)) if np.isfinite(med).any() else 1.0
    med = np.where(np.isfinite(med), med, fallback)

    fig, ax = plt.subplots(figsize=(12, 12), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    seg = np.stack([xy[edges[:, 0]], xy[edges[:, 1]]], axis=1)
    ax.add_collection(LineCollection(
        seg, colors="#3b2a66", linewidths=0.15, alpha=0.10, zorder=1))

    sc = ax.scatter(xy[:, 0], xy[:, 1], c=med, s=0.6 + 6 * np.sqrt(med / med.max()),
                    cmap="magma", norm=LogNorm(vmin=max(0.05, np.percentile(med, 1)),
                                               vmax=max(0.1, np.percentile(med, 99.9))),
                    alpha=0.85, linewidths=0, zorder=2)
    cb = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label("median compile seconds (log)", color="#dbe7f5")
    cb.ax.tick_params(colors="#a99bc4")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Where the build time lives — measured median compile cost",
                 color="#f2eaff", fontsize=15, pad=14)

    order = np.argsort(med)[::-1]
    total = med.sum()
    top = order[:10]
    lines = "\n".join(f"{names[i].split('.')[-1][:28]:30s} {med[i]:6.1f}s" for i in top)
    ax.text(0.01, 0.01, "slowest modules:\n" + lines, transform=ax.transAxes,
            color="#dbe7f5", fontsize=7.5, va="bottom",
            bbox=dict(boxstyle="round,pad=0.4", fc="#0b0e14", ec="#3b2a66", alpha=0.8))
    fig.savefig(args.out, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    print("wrote", args.out)
    k = max(1, len(med) // 100)
    print("total median seconds", round(total))
    print("top 1% share", round(100 * np.sort(med)[-k:].sum() / total, 1), "%")
    print("top 10", [(names[i], round(med[i], 1)) for i in top])


if __name__ == "__main__":
    main()
