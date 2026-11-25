#!/usr/bin/env python3
"""Extract per-module completion intervals for one build (log + olean mtimes)."""
import csv
import os
import re
import sys
from datetime import datetime, timezone

log, repo, out = sys.argv[1], sys.argv[2], sys.argv[3]
start = None
built = {}
with open(log, encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        m = re.match(r"start=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", line)
        if m:
            start = m.group(1)
            continue
        m = re.search(r"Built (\S+) \(([\d.]+)s\)", line)
        if m:
            built[m.group(1)] = float(m.group(2))

if start is None:
    print("no start= header", file=sys.stderr)
    sys.exit(2)
t0 = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()

rows = []
for mod, secs in built.items():
    p = os.path.join(repo, ".lake/build/lib/lean", mod.replace(".", "/") + ".olean")
    try:
        mt = os.path.getmtime(p)
    except OSError:
        continue
    if mt < t0 - 5:
        continue
    rows.append((mod, secs, mt - secs, mt))

rows.sort(key=lambda r: r[2])
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["module", "seconds", "start", "end"])
    w.writerows(rows)
print(f"start={start} logged={len(built)} with_fresh_olean={len(rows)}")
