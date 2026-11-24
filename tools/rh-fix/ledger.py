#!/usr/bin/env python3
"""Content-hash validation ledger.

A module is "known clean" at the current tip only if its source blob and its
direct project imports' blobs match the ones recorded when it was validated.
This avoids the false invalidation caused by unrelated files moving.

Usage:
  ledger.py build --repo PATH --sha SHA --validated FILE --out ledger.json
  ledger.py check --repo PATH --tip SHA --ledger ledger.json [--json]
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

IMPORT = re.compile(r"^(?:public\s+)?import\s+(\S+)")


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def blob(repo, sha, path):
    p = git(repo, "rev-parse", f"{sha}:{path}")
    return p.stdout.strip() if p.returncode == 0 else ""


def module_path(module):
    return "src/" + module.replace(".", "/") + ".lean"


def project_imports(repo, sha, module):
    """Direct imports that exist as project files at `sha` (Mathlib is skipped)."""
    p = git(repo, "show", f"{sha}:{module_path(module)}")
    if p.returncode != 0:
        return {}
    out = {}
    for line in p.stdout.splitlines():
        m = IMPORT.match(line)
        if not m:
            continue
        dep = m.group(1)
        b = blob(repo, sha, module_path(dep))
        if b:
            out[dep] = b
    return out


def build(repo, sha, modules):
    entries = {}
    for mod in modules:
        src = blob(repo, sha, module_path(mod))
        if not src:
            continue
        deps = project_imports(repo, sha, mod)
        dep_hash = hashlib.sha256(
            "\n".join(f"{k}:{v}" for k, v in sorted(deps.items())).encode()
        ).hexdigest()
        entries[mod] = {"source": src, "deps": dep_hash, "imports": deps}
    return {"sha": sha, "modules": entries}


def is_clean(repo, tip, ledger, module):
    e = ledger["modules"].get(module)
    if not e:
        return False
    if blob(repo, tip, module_path(module)) != e["source"]:
        return False
    cur = project_imports(repo, tip, module)
    cur_hash = hashlib.sha256(
        "\n".join(f"{k}:{v}" for k, v in sorted(cur.items())).encode()
    ).hexdigest()
    return cur_hash == e["deps"]


def load_validated(path):
    mods = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"OK (\S+)", line)
        if m:
            mods.append(m.group(1))
    return mods


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--repo", required=True)
    b.add_argument("--sha", required=True)
    b.add_argument("--validated", required=True)
    b.add_argument("--out", required=True)

    c = sub.add_parser("check")
    c.add_argument("--repo", required=True)
    c.add_argument("--tip", required=True)
    c.add_argument("--ledger", required=True)
    c.add_argument("--json", action="store_true")

    args = ap.parse_args()

    if args.cmd == "build":
        mods = load_validated(args.validated)
        led = build(args.repo, args.sha, mods)
        json.dump(led, open(args.out, "w"), indent=1)
        print(f"ledger: {len(led['modules'])} modules at {args.sha[:10]}")
        return 0

    led = json.load(open(args.ledger))
    clean, changed = [], []
    for mod in led["modules"]:
        (clean if is_clean(args.repo, args.tip, led, mod) else changed).append(mod)
    if args.json:
        json.dump({"clean": clean, "changed": changed}, sys.stdout, indent=1)
    else:
        print(f"clean={len(clean)} changed={len(changed)} at {args.tip[:10]}")
        for m in changed:
            print("CHANGED", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
