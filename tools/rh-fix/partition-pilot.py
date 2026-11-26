#!/usr/bin/env python3
"""Pilot: Ricci-flow communities vs spectral cut vs namespace partition.

Runs on the second-level cluster graph (<= ~316 nodes) so exact ORC/flow is
cheap. Reports topology modularity/cut, import-volume cut, ARI/NMI and
community composition. This is analysis to guide bundle boundaries, not a
build-time change.

Requires: GraphRicciCurvature, networkit, POT, python-louvain, scikit-learn.
"""
import argparse
import json
import os
from collections import Counter, defaultdict

import networkx as nx
import numpy as np
from GraphRicciCurvature.OllivierRicci import OllivierRicci
from networkx.algorithms.community import louvain_communities
from networkx.algorithms.community.quality import modularity
from sklearn.cluster import SpectralClustering
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score


def sets(partition):
    d = defaultdict(set)
    for n, c in partition.items():
        d[c].add(n)
    return list(d.values())


def metrics(G0, Gw, partition):
    parts = sets(partition)
    total0 = G0.size(weight="weight")
    totalw = Gw.size(weight="weight")
    int0 = sum(G0.subgraph(s).size(weight="weight") for s in parts)
    intw = sum(Gw.subgraph(s).size(weight="weight") for s in parts)
    return {
        "k": len(parts),
        "sizes": sorted((len(s) for s in parts), reverse=True),
        "modularity_topology": round(modularity(G0, parts, weight="weight"), 4),
        "modularity_import_volume": round(modularity(Gw, parts, weight="weight"), 4),
        "cut_topology": round(1 - int0 / total0, 4),
        "cut_import_volume": round(1 - intw / totalw, 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph-dir", default="/tmp/current-graph")
    ap.add_argument("--out-dir", default="evidence/partitions")
    ap.add_argument("--resolution", type=float, default=1.5)
    ap.add_argument("--spectral-k", type=int, default=8)
    args = ap.parse_args()

    names = [l.strip() for l in open(os.path.join(args.graph_dir, "names.txt"),
                                    encoding="utf-8") if l.strip()]
    cl = {m: ".".join(m.split(".")[:2]) for m in names}
    w = Counter()
    for line in open(os.path.join(args.graph_dir, "edges.tsv"), encoding="utf-8"):
        a, b = line.rstrip("\n").split("\t")
        x, y = cl[a], cl[b]
        if x != y:
            w[tuple(sorted((x, y)))] += 1

    Gw = nx.Graph()
    for (a, b), n in w.items():
        Gw.add_edge(a, b, weight=n)
    G0 = nx.Graph()
    G0.add_nodes_from(Gw.nodes())
    G0.add_edges_from(Gw.edges())
    nodes = sorted(G0.nodes())
    print(f"clusters={G0.number_of_nodes()} edges={G0.number_of_edges()}", flush=True)

    # Ricci flow on the unweighted topology
    orc = OllivierRicci(G0, alpha=0.5, method="OTDSinkhornMix", proc=1,
                        nbr_topk=3000, shortest_path="all_pairs", verbose="ERROR")
    Gf = orc.compute_ricci_flow(iterations=10, step=1)
    ric_comms = louvain_communities(Gf, weight="weight",
                                    resolution=args.resolution, seed=42)
    ricci = {n: i for i, c in enumerate(ric_comms) for n in c}

    # spectral cut on binary adjacency
    A = nx.to_numpy_array(G0, weight=None, nodelist=nodes)
    lab = SpectralClustering(n_clusters=args.spectral_k, affinity="precomputed",
                             assign_labels="discretize", random_state=42).fit_predict(A)
    spectral = {n: int(l) for n, l in zip(nodes, lab)}

    top = {n: n.split(".")[0] for n in nodes}

    parts = {"ricci": ricci, "spectral": spectral, "namespace": top}
    report = {"clusters": len(nodes), "import_edges": int(sum(w.values())),
              "resolution": args.resolution, "spectral_k": args.spectral_k,
              "partitions": {}, "pairwise": {}, "composition": {}}
    for name, p in parts.items():
        report["partitions"][name] = metrics(G0, Gw, p)
    keys = list(parts)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            report["pairwise"][f"{a}__{b}"] = {
                "ari": round(adjusted_rand_score([parts[a][n] for n in nodes],
                                                 [parts[b][n] for n in nodes]), 4),
                "nmi": round(normalized_mutual_info_score([parts[a][n] for n in nodes],
                                                          [parts[b][n] for n in nodes]), 4),
            }

    # composition of graph communities by top-level namespace
    for name in ("ricci", "spectral"):
        comp = defaultdict(Counter)
        for n, c in parts[name].items():
            comp[c][n.split(".")[0]] += 1
        rows = []
        for c, cnt in sorted(comp.items(), key=lambda kv: -sum(kv[1].values())):
            total = sum(cnt.values())
            root, k = cnt.most_common(1)[0]
            rows.append({"community": c, "size": total,
                         "top_root": root, "purity": round(k / total, 3),
                         "roots": dict(cnt.most_common(5))})
        report["composition"][name] = rows

    # heaviest edges crossing each partition
    report["cross_edges"] = {}
    for name, p in parts.items():
        cross = [(a, b, d["weight"]) for a, b, d in Gw.edges(data=True)
                 if p[a] != p[b]]
        cross.sort(key=lambda t: -t[2])
        report["cross_edges"][name] = [
            {"pair": f"{a} -- {b}", "imports": n} for a, b, n in cross[:15]
        ]

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "partition-pilot.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=1)

    with open(os.path.join(args.out_dir, "partition-pilot.md"), "w",
              encoding="utf-8") as f:
        f.write("# Ricci-flow vs spectral vs namespace partitions\n\n")
        f.write(f"- Clusters: {len(nodes)}\n- Import edges: {sum(w.values()):,}\n")
        f.write(f"- Ricci resolution: {args.resolution}; spectral k: {args.spectral_k}\n\n")
        f.write("| partition | k | mod (topology) | cut (topology) | mod (imports) | cut (imports) |\n")
        f.write("|---|---:|---:|---:|---:|---:|\n")
        for name, m in report["partitions"].items():
            f.write(f"| {name} | {m['k']} | {m['modularity_topology']} | "
                    f"{m['cut_topology']} | {m['modularity_import_volume']} | "
                    f"{m['cut_import_volume']} |\n")
        f.write("\n## Pairwise agreement\n\n")
        for k, v in report["pairwise"].items():
            f.write(f"- {k}: ARI {v['ari']}, NMI {v['nmi']}\n")
        f.write("\n## Ricci community composition\n\n")
        for row in report["composition"]["ricci"]:
            f.write(f"- size {row['size']}, purity {row['purity']} — {row['roots']}\n")
        f.write("\n## Spectral community composition\n\n")
        for row in report["composition"]["spectral"]:
            f.write(f"- size {row['size']}, purity {row['purity']} — {row['roots']}\n")
        f.write("\n## Heaviest cross-community imports (Ricci)\n\n")
        for e in report["cross_edges"]["ricci"][:10]:
            f.write(f"- {e['imports']:,} — {e['pair']}\n")
    print("wrote", args.out_dir)
    print(json.dumps(report["partitions"], indent=1))


if __name__ == "__main__":
    main()
