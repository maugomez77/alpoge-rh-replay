#!/usr/bin/env python3
"""Claim registry: module -> {pr, owner, note, at}."""
import argparse
import datetime
import json
import os
import sys

DEFAULT = os.path.expanduser("~/.rh-fix/claims.json")


def load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), indent=1, sort_keys=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("module")
    a.add_argument("--pr", default="")
    a.add_argument("--owner", default="")
    a.add_argument("--note", default="")
    r = sub.add_parser("remove")
    r.add_argument("module")
    sub.add_parser("list")
    args = ap.parse_args()

    data = load(args.file)
    if args.cmd == "add":
        data[args.module] = {
            "pr": args.pr, "owner": args.owner, "note": args.note,
            "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        save(args.file, data)
        print(f"claimed {args.module}" + (f" (PR {args.pr})" if args.pr else ""))
    elif args.cmd == "remove":
        data.pop(args.module, None)
        save(args.file, data)
        print(f"released {args.module}")
    else:
        for mod in sorted(data):
            e = data[mod]
            print(f"{mod}\t{e.get('pr','')}\t{e.get('owner','')}\t{e.get('at','')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
