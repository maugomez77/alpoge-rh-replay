#!/usr/bin/env python3
"""Quantify near-duplicate modules: TF-IDF + SVD nearest neighbours.

Produces a JSON/Markdown report and a PNG summary:
  - nearest-neighbour cosine distribution
  - number of pairs/modules above thresholds (0.95 / 0.90 / 0.80)
  - connected-component clusters at each threshold
  - upper-bound compile-time savings if one copy per cluster is kept
  - top example pairs, validated with exact sparse cosine

Usage:
  module-graph-duplicates.py [--repo PATH] [--out-dir DIR]
"""
import argparse
import json
import os
import re
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

SKIP = re.compile(r"^(import|public import)\b")
THRESHOLDS = (0.95, 0.90, 0.80)


def load_costs(path):
    t = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            p = line.split()
            if len(p) >= 4:
                try:
                    t[p[0]] = float(p[2])
                except ValueError:
                    pass
    return t


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--costs", default=os.path.expanduser("~/.rh-fix/times-rich.txt"))
    ap.add_argument("--out-dir", default="evidence/duplicates")
    ap.add_argument("--components", type=int, default=128)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--chunk", type=int, default=2000)
    args = ap.parse_args()

    src = os.path.join(args.repo, "src")
    names, docs = [], []
    for dp, _, fs in os.walk(src):
        for f in fs:
            if not f.endswith(".lean"):
                continue
            p = os.path.join(dp, f)
            m = os.path.relpath(p, src)[:-5].replace("/", ".")
            try:
                text = open(p, encoding="utf-8", errors="ignore").read(6000)
            except OSError:
                continue
            lines = [ln for ln in text.splitlines() if not SKIP.match(ln)]
            names.append(m)
            docs.append("\n".join(lines))
    n = len(names)
    print("docs", n, flush=True)

    vec = TfidfVectorizer(max_features=30000, min_df=3, max_df=0.5,
                          token_pattern=r"[A-Za-z_][A-Za-z0-9_']*",
                          lowercase=False, dtype=np.float32)
    X = vec.fit_transform(docs)
    Z = TruncatedSVD(n_components=args.components, random_state=42).fit_transform(X)
    Zn = Z / np.clip(np.linalg.norm(Z, axis=1, keepdims=True), 1e-9, None)
    print("svd", Z.shape, flush=True)

    k = min(args.k, n - 1)
    nn_sim = np.zeros(n, dtype=np.float32)
    cand = []
    for s in range(0, n, args.chunk):
        e = min(n, s + args.chunk)
        S = Zn[s:e] @ Zn.T
        for r in range(e - s):
            S[r, s + r] = -1.0
        part = np.argpartition(-S, k, axis=1)[:, :k]
        for r in range(e - s):
            i = s + r
            row = S[r]
            for j in part[r]:
                nn_sim[i] = max(nn_sim[i], row[j])
                cand.append((i, int(j), float(row[j])))
        if s % (args.chunk * 5) == 0:
            print(f"  {e}/{n}", flush=True)

    print("mean nn", round(float(nn_sim.mean()), 3),
          "p90", round(float(np.percentile(nn_sim, 90)), 3),
          "max", round(float(nn_sim.max()), 3), flush=True)

    # exact sparse cosine for the strongest candidate pairs
    def exact(i, j):
        return float(X[i].multiply(X[j]).sum())

    cand.sort(key=lambda t: -t[2])
    top_pairs = []
    seen = set()
    for i, j, s in cand:
        a, b = (i, j) if i < j else (j, i)
        if (a, b) in seen:
            continue
        seen.add((a, b))
        top_pairs.append((a, b, s, exact(a, b)))
        if len(top_pairs) >= 40:
            break

    costs = load_costs(args.costs)
    report = {"modules": n, "thresholds": {}, "top_pairs": []}
    for thr in THRESHOLDS:
        uf = UF(n)
        pairs = 0
        for i, j, s in cand:
            if s >= thr and i != j:
                uf.union(i, j)
                pairs += 1
        clusters = defaultdict(list)
        for i in range(n):
            clusters[uf.find(i)].append(i)
        sizes = [len(v) for v in clusters.values() if len(v) > 1]
        savings = 0.0
        dup_modules = 0
        for v in clusters.values():
            if len(v) < 2:
                continue
            dup_modules += len(v) - 1
            c = [costs.get(names[i], 0.0) for i in v]
            savings += sum(c) - max(c)
        report["thresholds"][str(thr)] = {
            "pairs": pairs,
            "duplicate_clusters": len(sizes),
            "duplicate_modules_above_one": dup_modules,
            "largest_cluster": max(sizes) if sizes else 0,
            "cost_savings_upper_s": round(savings, 1),
        }

    for a, b, s, e in top_pairs:
        report["top_pairs"].append({
            "a": names[a], "b": names[b],
            "svd_cosine": round(s, 4), "exact_cosine": round(e, 4),
            "cost_a_s": costs.get(names[a], 0.0),
            "cost_b_s": costs.get(names[b], 0.0),
        })

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "duplicates.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)

    with open(os.path.join(args.out_dir, "duplicates.md"), "w", encoding="utf-8") as f:
        f.write("# Near-duplicate module census\n\n")
        f.write(f"- Modules: {n:,}\n- SVD components: {args.components}\n")
        f.write(f"- Mean NN cosine: {nn_sim.mean():.3f}; p90 {np.percentile(nn_sim,90):.3f}; "
                f"max {nn_sim.max():.3f}\n\n")
        f.write("| threshold | pairs | clusters | duplicate modules | largest | cost upper bound (s) |\n")
        f.write("|---:|---:|---:|---:|---:|---:|\n")
        for thr, d in report["thresholds"].items():
            f.write(f"| {thr} | {d['pairs']:,} | {d['duplicate_clusters']:,} | "
                    f"{d['duplicate_modules_above_one']:,} | {d['largest_cluster']:,} | "
                    f"{d['cost_savings_upper_s']:,.0f} |\n")
        f.write("\n## Top pairs (exact cosine)\n\n")
        for p in report["top_pairs"][:15]:
            f.write(f"- `{p['exact_cosine']:.3f}` — `{p['a']}` ({p['cost_a_s']:.1f}s) "
                    f"vs `{p['b']}` ({p['cost_b_s']:.1f}s)\n")

    fig, ax = plt.subplots(figsize=(9, 5), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    ax.hist(nn_sim, bins=80, color="#b388ff", alpha=0.9)
    ax.set_xlabel("nearest-neighbour cosine (SVD)", color="#a99bc4")
    ax.set_ylabel("modules", color="#a99bc4")
    ax.tick_params(colors="#a99bc4")
    for sp in ax.spines.values():
        sp.set_color("#2c2350")
    ax.set_title("Near-duplicate proximity of module source", color="#f2eaff", pad=12)
    fig.savefig(os.path.join(args.out_dir, "duplicates.png"), dpi=160,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    print("wrote", args.out_dir)
    for thr, d in report["thresholds"].items():
        print(thr, d)


if __name__ == "__main__":
    main()
