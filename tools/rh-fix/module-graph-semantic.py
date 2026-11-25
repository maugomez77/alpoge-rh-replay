#!/usr/bin/env python3
"""Semantic map of module source: TF-IDF -> SVD -> t-SNE, coloured by namespace.

This is an approximate view: it clusters by textual similarity of the Lean
source, not by proof dependencies. Useful for finding near-duplicate bundles
and thematic clusters.

Usage:
  module-graph-semantic.py [--repo PATH] [--out PNG] [--sample 10000]
"""
import argparse
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import TSNE

PALETTE = ["#b388ff", "#7c4dff", "#e040fb", "#536dfe", "#18ffff",
           "#ff80ab", "#ea80fc", "#8c9eff", "#d500f9", "#64b5f6",
           "#f06292", "#b2ff59"]
SKIP = re.compile(r"^(import|public import)\b")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--out", default="dashboard/rh-module-semantic.png")
    ap.add_argument("--sample", type=int, default=10000)
    ap.add_argument("--max-chars", type=int, default=4000)
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
                text = open(p, encoding="utf-8", errors="ignore").read(args.max_chars)
            except OSError:
                continue
            lines = [ln for ln in text.splitlines() if not SKIP.match(ln)]
            names.append(m)
            docs.append("\n".join(lines))
    print("docs", len(docs), flush=True)

    vec = TfidfVectorizer(max_features=30000, min_df=3, max_df=0.5,
                          token_pattern=r"[A-Za-z_][A-Za-z0-9_']*",
                          lowercase=False, dtype=np.float32)
    X = vec.fit_transform(docs)
    print("tfidf", X.shape, "nnz", X.nnz, flush=True)
    svd = TruncatedSVD(n_components=50, random_state=42)
    Z = svd.fit_transform(X)
    print("svd done, evr", round(float(svd.explained_variance_ratio_.sum()), 3),
          flush=True)

    rng = np.random.default_rng(42)
    n = min(args.sample, len(names))
    sel = rng.choice(len(names), size=n, replace=False)
    print(f"tsne on {n} points ...", flush=True)
    emb = TSNE(n_components=2, perplexity=30, max_iter=750, init="pca",
               learning_rate="auto", random_state=42, n_jobs=-1).fit_transform(Z[sel])
    print("tsne done", flush=True)

    roots = np.array([names[i].split(".")[0] for i in sel])
    uniq = sorted(set(roots.tolist()))
    color = {r: PALETTE[i % len(PALETTE)] for i, r in enumerate(uniq)}

    fig, ax = plt.subplots(figsize=(12, 12), facecolor="#05030a")
    ax.set_facecolor("#05030a")
    for r in uniq:
        m = roots == r
        ax.scatter(emb[m, 0], emb[m, 1], s=2.2, c=color[r], alpha=0.55,
                   linewidths=0, label=r)
    ax.axis("off")
    ax.set_title(f"Semantic map of module source — TF-IDF→SVD→t-SNE  ·  "
                 f"{n:,} of {len(names):,} modules",
                 color="#f2eaff", fontsize=15, pad=14)
    leg = ax.legend(loc="lower left", frameon=False, fontsize=8, markerscale=4,
                    labelcolor="#dbe7f5", ncol=2)
    fig.savefig(args.out, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    print("wrote", args.out)


if __name__ == "__main__":
    main()
