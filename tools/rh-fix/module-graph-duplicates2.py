#!/usr/bin/env python3
"""Strict near-duplicate census: rare identifiers kept + Jaccard validation.

v1 used min_df=3, which dropped the distinguishing theorem/identifier names and
made boilerplate-only modules look identical (cosine 1.0, token Jaccard 0.15).
v2 keeps all tokens (min_df=1), then validates every high-cosine candidate with
a stopword-filtered token Jaccard.

Usage:
  module-graph-duplicates2.py [--repo PATH] [--out-dir DIR]
"""
import argparse
import json
import os
import re
from collections import defaultdict

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

SKIP = re.compile(r"^(import|public import)\b")
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_']{2,}")
STOP = {
    "theorem", "lemma", "def", "instance", "structure", "class", "where", "by",
    "simp", "exact", "apply", "intro", "intros", "rw", "have", "let", "fun",
    "Type", "Prop", "Sort", "section", "namespace", "end", "open", "variable",
    "noncomputable", "private", "public", "protected", "scoped", "attribute",
    "deriving", "extends", "forall", "exists", "match", "with", "then", "else",
    "return", "do", "at", "in", "of", "to", "the", "and", "or", "not", "is",
}


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
    ap.add_argument("--out-dir", default="evidence/duplicates")
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
            text = open(p, encoding="utf-8", errors="ignore").read(8000)
            names.append(m)
            docs.append("\n".join(l for l in text.splitlines() if not SKIP.match(l)))
    n = len(names)
    print("docs", n, flush=True)

    vec = TfidfVectorizer(min_df=1, max_df=0.5,
                          token_pattern=r"[A-Za-z_][A-Za-z0-9_']*",
                          lowercase=False, dtype=np.float32)
    X = vec.fit_transform(docs)
    print("tfidf", X.shape, "nnz", X.nnz, flush=True)
    Z = TruncatedSVD(n_components=128, random_state=42).fit_transform(X)
    Zn = Z / np.clip(np.linalg.norm(Z, axis=1, keepdims=True), 1e-9, None)
    print("svd done", flush=True)

    toks = {}

    def token_set(i):
        if i not in toks:
            toks[i] = {t for t in TOKEN.findall(docs[i]) if t not in STOP}
        return toks[i]

    k = min(args.k, n - 1)
    cand = []
    for s in range(0, n, args.chunk):
        e = min(n, s + args.chunk)
        S = Zn[s:e] @ Zn.T
        for r in range(e - s):
            S[r, s + r] = -1.0
        part = np.argpartition(-S, k, axis=1)[:, :k]
        for r in range(e - s):
            i = s + r
            for j in part[r]:
                cand.append((i, int(j), float(S[r, j])))
        print(f"  {e}/{n}", flush=True)

    seen = set()
    scored = []
    for i, j, c in cand:
        a, b = (i, j) if i < j else (j, i)
        if (a, b) in seen:
            continue
        seen.add((a, b))
        if c < 0.80:
            continue
        ta, tb = token_set(a), token_set(b)
        if not ta or not tb:
            continue
        jac = len(ta & tb) / len(ta | tb)
        scored.append((a, b, c, jac))

    print("pairs scored", len(scored), flush=True)
    report = {"modules": n, "vocab": X.shape[1], "pairs": {}}
    for cthr, jthr in ((0.95, 0.80), (0.95, 0.60), (0.90, 0.70),
                       (0.90, 0.50), (0.85, 0.50)):
        uf = UF(n)
        pairs = 0
        for a, b, c, jac in scored:
            if c >= cthr and jac >= jthr:
                uf.union(a, b)
                pairs += 1
        clusters = defaultdict(list)
        for i in range(n):
            clusters[uf.find(i)].append(i)
        sizes = [len(v) for v in clusters.values() if len(v) > 1]
        dup = sum(len(v) - 1 for v in clusters.values() if len(v) > 1)
        report["pairs"][f"cos>={cthr},jaccard>={jthr}"] = {
            "pairs": pairs, "clusters": len(sizes),
            "duplicate_modules": dup, "largest": max(sizes) if sizes else 0,
        }

    scored.sort(key=lambda t: (-t[2], -t[3]))
    report["top_pairs"] = [
        {"a": names[a], "b": names[b], "cosine": round(c, 4),
         "jaccard": round(j, 4)}
        for a, b, c, j in scored[:25]
    ]

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "duplicates-strict.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    with open(os.path.join(args.out_dir, "duplicates-strict.md"), "w",
              encoding="utf-8") as f:
        f.write("# Strict near-duplicate census (rare identifiers kept)\n\n")
        f.write(f"- Modules: {n:,}\n- Vocabulary: {X.shape[1]:,}\n")
        f.write("- Duplicate requires **both** SVD cosine and token Jaccard.\n\n")
        f.write("| condition | pairs | clusters | duplicate modules | largest |\n")
        f.write("|---|---:|---:|---:|---:|\n")
        for key, d in report["pairs"].items():
            f.write(f"| {key} | {d['pairs']:,} | {d['clusters']:,} | "
                    f"{d['duplicate_modules']:,} | {d['largest']:,} |\n")
        f.write("\n## Top pairs\n\n")
        for p in report["top_pairs"][:15]:
            f.write(f"- cos {p['cosine']:.3f} · Jaccard {p['jaccard']:.3f} — "
                    f"`{p['a']}` vs `{p['b']}`\n")
    print("wrote", args.out_dir)
    for key, d in report["pairs"].items():
        print(key, d)


if __name__ == "__main__":
    main()
