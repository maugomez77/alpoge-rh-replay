#!/usr/bin/env python3
"""Map the `attribute [-instance]` debt onto the import-graph layout."""
import argparse
import json
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

PAT = re.compile(r"attribute\s*\[-instance\]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--npz", default="/tmp/rh-module-layout.npz")
    ap.add_argument("--meta", default="/tmp/rh-module-layout.json")
    ap.add_argument("--counts", default=None,
                    help="TSV module<TAB>count from export-graph.py "
                         "(skips source parsing)")
    ap.add_argument("--out", default="dashboard/rh-module-instances.png")
    args = ap.parse_args()

    if args.counts:
        counts = {}
        with open(args.counts, encoding="utf-8") as fh:
            for line in fh:
                mod, n = line.rstrip("\n").split("\t")
                counts[mod] = int(n)
    else:
        src = os.path.join(args.repo, "src")
        counts = {}
        for dp, _, fs in os.walk(src):
            for f in fs:
                if not f.endswith(".lean"):
                    continue
                p = os.path.join(dp, f)
                m = os.path.relpath(p, src)[:-5].replace("/", ".")
                n = 0
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        if PAT.search(line):
                            n += 1
                if n:
                    counts[m] = n

    d = np.load(args.npz)
    xy = d["xy"]
    edges = d["edges"]
    with open(args.meta, encoding="utf-8") as f:
        meta = json.load(f)
    names = meta["nodes"]
    vals = np.array([counts.get(m, 0) for m in names])
    files = int((vals > 0).sum())
    total = int(vals.sum())

    fig, ax = plt.subplots(figsize=(12, 12), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    ax.add_collection(LineCollection(
        np.stack([xy[edges[:, 0]], xy[edges[:, 1]]], axis=1),
        colors="#241b3f", linewidths=0.12, alpha=0.08, zorder=1))
    nz = vals > 0
    sc = ax.scatter(xy[~nz, 0], xy[~nz, 1], s=0.5, c="#4a4066", alpha=0.4,
                    linewidths=0, zorder=2)
    sc = ax.scatter(xy[nz, 0], xy[nz, 1],
                    c=vals[nz], s=6 + 8 * np.sqrt(vals[nz]),
                    cmap="plasma", alpha=0.9, linewidths=0, zorder=3)
    cb = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label("`attribute [-instance]` lines", color="#dbe7f5")
    cb.ax.tick_params(colors="#a99bc4")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Instance-shadow debt — {total:,} disables in {files:,} modules",
                 color="#f2eaff", fontsize=15, pad=14)

    top = sorted(counts.items(), key=lambda kv: -kv[1])[:10]
    txt = "\n".join(f"{m.split('.')[-1][:26]:28s} {v:5d}" for m, v in top)
    ax.text(0.01, 0.01, "most disabled modules:\n" + txt, transform=ax.transAxes,
            color="#ffe9d6", fontsize=7.2, va="bottom",
            bbox=dict(boxstyle="round,pad=0.4", fc="#0b0e14", ec="#5a2a1a", alpha=0.85))
    fig.savefig(args.out, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"wrote {args.out} ({total} lines in {files} modules)")
    print("top:", top[:5])


if __name__ == "__main__":
    main()
