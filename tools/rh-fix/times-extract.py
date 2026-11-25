#!/usr/bin/env python3
"""Per-module compile-time history from build logs, persisted across runs.

Every Lake log line of the form
    ✔ [i/n] Built Foo.Bar.Bundle0123 (3.3s)
is a sample. We keep the most recent --cap samples per module in a JSON
database (default ~/.rh-fix/build-costs.json), so the history survives log
rotation and can feed plan.py / progress estimates.

Writes:
  - <db>            module -> [seconds, ...]  (JSON)
  - /work/times-rich.txt   module<TAB>max<TAB>median<TAB>n
  - ~/.rh-fix/times.txt    module<TAB>median

Usage:
  times-extract.py [--logs GLOB] [--db PATH] [--out PATH] [--times PATH]
"""
import argparse
import glob
import json
import os
import re
import statistics
from collections import defaultdict

LINE_RE = re.compile(r"Built (\S+) \(([\d.]+)s\)")


def load_db(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {k: [float(x) for x in v] for k, v in data.items()}
    except (OSError, ValueError):
        pass
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="/work/*.log")
    ap.add_argument("--db", default=os.path.expanduser("~/.rh-fix/build-costs.json"))
    ap.add_argument("--out", default="/work/times-rich.txt")
    ap.add_argument("--times", default=os.path.expanduser("~/.rh-fix/times.txt"))
    ap.add_argument("--cap", type=int, default=20, help="samples kept per module")
    args = ap.parse_args()

    db = load_db(args.db)
    fresh = defaultdict(int)
    seen_logs = 0
    for path in sorted(glob.glob(args.logs)):
        try:
            fh = open(path, encoding="utf-8", errors="ignore")
        except OSError:
            continue
        seen_logs += 1
        for line in fh:
            m = LINE_RE.search(line)
            if not m:
                continue
            mod, secs = m.group(1), float(m.group(2))
            samples = db.setdefault(mod, [])
            samples.append(secs)
            if len(samples) > args.cap:
                del samples[: len(samples) - args.cap]
            fresh[mod] += 1
        fh.close()

    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)
    with open(args.db, "w", encoding="utf-8") as f:
        json.dump(db, f, sort_keys=True)
        f.write("\n")

    with open(args.out, "w", encoding="utf-8") as f:
        for mod in sorted(db):
            v = db[mod]
            if not v:
                continue
            f.write(f"{mod}\t{max(v):.1f}\t{statistics.median(v):.1f}\t{len(v)}\n")

    with open(args.times, "w", encoding="utf-8") as f:
        for mod in sorted(db):
            v = db[mod]
            if v:
                f.write(f"{mod}\t{statistics.median(v):.1f}\n")

    print(f"logs={seen_logs} modules={len(db)} new_samples={sum(fresh.values())}")
    print(f"db={args.db}")
    print(f"times={args.out} ({len(db)} modules)")


if __name__ == "__main__":
    main()
