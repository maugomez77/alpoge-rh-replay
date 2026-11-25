#!/usr/bin/env python3
"""Per-module compile-time stats from all /work logs: max, median, count."""
import glob
import re
import statistics
from collections import defaultdict

vals = defaultdict(list)
for path in glob.glob("/work/*.log"):
    try:
        fh = open(path, encoding="utf-8", errors="ignore")
    except OSError:
        continue
    for line in fh:
        m = re.search(r"Built (\S+) \(([\d.]+)s\)", line)
        if m:
            vals[m.group(1)].append(float(m.group(2)))
    fh.close()

with open("/work/times-rich.txt", "w", encoding="utf-8") as f:
    for mod in sorted(vals):
        v = vals[mod]
        f.write(f"{mod}\t{max(v):.1f}\t{statistics.median(v):.1f}\t{len(v)}\n")
print("modules", len(vals))
