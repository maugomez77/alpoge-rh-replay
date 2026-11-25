#!/usr/bin/env python3
"""Export names, internal import edges, and instance-disable counts for a tree."""
import os
import re
import sys

repo, out = sys.argv[1], sys.argv[2]
src = os.path.join(repo, "src")
IMPORT_RE = re.compile(r"^\s*(?:public\s+)?import\s+(\S+)")
INST_RE = re.compile(r"attribute\s*\[-instance\]")

os.makedirs(out, exist_ok=True)
names, imports, counts = {}, {}, {}
for dp, _, fs in os.walk(src):
    for f in fs:
        if not f.endswith(".lean"):
            continue
        p = os.path.join(dp, f)
        m = os.path.relpath(p, src)[:-5].replace("/", ".")
        names[m] = p
        imps, n = [], 0
        with open(p, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                h = IMPORT_RE.match(line)
                if h:
                    imps.append(h.group(1))
                if INST_RE.search(line):
                    n += 1
        imports[m] = imps
        if n:
            counts[m] = n

with open(os.path.join(out, "names.txt"), "w", encoding="utf-8") as fh:
    for m in sorted(names):
        fh.write(m + "\n")

with open(os.path.join(out, "edges.tsv"), "w", encoding="utf-8") as fh:
    for m in sorted(names):
        for i in imports[m]:
            if i in names and i != m:
                fh.write(f"{m}\t{i}\n")

with open(os.path.join(out, "instance-counts.tsv"), "w", encoding="utf-8") as fh:
    for m in sorted(counts):
        fh.write(f"{m}\t{counts[m]}\n")

print("modules", len(names), "counts", len(counts),
      "lines", sum(counts.values()))
