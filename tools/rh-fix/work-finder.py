#!/usr/bin/env python3
"""Work-finder: scan the live PR120 board (and optionally a build log) for small,
unclaimed fixes, split into an M4 lane (build + fix) and a mini lane (triage).

Modes:
  --once            print the queue and exit
  (default)         poll every --interval seconds; exit when the queue changes

The queue signature excludes ordering, so a new claim/row triggers an event.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import ledger as ledger_mod
except Exception:
    ledger_mod = None

BOARD_REPO = "rohanarun/alpoge-rh-replay"
BOARD_PATH = "PR120-BUGS.md"
TIP_REPO = "/Volumes/Storage/Riemmann/rh120"
BRANCH = "refs/heads/opt/collapse-and-consolidate-4.36"

ROW = re.compile(r"^\| `([^`]+?\.lean):(\d+)` \| ([^|]*) \| (.*?) \| (.*?) \|$")

MECHANICAL = {"ambiguous name", "unknown constant", "wrong name resolved (likely collision)"}


def gh(*args):
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""


def board_text(path):
    if path:
        return open(path, encoding="utf-8").read()
    import base64

    raw = gh("api", f"repos/{BOARD_REPO}/contents/{BOARD_PATH}", "--jq", ".content")
    return base64.b64decode(raw).decode("utf-8", "ignore") if raw.strip() else ""


def current_tip(repo):
    subprocess.run(
        ["git", "-C", repo, "fetch", "-q", "origin", "opt/collapse-and-consolidate-4.36"],
        capture_output=True, text=True,
    )
    out = subprocess.run(
        ["git", "-C", repo, "rev-parse", "origin/opt/collapse-and-consolidate-4.36"],
        capture_output=True, text=True,
    ).stdout.strip()
    return out


def parse(text):
    head = updated = compiled = ""
    m = re.search(r"head `([0-9a-f]+)`", text)
    if m:
        head = m.group(1)
    m = re.search(r"Updated ([0-9-]+ [0-9:]+ UTC)", text)
    if m:
        updated = m.group(1)
    m = re.search(r"\*\*Compiled: ([^*]+)\*\*", text)
    if m:
        compiled = m.group(1).strip()

    rows = []
    for line in text.splitlines():
        m = ROW.match(line.strip())
        if not m:
            continue
        path, lineno, cls, msg, notes = m.groups()
        claimed = bool(re.search(r"claimed:|fix exists", notes, re.I))
        rows.append({
            "path": path, "line": int(lineno),
            "class": cls.strip(), "msg": msg.strip(),
            "notes": notes.strip(), "claimed": claimed,
        })
    return head, updated, compiled, rows


def tip_age(repo, tip):
    out = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%ct", tip],
                         capture_output=True, text=True).stdout.strip()
    try:
        return time.time() - int(out)
    except ValueError:
        return 0.0


def load_times(path):
    t = {}
    for line in open(path, encoding="utf-8"):
        parts = line.split()
        if len(parts) == 2:
            try:
                t[parts[0]] = float(parts[1])
            except ValueError:
                pass
        elif len(parts) >= 4:
            try:
                t[parts[0]] = float(parts[2])  # median
            except ValueError:
                pass
    return t


def load_claims(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}


def parse_log(path):
    """Rows from a `grep '^error: src'` extract of a build log."""
    out = []
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = re.match(r"^error: src/(.+?\.lean):(\d+):\d+: (.*)", line)
        if m:
            out.append({
                "path": m.group(1), "line": int(m.group(2)),
                "class": "build", "msg": m.group(3).strip(),
                "notes": "", "claimed": False, "verify": True,
            })
    return out


def queue(rows, claims=None, times=None):
    by_mod = {}
    for r in rows:
        by_mod.setdefault(r["path"], []).append(r)
    items = []
    for path, rs in by_mod.items():
        module = path[:-5].replace("/", ".")
        claimed = any(r["claimed"] for r in rs) or module in (claims or {})
        verify = any(r.get("verify") for r in rs)
        est = (times or {}).get(module)
        classes = [r["class"] for r in rs]
        cls = next((c for c in classes if c in MECHANICAL), classes[0] if classes else "other")
        n = len(rs)
        score = (3 if cls in MECHANICAL else 2 if cls == "instance" else 1) + (4 - min(n, 3))
        first = rs[0]
        lane = "m4" if (not claimed and not verify and n <= 2
                        and (cls in MECHANICAL | {"instance"} or cls == "build")) else "mini"
        items.append({
            "key": f"{path}:{first['line']}",
            "path": path, "line": first["line"], "errors": n,
            "class": cls, "claimed": claimed, "verify": verify, "lane": lane,
            "score": score, "msg": first["msg"], "est": est,
        })
    items.sort(key=lambda i: (-i["score"], i["est"] if i["est"] is not None else 1e9, i["path"]))
    return items


def render(items, head, tip, updated, compiled):
    stale = bool(head and tip and not tip.startswith(head[:8]))
    out = [
        "# Work queue — " + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        f"board head `{head[:10]}` · tip `{tip[:10]}` · stale={stale} · updated {updated}",
        f"compiled: {compiled}",
        "",
    ]
    for lane, title in (("m4", "M4 — build & fix"), ("mini", "mini — triage (static analysis)")):
        sel = [i for i in items if i["lane"] == lane]
        out.append(f"## {title} ({len(sel)})")
        if not sel:
            out.append("_none_")
        for i in sel:
            tag = "VERIFY" if i["verify"] else ("CLAIMED" if i["claimed"] else "free")
            out.append(
                f"- `{i['path']}:{i['line']}` — {i['errors']} error(s) — {i['class']} — "
                f"{tag} — score {i['score']}"
                + (f" — ~{i['est']:.0f}s" if i.get("est") is not None else "")
            )
        out.append("")
    return stale, "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--board", default=None, help="local board markdown (default: GitHub)")
    ap.add_argument("--interval", type=int, default=300)
    ap.add_argument("--rounds", type=int, default=288)
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", TIP_REPO),
                    help="path to the riemann-hypothesis checkout")
    ap.add_argument("--state", default=os.path.expanduser("~/.rh-fix/work-state.json"))
    ap.add_argument("--validated", default=None,
                    help="file with 'OK Module' lines from a previous build (known-clean)")
    ap.add_argument("--validated-sha", default=None,
                    help="SHA at which those OK lines were produced")
    ap.add_argument("--stable-for", type=int, default=0,
                    help="only report when the tip commit is at least this many seconds old")
    ap.add_argument("--times", default=None, help="module<TAB>seconds historical times")
    ap.add_argument("--claims", default=None, help="claims JSON: module -> {pr,...}")
    ap.add_argument("--ledger", default=None,
                    help="content-hash ledger JSON (preferred over --validated)")
    ap.add_argument("--build-log", default=None,
                    help="file of 'error: src/...' lines from a build log")
    ap.add_argument("--log-sha", default=None,
                    help="SHA of that build log (rows whose file changed since are marked VERIFY)")
    args = ap.parse_args()

    validated = set()
    if args.validated:
        for line in open(args.validated, encoding="utf-8"):
            m = re.match(r"OK (\S+)", line)
            if m:
                validated.add(m.group(1))

    state = {}
    if os.path.exists(args.state):
        try:
            state = json.load(open(args.state))
        except Exception:
            state = {}
    last_sig = state.get("sig", "")

    for rnd in range(args.rounds):
        text = board_text(args.board)
        if not text.strip():
            print("work-finder: empty board", file=sys.stderr)
            return 2
        head, updated, compiled, rows = parse(text)
        tip = current_tip(args.repo)
        stale = bool(head and tip and not tip.startswith(head[:8]))

        if args.stable_for and tip and tip_age(args.repo, tip) < args.stable_for:
            if args.once:
                print(f"tip not stable yet (age {int(tip_age(args.repo, tip))}s < {args.stable_for}s)")
                return 0
            if rnd < args.rounds - 1:
                time.sleep(args.interval)
            continue

        claims = load_claims(args.claims) if args.claims else {}
        times = load_times(args.times) if args.times else {}

        clean_ledger = set()
        if args.ledger and ledger_mod and tip:
            try:
                led = json.load(open(args.ledger, encoding="utf-8"))
                for mod in led.get("modules", {}):
                    if ledger_mod.is_clean(args.repo, tip, led, mod):
                        clean_ledger.add(mod)
            except Exception:
                pass

        if args.build_log:
            log_rows = parse_log(args.build_log)
            changed_log = set()
            if args.log_sha and tip:
                diff = subprocess.run(
                    ["git", "-C", args.repo, "diff", "--name-only",
                     f"{args.log_sha}..{tip}", "--", "src"],
                    capture_output=True, text=True,
                ).stdout
                changed_log = set(diff.splitlines())
            seen = {(r["path"], r["line"]) for r in rows}
            for r in log_rows:
                if (r["path"], r["line"]) in seen:
                    continue
                if args.log_sha:
                    r["verify"] = f"src/{r['path']}" in changed_log
                rows.append(r)
                seen.add((r["path"], r["line"]))

        changed = set()
        if validated and args.validated_sha and tip:
            diff = subprocess.run(
                ["git", "-C", args.repo, "diff", "--name-only",
                 f"{args.validated_sha}..{tip}", "--", "src"],
                capture_output=True, text=True,
            ).stdout
            changed = set(diff.splitlines())
        before = len(rows)
        if args.ledger:
            rows = [
                r for r in rows
                if r["path"][:-5].replace("/", ".") not in clean_ledger
            ]
        else:
            rows = [
                r for r in rows
                if not (r["path"][:-5].replace("/", ".") in validated
                        and f"src/{r['path']}" not in changed)
            ]
        excluded = before - len(rows)

        items = queue(rows, claims, times)
        _, body = render(items, head, tip, updated, compiled)
        if excluded:
            if args.ledger:
                body += f"\n_excluded {excluded} rows known clean by content-hash ledger._\n"
            else:
                body += f"\n_excluded {excluded} rows already validated clean at `{args.validated_sha[:10]}` and unchanged since._\n"
        # ignore the timestamp line so the signature only changes on real queue changes
        sig = hashlib.sha256("\n".join(
            f"{i['key']}|{i['lane']}|{i['claimed']}|{i['verify']}|{i['errors']}|{i['class']}"
            for i in items).encode()).hexdigest()

        if args.once:
            print(body)
            return 0
        if not last_sig and not args.once:
            # baseline on first run: record the current queue, don't fire
            json.dump({"sig": sig}, open(args.state, "w"))
            last_sig = sig
            if rnd < args.rounds - 1:
                time.sleep(args.interval)
            continue
        if sig != last_sig:
            print(f"EVENT at {datetime.now(timezone.utc).strftime('%H:%M:%S')}")
            print(body)
            json.dump({"sig": sig}, open(args.state, "w"))
            return 0
        if rnd < args.rounds - 1:
            time.sleep(args.interval)
    print("no queue change", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
