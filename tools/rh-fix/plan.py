#!/usr/bin/env python3
"""Beforehand estimate for a Lake target: modules, jobs, must-build set, time.

Uses:
  - import-graph closure (exact module count)
  - Lake .trace files (source/import mtimes -> staleness)
  - per-module compile stats (max/median/count) from times-extract.py
  - optional live-log cost model: weighted progress + ETA interval

Usage:
  plan.py --repo PATH [--targets Main Challenge] [--times times-rich.txt]
          [--time-stat median|max] [--jobs-per-module 4]
          [--parallel 12] [--jobs-per-min 900] [--log BUILD.log] [--json]

Refresh the history first (inside the container):
  times-extract.py            # /work/*.log -> ~/.rh-fix/build-costs.json
"""
import argparse
import json
import os
import re
import sys
from collections import deque
from datetime import datetime, timezone

DEFAULT_TARGETS = ["Main", "Challenge"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/work/rh120"))
    ap.add_argument("--targets", nargs="+", default=DEFAULT_TARGETS)
    ap.add_argument("--times", default=None)
    ap.add_argument("--time-stat", choices=["median", "max"], default="median")
    ap.add_argument("--jobs-per-module", type=float, default=4.0)
    ap.add_argument("--elab-only", action="store_true",
                    help="intermediate check mode: 2 jobs/module (olean+ilean), no IR/C")
    ap.add_argument("--parallel", type=int, default=12)
    ap.add_argument("--jobs-per-min", type=float, default=1000.0,
                    help="Lake job processing rate (replays + compiles)")
    ap.add_argument("--log", default=None,
                    help="live build log: add cost-weighted progress and ETA")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.elab_only:
        args.jobs_per_module = 2.0

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

    log_info = {}
    if args.log and os.path.exists(args.log):
        done = {}
        job_index = (0, 0)
        start = None
        with open(args.log, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                mi = re.search(r"\[(\d+)/(\d+)\]", line)
                if mi:
                    job_index = (int(mi.group(1)), int(mi.group(2)))
                mb = re.search(r"Built (\S+) \(([\d.]+)s\)", line)
                if mb:
                    done[mb.group(1)] = float(mb.group(2))
                ms = re.match(r"start=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", line)
                if ms:
                    start = ms.group(1)

        weight_total = 0.0
        weight_done = 0.0
        weight_remaining_max = 0.0
        for m in closure:
            if m in done:
                w = done[m]
                weight_done += w
            else:
                w = tv(m) if m in must else 0.2
                if m in must:
                    weight_remaining_max += times.get(m, {}).get("max", fallback)
                else:
                    weight_remaining_max += 0.2
            weight_total += w

        elapsed = None
        if start:
            try:
                t0 = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
            except ValueError:
                elapsed = None
        throughput = (weight_done / elapsed) if elapsed and elapsed > 0 else 0.0
        remaining = max(0.0, weight_total - weight_done)
        eta_median = remaining / throughput if throughput > 0 else None
        eta_max = weight_remaining_max / throughput if throughput > 0 else None

        log_info = {
            "log": args.log,
            "log_jobs_done": job_index[0],
            "log_jobs_total": job_index[1],
            "log_modules_seen": len(done),
            "cost_weight_done_s": round(weight_done),
            "cost_weight_total_s": round(weight_total),
            "cost_weight_remaining_s": round(remaining),
            "cost_weighted_progress_pct": round(100.0 * weight_done / weight_total, 1) if weight_total else None,
            "elapsed_s": round(elapsed) if elapsed is not None else None,
            "throughput_cost_per_s": round(throughput, 2) if throughput else None,
            "eta_median_s": round(eta_median) if eta_median is not None else None,
            "eta_median_min": round(eta_median / 60, 1) if eta_median is not None else None,
            "eta_pessimistic_min": round(eta_max / 60, 1) if eta_max is not None else None,
            "eta_source": "log cost model (historical medians/max)",
        }

    compile_jobs = args.jobs_per_module * len(must)
    replay_jobs = max(0.0, jobs - compile_jobs)
    compile_wall = total / max(1, args.parallel)
    job_wall = replay_jobs / max(1.0, args.jobs_per_min) * 60.0
    wall = max(cp, compile_wall) + job_wall

    out = {
        "closure_modules": len(closure),
        "jobs_estimate": round(jobs),
        "facet_mode": "elabArts (no IR/C)" if args.elab_only else "default (irArts)",
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
    out.update(log_info)
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"targets            {args.targets}")
        for k, v in out.items():
            print(f"{k:24s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
