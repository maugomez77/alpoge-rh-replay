#!/usr/bin/env python3
"""Extract Lake's real build DAG into SQLite.

Data sources:
  - .lake/build/lib/lean/**/*.trace   (JSON: depHash, outputs, input hashes)
  - src/**/*.lean                     (source import edges)
  - times-rich.txt                    (optional measured costs)

The trace files are Lake's own build state (schemaVersion 2025-09-10 here).
This store is derived data: rebuild it after significant tree/build changes.

Usage:
  lake-dag.py --repo PATH --db PATH [--times PATH] [--limit-traces N]

Schema:
  modules(name PK, path, dep_hash, source_hash, olean_hash, ilean_hash,
          ir_hash, c_hash, schema_version)
  imports(src, dst)                 -- source import edges
  costs(module PK, median_s, max_s, n)
"""
import argparse
import gzip
import json
import os
import re
import sqlite3
import sys

IMPORT_RE = re.compile(r"^\s*(?:public\s+)?import\s+(\S+)")


def source_modules(repo):
    src = os.path.join(repo, "src")
    mods = {}
    imports = []
    for dp, _, fs in os.walk(src):
        for f in fs:
            if not f.endswith(".lean"):
                continue
            p = os.path.join(dp, f)
            m = os.path.relpath(p, src)[:-5].replace("/", ".")
            mods[m] = p
            with open(p, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    hit = IMPORT_RE.match(line)
                    if hit:
                        imports.append((m, hit.group(1)))
    return mods, imports


def first_output(val):
    if isinstance(val, list):
        return val[0] if val else None
    if isinstance(val, str):
        return val
    return None


def load_times(path):
    if not path or not os.path.exists(path):
        return {}
    opener = gzip.open if path.endswith(".gz") else open
    out = {}
    with opener(path, "rt", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            p = line.split()
            if len(p) >= 4:
                try:
                    out[p[0]] = (float(p[1]), float(p[2]), int(p[3]))
                except ValueError:
                    pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--db", default="/tmp/lake-dag.sqlite")
    ap.add_argument("--times", default=os.path.expanduser("~/.rh-fix/times-rich.txt"))
    ap.add_argument("--limit-traces", type=int, default=0)
    args = ap.parse_args()

    mods, imports = source_modules(args.repo)
    print(f"source modules={len(mods)} imports={len(imports)}", flush=True)
    times = load_times(args.times)

    trace_root = os.path.join(args.repo, ".lake/build/lib/lean")
    traces = []
    for dp, _, fs in os.walk(trace_root):
        for f in fs:
            if f.endswith(".trace"):
                traces.append(os.path.join(dp, f))
    traces.sort()
    if args.limit_traces:
        traces = traces[: args.limit_traces]
    print(f"trace files={len(traces)}", flush=True)

    if os.path.exists(args.db):
        os.remove(args.db)
    db = sqlite3.connect(args.db)
    db.executescript("""
      PRAGMA journal_mode=WAL;
      CREATE TABLE modules(
        name TEXT PRIMARY KEY, path TEXT, dep_hash TEXT, source_hash TEXT,
        olean_hash TEXT, ilean_hash TEXT, ir_hash TEXT, c_hash TEXT,
        schema_version TEXT);
      CREATE TABLE imports(src TEXT, dst TEXT, PRIMARY KEY(src, dst));
      CREATE TABLE costs(module TEXT PRIMARY KEY, median_s REAL, max_s REAL, n INTEGER);
      CREATE INDEX imports_dst ON imports(dst);
      CREATE INDEX modules_dep ON modules(dep_hash);
    """)

    seen = set()
    for path in traces:
        rel = os.path.relpath(path, trace_root)[:-len(".trace")]
        mod = rel.replace("/", ".")
        try:
            d = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        outs = d.get("outputs") or {}
        source_hash = None
        for item in d.get("inputs") or []:
            try:
                name, val = item[0], item[1]
            except (IndexError, TypeError):
                continue
            if isinstance(name, str) and name.endswith(".lean") and "/src/" in name:
                source_hash = val
                break
        db.execute(
            "INSERT OR REPLACE INTO modules VALUES (?,?,?,?,?,?,?,?,?)",
            (mod, mods.get(mod), d.get("depHash"), source_hash,
             first_output(outs.get("o")), first_output(outs.get("i")),
             first_output(outs.get("r")), first_output(outs.get("c")),
             d.get("schemaVersion")))
        seen.add(mod)

    # modules known from source but without traces
    for m, p in mods.items():
        db.execute("INSERT OR IGNORE INTO modules(name, path) VALUES (?,?)", (m, p))

    db.executemany("INSERT OR IGNORE INTO imports(src, dst) VALUES (?,?)", imports)
    for m, (mx, med, n) in times.items():
        db.execute("INSERT OR REPLACE INTO costs VALUES (?,?,?,?)", (m, med, mx, n))
    db.commit()

    counts = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("modules", "imports", "costs")}
    traced = db.execute("SELECT COUNT(*) FROM modules WHERE dep_hash IS NOT NULL").fetchone()[0]
    print(f"db={args.db} modules={counts['modules']} traced={traced} "
          f"imports={counts['imports']} costs={counts['costs']}")
    print("top in-degree:", db.execute(
        "SELECT dst, COUNT(*) n FROM imports GROUP BY dst ORDER BY n DESC LIMIT 5").fetchall())
    db.close()


if __name__ == "__main__":
    main()
