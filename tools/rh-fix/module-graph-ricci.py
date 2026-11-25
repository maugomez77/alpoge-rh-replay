#!/usr/bin/env python3
"""Exact Ollivier-Ricci curvature at namespace-cluster level.

Module-level exact ORC is impractical here (per-edge optimal transport over
neighborhood shortest paths). At cluster level the graphs are 10-316 nodes, so
exact ORC is fast and still reveals architectural bridges vs communities.

Usage:
  module-graph-ricci.py [--graph-dir DIR] [--out-dir DIR]
"""
import argparse
import json
import os

import networkx as nx
from GraphRicciCurvature.OllivierRicci import OllivierRicci


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph-dir", default="/tmp/current-graph")
    ap.add_argument("--out-dir", default="evidence/curvature")
    args = ap.parse_args()

    names = [l.strip() for l in open(os.path.join(args.graph_dir, "names.txt"),
                                    encoding="utf-8") if l.strip()]
    edges = []
    with open(os.path.join(args.graph_dir, "edges.tsv"), encoding="utf-8") as fh:
        for line in fh:
            a, b = line.rstrip("\n").split("\t")
            edges.append((a, b))

    report = {"levels": {}, "modules": len(names), "edges": len(edges)}
    for level in (1, 2):
        cl = {m: ".".join(m.split(".")[:level]) for m in names}
        pairs = {(cl[a], cl[b]) for a, b in edges if cl[a] != cl[b]}
        G = nx.Graph()
        G.add_edges_from(pairs)
        orc = OllivierRicci(G, alpha=0.5, method="OTDSinkhornMix", proc=1,
                            nbr_topk=3000, verbose="ERROR")
        orc.compute_ricci_curvature()
        items = [(a, b, float(d["ricciCurvature"]))
                 for a, b, d in orc.G.edges(data=True)]
        items.sort(key=lambda t: t[2])
        vals = [v for _, _, v in items]
        report["levels"][str(level)] = {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "mean": round(sum(vals) / len(vals), 4),
            "negative": sum(1 for v in vals if v < 0),
            "most_negative": [
                {"edge": f"{a} -- {b}", "curvature": round(v, 4)}
                for a, b, v in items[:10]
            ],
            "most_positive": [
                {"edge": f"{a} -- {b}", "curvature": round(v, 4)}
                for a, b, v in items[-10:][::-1]
            ],
        }

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "ricci-clusters.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    with open(os.path.join(args.out_dir, "ricci-clusters.md"), "w",
              encoding="utf-8") as f:
        f.write("# Ollivier–Ricci curvature by namespace level\n\n")
        for level, d in report["levels"].items():
            f.write(f"## Level {level} — {d['nodes']} nodes, {d['edges']} edges\n\n")
            f.write(f"- mean curvature: {d['mean']}\n")
            f.write(f"- negative edges: {d['negative']}/{d['edges']}\n\n")
            f.write("| most negative (bridges) | κ |\n|---|---:|\n")
            for e in d["most_negative"]:
                f.write(f"| `{e['edge']}` | {e['curvature']} |\n")
            f.write("\n| most positive (communities) | κ |\n|---|---:|\n")
            for e in d["most_positive"]:
                f.write(f"| `{e['edge']}` | {e['curvature']} |\n")
            f.write("\n")
    print("wrote", args.out_dir)
    for level, d in report["levels"].items():
        print("level", level, "nodes", d["nodes"], "edges", d["edges"],
              "mean", d["mean"], "neg", d["negative"])


if __name__ == "__main__":
    main()
