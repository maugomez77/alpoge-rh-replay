#!/usr/bin/env python3
"""Reverse-dependency closure of changed Lean modules.

Given what changed, print the set of modules whose `.olean` may be invalidated:
the changed modules plus every module that transitively imports them.

This is the "delta-green" unit: building the closure verifies every affected
consumer without paying for unrelated branches of the tree.  Lake's own traces
already prune unchanged work, but the closure gives you a *bounded target* and a
coverage number you can put in a receipt.

Usage:
  import-closure.py --src src --changed origin/main
  import-closure.py --src src --changed <base> --json --out /tmp/closure.json
  import-closure.py --src src --modules Foo.Bar Baz.Qux --json

Exit codes: 0 ok, 2 usage/IO, 3 "full rebuild required" (config changed / `import all`).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

IMPORT_RE = re.compile(r"(?m)^\s*(?:public\s+|private\s+|meta\s+)*import\s+([A-Za-z0-9_.]+)")
IMPORT_ALL_RE = re.compile(r"(?m)^\s*(?:public\s+|private\s+|meta\s+)*import\s+all\b")
CONFIG_FILES = {"lakefile.toml", "lakefile.lean", "lean-toolchain", "lake-manifest.json"}


def module_of(path: Path, src: Path) -> str | None:
    try:
        rel = path.relative_to(src)
    except ValueError:
        return None
    if rel.suffix != ".lean":
        return None
    return str(rel.with_suffix("")).replace("/", ".")


def build_graph(src: Path) -> tuple[dict[str, set[str]], dict[str, set[str]], set[str]]:
    fwd: dict[str, set[str]] = {}
    all_importers: set[str] = set()
    for p in src.rglob("*.lean"):
        mod = module_of(p, src)
        if mod is None:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if IMPORT_ALL_RE.search(text):
            all_importers.add(mod)
        fwd[mod] = set(IMPORT_RE.findall(text))
    rev: dict[str, set[str]] = defaultdict(set)
    for m, imps in fwd.items():
        for i in imps:
            if i in fwd:
                rev[i].add(m)
    return fwd, rev, all_importers


def changed_paths(base: str, head: str | None = None) -> list[str]:
    cmd = ["git", "diff", "--name-only", "--diff-filter=ACMRD", base]
    if head:
        cmd.append(head)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        print(f"error: git diff failed: {e}", file=sys.stderr)
        sys.exit(2)
    return [l for l in out.splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="src")
    ap.add_argument("--changed", metavar="BASE", default=None, help="git base to diff against")
    ap.add_argument("--head", metavar="REV", default=None, help="optional head revision (default: working tree)")
    ap.add_argument("--modules", nargs="*", default=None, help="explicit module names")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None, help="write the module list (one per line)")
    ap.add_argument("--explain", action="store_true", help="show the biggest hubs in the closure")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.is_dir():
        print(f"error: {src} is not a directory", file=sys.stderr)
        return 2

    full_reasons: list[str] = []
    changed_modules: set[str] = set()

    if args.modules:
        changed_modules = set(args.modules)
    elif args.changed:
        paths = changed_paths(args.changed, args.head)
        for p in paths:
            if Path(p).name in CONFIG_FILES:
                full_reasons.append(f"config changed: {p}")
                continue
            if not p.endswith(".lean"):
                continue
            mod = module_of(Path(p), src)
            if mod:
                changed_modules.add(mod)
    else:
        print("error: pass --changed BASE or --modules ...", file=sys.stderr)
        return 2

    fwd, rev, all_importers = build_graph(src)

    # BFS over reverse edges.  A module with `import all` depends on the whole
    # package, so any change invalidates it: seed it as a root (cheap, exact).
    closure: set[str] = set()
    q = deque(sorted(changed_modules | all_importers))
    while q:
        m = q.popleft()
        if m in closure:
            continue
        closure.add(m)
        for parent in rev.get(m, ()):
            if parent not in closure:
                q.append(parent)

    total = len(fwd)
    coverage = (len(closure) / total) if total else 0.0
    data = {
        "changed": sorted(changed_modules),
        "closure": sorted(closure),
        "closure_size": len(closure),
        "total_modules": total,
        "coverage": round(coverage, 4),
        "full_rebuild_reasons": full_reasons,
        "import_all_files": sorted(all_importers),
        "requires_full": bool(full_reasons),
    }

    if args.explain:
        hub = sorted(((len(rev.get(m, ())), m) for m in closure), reverse=True)[:15]
        data["hubs"] = [{"module": m, "importers": n} for n, m in hub]

    if args.out:
        Path(args.out).write_text("\n".join(sorted(closure)) + "\n", encoding="utf-8")
        print(f"wrote {len(closure)} modules to {args.out}", file=sys.stderr)

    if args.json:
        print(json.dumps(data, indent=1))
    else:
        print(f"changed modules: {len(changed_modules)}")
        print(f"closure: {len(closure)} / {total} modules ({coverage:.1%})")
        if full_reasons:
            print("FULL REBUILD REQUIRED:")
            for r in full_reasons:
                print(f"  - {r}")
        if all_importers:
            print(f"note: {len(all_importers)} file(s) use `import all`; seeded as closure roots")
        if args.explain:
            print("top hubs:")
            for n, m in sorted(((len(rev.get(m, ())), m) for m in closure), reverse=True)[:15]:
                print(f"  {n:5d} importers  {m}")
        for m in sorted(closure)[:20]:
            print(f"  {m}")
        if len(closure) > 20:
            print(f"  ... and {len(closure) - 20} more")

    if full_reasons:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
