#!/usr/bin/env python3
"""Render a real build timeline (Gantt) from a log+olean-mtime CSV.

The CSV is produced inside the container by extract-timeline.py. Lanes are
assigned greedily by start time, so lane count is an observed concurrency
estimate, not a fixed assumption.

Usage:
  module-graph-timeline.py [--csv PATH] [--out PNG]
"""
import argparse
import csv
import heapq

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection

PALETTE = ["#b388ff", "#7c4dff", "#e040fb", "#536dfe", "#18ffff",
           "#ff80ab", "#ea80fc", "#8c9eff", "#d500f9", "#64b5f6",
           "#f06292", "#b2ff59"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="/tmp/timeline-mainbuild16b.csv")
    ap.add_argument("--out", default="dashboard/rh-module-timeline.png")
    args = ap.parse_args()

    rows = []
    with open(args.csv, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append((r["module"], float(r["seconds"]),
                         float(r["start"]), float(r["end"])))
    if not rows:
        raise SystemExit("empty timeline")
    rows.sort(key=lambda r: r[2])
    t0 = rows[0][2]
    span = max(r[3] for r in rows) - t0

    lane_end = []
    placed = []
    next_lane = 0
    for mod, secs, start, end in rows:
        if lane_end and lane_end[0][0] <= start:
            _, lane = heapq.heappop(lane_end)
        else:
            lane = next_lane
            next_lane += 1
        heapq.heappush(lane_end, (end, lane))
        placed.append((start - t0, lane, max(0.05, end - start), mod, secs))

    roots = [m.split(".")[0] for _, _, _, m, _ in placed]
    uniq = sorted(set(roots))
    color = {r: PALETTE[i % len(PALETTE)] for i, r in enumerate(uniq)}

    verts, cols = [], []
    for (x, lane, w, m, s), root in zip(placed, roots):
        verts.append([(x, lane - 0.42), (x + w, lane - 0.42),
                      (x + w, lane + 0.42), (x, lane + 0.42)])
        cols.append(color[root])

    fig, ax = plt.subplots(figsize=(15, 7), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    ax.add_collection(PolyCollection(verts, facecolors=cols, edgecolors="none",
                                     alpha=0.9))
    ax.set_xlim(0, span / 60)
    ax.set_ylim(-1, max(l for _, l, _, _, _ in placed) + 1)
    ax.set_xlabel("minutes since build start", color="#a99bc4")
    ax.set_ylabel("concurrency lane (greedy packed)", color="#a99bc4")
    ax.tick_params(colors="#a99bc4")
    for sp in ax.spines.values():
        sp.set_color("#2c2350")
    ax.set_title(f"Build timeline — {len(placed):,} modules in {span/60:.0f} min  ·  "
                 f"observed lanes {max(l for _, l, _, _, _ in placed)+1}",
                 color="#f2eaff", fontsize=15, pad=12)

    ax2 = ax.twinx()
    t = np.array([p[0] for p in placed]) / 60
    cum = np.arange(1, len(placed) + 1)
    ax2.plot(t, cum, color="#ffd166", linewidth=1.2, alpha=0.8)
    ax2.set_ylabel("modules completed", color="#ffd166")
    ax2.tick_params(colors="#ffd166")
    for sp in ax2.spines.values():
        sp.set_color("#2c2350")
    ax2.set_facecolor("#05030a")

    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=color[r], label=r) for r in uniq],
              loc="upper left", frameon=False, fontsize=8,
              labelcolor="#dbe7f5", ncol=2)
    fig.savefig(args.out, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    print("wrote", args.out)


if __name__ == "__main__":
    main()
