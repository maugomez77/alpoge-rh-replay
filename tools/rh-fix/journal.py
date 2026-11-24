#!/usr/bin/env python3
"""Append/read the event journal (local; sync.sh publishes it)."""
import argparse
import datetime
import os
import sys

DEFAULT = os.path.expanduser("~/.rh-fix/JOURNAL.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append")
    a.add_argument("text", nargs="+")
    s = sub.add_parser("show")
    s.add_argument("-n", type=int, default=20)
    args = ap.parse_args()

    if args.cmd == "append":
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        line = f"- {ts} " + " ".join(args.text) + "\n"
        with open(args.file, "a", encoding="utf-8") as f:
            f.write(line)
        print(line.strip())
    else:
        if os.path.exists(args.file):
            print("".join(open(args.file, encoding="utf-8").readlines()[-args.n:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
