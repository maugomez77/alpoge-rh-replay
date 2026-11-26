#!/usr/bin/env python3
"""Diff two Lake DAG snapshots by trace hash and compute the rebuild cone.

Usage:
  dag-diff.py --old old.sqlite --new new.sqlite [--out DIR] [--json]

Outputs changed modules (added/removed/dep_hash changed), the reverse-dependency
closure in the new snapshot, and the measured-cost upper bound for that cone.
"""
import argparse
import json
import os
import sqlite3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", default="evidence/dag-diff")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = sqlite3.connect(args.new)
    db.execute("ATTACH DATABASE ? AS old", (args.old,))
    changed = db.execute("""
        SELECT new.name, new.dep_hash, old.dep_hash
        FROM modules new JOIN old.modules old USING(name)
        WHERE new.dep_hash IS NOT old.dep_hash
    """).fetchall()
    added = db.execute("""
        SELECT new.name FROM modules new
        LEFT JOIN old.modules old USING(name)
        WHERE old.name IS NULL
    """).fetchall()
    removed = db.execute("""
        SELECT old.name FROM old.modules old
        LEFT JOIN modules new USING(name)
        WHERE new.name IS NULL
    """).fetchall()

    names = [r[0] for r in changed] + [r[0] for r in added]
    db.execute("CREATE TEMP TABLE changed(name TEXT PRIMARY KEY)")
    db.executemany("INSERT OR IGNORE INTO changed(name) VALUES (?)",
                   [(n,) for n in names])
    cone = db.execute("""
        WITH RECURSIVE c(m) AS (
          SELECT name FROM changed
          UNION
          SELECT i.src FROM imports i JOIN c ON i.dst = c.m
        )
        SELECT m FROM c
    """).fetchall()
    cone_names = [r[0] for r in cone]

    cost = db.execute("""
        WITH RECURSIVE c(m) AS (
          SELECT name FROM changed
          UNION
          SELECT i.src FROM imports i JOIN c ON i.dst = c.m
        )
        SELECT COALESCE(SUM(costs.median_s),0), COUNT(*)
        FROM c LEFT JOIN costs ON costs.module = c.m
    """).fetchone()

    report = {
        "old": os.path.abspath(args.old),
        "new": os.path.abspath(args.new),
        "changed": len(names),
        "added": len(added),
        "removed": len(removed),
        "closure": len(cone_names),
        "closure_cost_median_s": round(float(cost[0]), 1),
        "closure_cost_upper_16core_min": round(float(cost[0]) / 16 / 60, 1),
        "changed_modules": names[:50],
        "cone_sample": cone_names[:50],
    }
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "dag-diff.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    with open(os.path.join(args.out, "dag-diff.md"), "w", encoding="utf-8") as f:
        f.write("# Lake DAG diff\n\n")
        f.write(f"- Changed modules: **{report['changed']}** "
                f"(+{report['added']} added, -{report['removed']} removed)\n")
        f.write(f"- Rebuild closure: **{report['closure']}** modules\n")
        f.write(f"- Measured cost (median): {report['closure_cost_median_s']:,} s "
                f"(≈{report['closure_cost_upper_16core_min']} min on 16 cores)\n")
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"changed={report['changed']} added={report['added']} "
              f"removed={report['removed']} closure={report['closure']} "
              f"cost={report['closure_cost_median_s']}s")
    db.close()


if __name__ == "__main__":
    main()
