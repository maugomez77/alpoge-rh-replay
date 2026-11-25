#!/usr/bin/env python3
"""Beforehand estimate for a Lake target: modules, jobs, must-build set, time.

Uses:
  - import-graph closure (exact module count)
  - Lake .trace files (source/import mtimes -> staleness)
  - per-module compile stats (max/median/count)

Usage:
  plan.py --repo PATH [--targets Main Challenge] [--times times-rich.txt]
          [--time-stat median|max] [--jobs-per-module 4]
          [--parallel 12] [--jobs-per-min 900] [--json]
"""
import argparse
import json
import os
import sys
from collections import deque

DEFAULT_TARGETS = ["Main", "Challenge"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--targets", nargs="+", default=DEFAULT_TARGETS)
    ap.add_argument("--times", default=None)
    ap.add_argument("--time-stat", choices=["median", "max"], default="median")
    ap.add_argument("--jobs-per-module", type=float, default=4.0)
    ap.add_argument("--parallel", type=int, default=12)
    ap.add_argument("--jobs-per-min", type=float, default=1000.0,
                    help="Lake job processing rate (replays + compiles)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    src = os.path.join(args.repo, "src")
    lib = os.path.join(args.repo, ".lake/build/lib/lean")

    mods, imports = {}, {}
    for dp, _, fs in os.walk(src):
        for f in fs:
            if not f.endswith(".lean"):
                continue
            p = os.path.join(dp, f)
            m = os.path.relpath(p, src)[:-5].replace("/", ".")
            mods[m] = p
            imps = []
            for line in open(p, encoding="utf-8", errors="ignore"):
                if line.startswith("import ") or line.startswith("public import "):
                    imps.append(line.split()[-1])
            imports[m] = imps

    closure, dq = set(), deque(args.targets)
    while dq:
        m = dq.popleft()
        if m in closure:
            continue
        closure.add(m)
        for i in imports.get(m, []):
            if i not in closure and i in mods:
                dq.append(i)

    times = {}
    if args.times:
        for line in open(args.times, encoding="utf-8"):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    times[parts[0]] = {
                        "max": float(parts[1]),
                        "median": float(parts[2]),
                        "n": int(parts[3]),
                    }
                except ValueError:
                    pass
            elif len(parts) == 2:
                try:
                    v = float(parts[1])
                    times[parts[0]] = {"max": v, "median": v, "n": 1}
                except ValueError:
                    pass
    stat = args.time_stat
    vals = sorted(t[stat] for t in times.values() if stat in t) or [6.0]
    fallback = vals[len(vals) // 2]

    def tv(m):
        return times.get(m, {}).get(stat, fallback)

    def tpath(m):
        return os.path.join(lib, m.replace(".", "/") + ".trace")

    def opath(m):
        return os.path.join(lib, m.replace(".", "/") + ".olean")

    def mt(p):
        try:
            return os.path.getmtime(p)
        except OSError:
            return 0.0

    missing, no_trace, stale_src, stale_dep = [], [], [], []
    for m in closure:
        if not os.path.exists(opath(m)):
            missing.append(m)
            continue
        tr = tpath(m)
        if not os.path.exists(tr):
            no_trace.append(m)
            continue
        t = os.path.getmtime(tr)
        if mt(mods[m]) > t:
            stale_src.append(m)
            continue
        if any(mt(opath(i)) > t for i in imports.get(m, []) if i in mods):
            stale_dep.append(m)

    must = set(missing) | set(no_trace) | set(stale_src) | set(stale_dep)
    clean = closure - must
    jobs = len(closure) * args.jobs_per_module

    # critical path over the closure (must-build get full time, clean ~0.2s)
    t = {m: tv(m) if m in must else 0.2 for m in closure}
    indeg = {m: 0 for m in closure}
    adj = {m: [] for m in closure}
    for m in closure:
        for d in imports.get(m, []):
            if d in closure:
                adj[d].append(m)
                indeg[m] += 1
    q = deque([m for m in closure if indeg[m] == 0])
    dp = dict(t)
    while q:
        m = q.popleft()
        for c in adj[m]:
            if dp[m] + t[c] > dp[c]:
                dp[c] = dp[m] + t[c]
            indeg[c] -= 1
            if indeg[c] == 0:
                q.append(c)
    cp = dp.get("Main", max(dp.values()) if dp else 0.0)
    total = sum(t[m] for m in must)

    compile_jobs = args.jobs_per_module * len(must)
    replay_jobs = max(0.0, jobs - compile_jobs)
    compile_wall = total / max(1, args.parallel)
    job_wall = replay_jobs / max(1.0, args.jobs_per_min) * 60.0
    wall = max(cp, compile_wall) + job_wall

    out = {
        "closure_modules": len(closure),
        "jobs_estimate": round(jobs),
        "must_build": len(must),
        "known_clean": len(clean),
        "missing_olean": len(missing),
        "no_trace": len(no_trace),
        "stale_source": len(stale_src),
        "stale_deps": len(stale_dep),
        "time_stat": stat,
        "compile_time_sum_s": round(total),
        "critical_path_s": round(cp),
        "compile_wall_s": round(compile_wall),
        "compile_jobs": round(compile_jobs),
        "replay_jobs": round(replay_jobs),
        "job_wall_s": round(job_wall),
        "wall_clock_estimate_s": round(wall),
        "wall_clock_estimate_min": round(wall / 60, 1),
        "parallel_assumed": args.parallel,
        "jobs_per_min_assumed": args.jobs_per_min,
    }
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"targets            {args.targets}")
        for k, v in out.items():
            print(f"{k:24s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
