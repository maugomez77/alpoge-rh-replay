#!/usr/bin/env python3
"""Render a real dependency graph of the Lean tree from `import` lines.

Nodes are namespace clusters (top-level, or first two segments like
`Development.AutomorphicArithmetic`). Node size is the number of modules in the
cluster; edge width is the number of imports crossing clusters.

Usage:
  dep-graph.py [--repo PATH] [--out DIR] [--level 1|2] [--top N]
               [--include-external] [--min-modules N]
"""
import argparse
import json
import os
import re
from collections import Counter, defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch

IMPORT_RE = re.compile(r"^\s*(?:public\s+)?import\s+(\S+)")


def cluster(module, level):
    parts = module.split(".")
    return ".".join(parts[:level]) if len(parts) > 1 else parts[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--out", default="dashboard")
    ap.add_argument("--level", type=int, default=2, choices=[1, 2])
    ap.add_argument("--top", type=int, default=60, help="keep the N largest clusters")
    ap.add_argument("--min-modules", type=int, default=1)
    ap.add_argument("--include-external", action="store_true",
                    help="include a Mathlib node")
    ap.add_argument("--label-top", type=int, default=0,
                    help="label only the N largest clusters (0 = all)")
    ap.add_argument("--layout", choices=["spring", "circular"], default="spring")
    ap.add_argument("--name", default="dep-graph", help="output basename")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    src = os.path.join(args.repo, "src")
    mods = {}
    imports = {}
    for dp, _, fs in os.walk(src):
        for f in fs:
            if not f.endswith(".lean"):
                continue
            p = os.path.join(dp, f)
            m = os.path.relpath(p, src)[:-5].replace("/", ".")
            mods[m] = p
            imps = []
            try:
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        hit = IMPORT_RE.match(line)
                        if hit:
                            imps.append(hit.group(1))
            except OSError:
                pass
            imports[m] = imps

    mod_set = set(mods)
    nodes = Counter(cluster(m, args.level) for m in mod_set)
    root_of = {}
    for m in mod_set:
        c = cluster(m, args.level)
        root_of.setdefault(c, m.split(".")[0])

    keep = {c for c, n in nodes.items() if n >= args.min_modules}
    if len(keep) > args.top:
        keep = {c for c, _ in nodes.most_common(args.top)}

    edges = Counter()
    external = Counter()
    for m, imps in imports.items():
        a = cluster(m, args.level)
        if a not in keep:
            continue
        for i in imps:
            if i in mod_set:
                b = cluster(i, args.level)
                if b in keep and b != a:
                    edges[(a, b)] += 1
            else:
                ext = i.split(".")[0]
                if args.include_external and ext == "Mathlib":
                    external[(a, "Mathlib")] += 1

    nodes_kept = {c: nodes[c] for c in keep}
    all_nodes = dict(nodes_kept)
    if args.include_external and external:
        all_nodes["Mathlib"] = sum(external.values())

    G = nx.DiGraph()
    for c, n in all_nodes.items():
        G.add_node(c, modules=n, root=root_of.get(c, "Mathlib"))
    for (a, b), w in edges.items():
        G.add_edge(a, b, weight=w)
    if args.include_external:
        for (a, b), w in external.items():
            G.add_edge(a, b, weight=w)

    if args.layout == "circular":
        order = sorted(G.nodes(), key=lambda c: (root_of.get(c, "Mathlib"), c))
        pos = nx.circular_layout(G, scale=1.0)
        pos = {c: pos[c] for c in order}
    else:
        pos = nx.spring_layout(G, seed=args.seed, k=2.2 / np.sqrt(max(1, len(G))),
                               iterations=300, weight="weight")
    roots = sorted({d["root"] for _, d in G.nodes(data=True)})
    cmap = plt.get_cmap("tab10")
    color_of = {r: cmap(i % 10) for i, r in enumerate(roots)}

    fig, ax = plt.subplots(figsize=(15, 15), facecolor="#0b0e14")
    ax.set_facecolor("#0b0e14")

    segs, widths, alphas = [], [], []
    maxw = max((d["weight"] for _, _, d in G.edges(data=True)), default=1)
    for a, b, d in G.edges(data=True):
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        segs.append([(x1, y1), (x2, y2)])
        widths.append(0.3 + 3.0 * (d["weight"] / maxw) ** 0.5)
        alphas.append(0.05 + 0.35 * (d["weight"] / maxw) ** 0.5)
    lc = LineCollection(segs, colors=[(0.55, 0.75, 1.0, a) for a in alphas],
                        linewidths=widths, zorder=1)
    ax.add_collection(lc)

    xs, ys, sizes, colors = [], [], [], []
    for c, d in G.nodes(data=True):
        x, y = pos[c]
        xs.append(x)
        ys.append(y)
        s = 80 + 110 * np.sqrt(d["modules"])
        if args.layout == "circular":
            s = min(s, 2000)
        sizes.append(s)
        colors.append(color_of[d["root"]])
    ax.scatter(xs, ys, s=[s * 2.2 for s in sizes], c=colors, alpha=0.10,
               linewidths=0, zorder=2)
    ax.scatter(xs, ys, s=sizes, c=colors, alpha=0.95,
               edgecolors="#0b0e14", linewidths=0.8, zorder=3)

    label_nodes = set(G.nodes())
    if args.label_top > 0:
        label_nodes = {c for c, _ in nodes.most_common(args.label_top) if c in G}

    for c, d in G.nodes(data=True):
        if c not in label_nodes:
            continue
        x, y = pos[c]
        label = c if len(c) <= 34 else "…" + c[-32:]
        if args.layout == "circular":
            ang = np.degrees(np.arctan2(y, x))
            rot = ang if -90 <= ang <= 90 else ang + 180
            ha = "left" if -90 <= ang <= 90 else "right"
            ax.annotate(label, (x, y), xytext=(9 if ha == "left" else -9, 0),
                        textcoords="offset points", ha=ha, va="center",
                        rotation=rot, rotation_mode="anchor",
                        fontsize=7.0, color="#dbe7f5", zorder=4,
                        bbox=dict(boxstyle="round,pad=0.15", fc="#0b0e14",
                                  ec="none", alpha=0.55))
            continue
        ax.annotate(label, (x, y), xytext=(0, 7), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7.2, color="#dbe7f5",
                    zorder=4,
                    bbox=dict(boxstyle="round,pad=0.18", fc="#0b0e14", ec="none",
                              alpha=0.55))

    if args.layout != "circular":
        handles = [Patch(facecolor=color_of[r], label=r) for r in roots]
        ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=9,
                  labelcolor="#dbe7f5", ncol=2)
    ax.set_title(f"Lean module dependency graph — {len(mods):,} modules, "
                 f"{len(nodes_kept)} clusters, {sum(edges.values()):,} cross-cluster imports",
                 color="#eaf2ff", fontsize=14, pad=30)
    ax.text(0.5, 0.005, "node size ∝ modules in cluster · edge width ∝ imports",
            transform=ax.transAxes, ha="center", color="#8fa3b8", fontsize=9)
    ax.axis("off")
    ax.margins(0.06)

    os.makedirs(args.out, exist_ok=True)
    svg = os.path.join(args.out, f"{args.name}.svg")
    png = os.path.join(args.out, f"{args.name}.png")
    meta = os.path.join(args.out, f"{args.name}.json")
    fig.savefig(svg, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(png, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    with open(meta, "w", encoding="utf-8") as f:
        json.dump({
            "repo": os.path.abspath(args.repo),
            "modules": len(mods),
            "level": args.level,
            "clusters": [{"name": c, "modules": n, "root": root_of.get(c, "Mathlib")}
                         for c, n in sorted(nodes_kept.items(), key=lambda kv: -kv[1])],
            "edges": [{"from": a, "to": b, "imports": w}
                      for (a, b), w in edges.most_common()],
            "external_imports": sum(external.values()) if args.include_external else 0,
        }, f, indent=1)

    print(f"modules={len(mods)} clusters={len(nodes_kept)} edges={len(edges)}")
    print(f"wrote {svg}")
    print(f"wrote {png}")
    print(f"wrote {meta}")


if __name__ == "__main__":
    main()
