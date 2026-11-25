#!/usr/bin/env python3
"""Build a force layout from exported names/edges TSV."""
import json
import sys

import igraph as ig
import numpy as np

d = sys.argv[1] if len(sys.argv) > 1 else "/tmp/current-graph"
names = [l.strip() for l in open(f"{d}/names.txt", encoding="utf-8") if l.strip()]
idx = {m: i for i, m in enumerate(names)}
edges = []
with open(f"{d}/edges.tsv", encoding="utf-8") as fh:
    for line in fh:
        a, b = line.rstrip("\n").split("\t")
        edges.append((idx[a], idx[b]))
print("nodes", len(names), "edges", len(edges), flush=True)
g = ig.Graph(n=len(names), edges=edges, directed=True)
xy = np.array(g.layout_drl().coords, dtype=np.float32)
xy -= xy.mean(axis=0)
xy /= np.abs(xy).max()
clusters = [".".join(m.split(".")[:2]) if "." in m else m for m in names]
np.savez_compressed(f"{d}/layout.npz", xy=xy,
                    edges=np.array(edges, dtype=np.int32))
with open(f"{d}/layout.json", "w", encoding="utf-8") as fh:
    json.dump({"nodes": names, "clusters": clusters}, fh)
print("wrote", d)
