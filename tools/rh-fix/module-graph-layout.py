#!/usr/bin/env python3
"""Compute a force-directed layout of the full 47k-module import graph."""
import argparse
import json
import os
import re

import igraph as ig
import numpy as np

IMPORT_RE = re.compile(r"^\s*(?:public\s+)?import\s+(\S+)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--out", default="/tmp/rh-module-layout.npz")
    ap.add_argument("--meta", default="/tmp/rh-module-layout.json")
    ap.add_argument("--iters", type=int, default=0)
    args = ap.parse_args()

    src = os.path.join(args.repo, "src")
    mods, imports = {}, {}
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
    names = sorted(mod_set)
    idx = {m: i for i, m in enumerate(names)}
    edges = []
    for m, imps in imports.items():
        a = idx[m]
        for i in imps:
            b = idx.get(i)
            if b is not None and b != a:
                edges.append((a, b))
    print(f"nodes={len(names)} edges={len(edges)}", flush=True)

    g = ig.Graph(n=len(names), edges=edges, directed=True)
    print("layout_drl ...", flush=True)
    layout = g.layout_drl()
    xy = np.array(layout.coords, dtype=np.float32)
    xy -= xy.mean(axis=0)
    xy /= np.abs(xy).max()

    clusters = [".".join(m.split(".")[:2]) if "." in m else m for m in names]
    np.savez_compressed(args.out, xy=xy, edges=np.array(edges, dtype=np.int32))
    with open(args.meta, "w", encoding="utf-8") as f:
        json.dump({"nodes": names, "clusters": clusters}, f)
    print(f"wrote {args.out} and {args.meta}", flush=True)


if __name__ == "__main__":
    main()
