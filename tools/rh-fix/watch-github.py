#!/usr/bin/env python3
"""Cheap repo-wide GitHub watcher (port of roy7's gh-watch.sh for macOS).

Instead of polling each PR, this makes one repo-wide `issues/comments?since=`
call (plus `pulls/comments`) per repo per round and filters locally to the
threads we care about: every issue/PR we opened, plus a small explicit list.

Events (one round, exits on the first new activity with the FULL text):
  - new conversation or inline review comment by someone else on a watched thread
  - state change (merged/closed/reopened) or review by someone else on our PRs
  - one of our open PRs starting to conflict (doesn't bump updatedAt)
  - a new commit touching a `owner/repo:path` entry in watch-files.txt

Config files (under ~/.rh-fix by default):
  watch-repos.txt    "owner/repo [own|threads]"  (own = all issues/PRs we created)
  watch-threads.txt  "owner/repo N [note]" or "owner/repo#N"
  watch-files.txt    "owner/repo:path"

Usage:
  watch-github.py --once [--since ISO]     # one round, for testing / cron
  watch-github.py                          # loop until an event, then exit 0
  watch-github.py --interval 180 --rounds 60

Exit: 0 on event or clean stop; 2 on config/API error.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
CFG = os.path.join(HOME, ".rh-fix")
ISO = "%Y-%m-%dT%H:%M:%SZ"


def now():
    return datetime.now(timezone.utc)


def gh(*args, check=True):
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if p.returncode != 0:
        if check:
            raise RuntimeError(f"gh {' '.join(args[:3])}: {p.stderr.strip()[:300]}")
        return None
    return p.stdout.strip()


def gh_json(*args):
    out = gh(*args, check=False)
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def api_pages(path):
    """GET all pages of a REST list endpoint (100/page)."""
    out, page = [], 1
    sep = "&" if "?" in path else "?"
    while True:
        data = gh_json("api", f"{path}{sep}per_page=100&page={page}")
        if not isinstance(data, list):
            return out
        out.extend(data)
        if len(data) < 100:
            return out
        page += 1


def graphql(query, variables):
    args = ["api", "graphql"]
    for k, v in variables.items():
        args += ["-f", f"{k}={v}"]
    args += ["-f", f"query={query}"]
    data = gh_json(*args)
    if not data:
        return []
    return ((data.get("data") or {}).get("search") or {}).get("nodes") or []


PR_QUERY = """
query($q: String!) { search(query: $q, type: ISSUE, first: 100) {
  nodes { ... on PullRequest { number state mergeable
    repository { nameWithOwner }
    reviews(last: 20) { nodes { author { login } state submittedAt body } } } } } }
"""


def read_lines(name):
    path = os.path.join(CFG, name)
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def load_config(args):
    me = args.me or gh("api", "user", "--jq", ".login")
    repos = {}  # repo -> "own" | "threads"
    cfg_repos = args.repos.split() if args.repos else read_lines("watch-repos.txt")
    for line in cfg_repos:
        parts = line.split()
        if len(parts) == 1:
            repos[parts[0]] = "own"
        else:
            repos[parts[0]] = parts[1]
    threads = {}  # "owner/repo#N" -> note
    for line in read_lines("watch-threads.txt"):
        if "#" in line and " " not in line:
            key = line
        else:
            parts = line.split(None, 2)
            key = f"{parts[0]}#{parts[1]}"
        threads[key] = "listed"
        repo = key.rsplit("#", 1)[0]
        repos.setdefault(repo, "threads")
    files = read_lines("watch-files.txt")
    return me, repos, threads, files


def watched_threads(me, repos, threads):
    watch = dict(threads)
    for repo, mode in repos.items():
        if mode != "own":
            continue
        for it in api_pages(f"repos/{repo}/issues?creator={me}&state=all"):
            watch.setdefault(f"{repo}#{it['number']}", "ours")
    return watch


def pr_baseline(me, repos):
    states, merges = {}, {}
    q = f"author:{me} is:pr updated:>={ (now() - timedelta(days=30)).strftime('%Y-%m-%d') }" + "".join(
        f" repo:{r}" for r in repos
    )
    for pr in graphql(PR_QUERY, {"q": q}):
        key = f"{pr['repository']['nameWithOwner']}#{pr['number']}"
        states[key] = pr["state"]
        if pr["state"] == "OPEN":
            merges[key] = pr["mergeable"]
    return states, merges


def print_comment(repo, num, kind, user, when, body, extra=""):
    return f"--- {repo}#{num} [{kind}{extra}] {user} {when}\n{body}\n"


def is_bot(user):
    return user.get("type") == "Bot" or str(user.get("login", "")).endswith("[bot]")


def comment_event(c, since, seen):
    """Classify a comment as new / edited / none.

    New:    created_at > since
    Edited: created_at <= since < updated_at (the repo-wide since= query
            already returns edited comments; no extra API call).
    Returns (kind, token) or None.
    """
    created = c.get("created_at", "")
    updated = c.get("updated_at") or created
    if created > since:
        token = c["id"]
        return ("comment", token) if token not in seen else None
    if updated > since:
        token = f"{c['id']}@{updated}"
        return ("edited comment", token) if token not in seen else None
    return None


def round_once(ctx, since_dt, seen):
    me, repos, watch = ctx["me"], ctx["repos"], ctx["watch"]
    since = since_dt.strftime(ISO)
    # Query with a 60s overlap for indexing lag, but never rewind the saved
    # cursor: comments older than the cursor are deduped by `seen`.
    q_since = (since_dt - timedelta(seconds=60)).strftime(ISO)
    events = []
    new_ids = set()

    for repo in repos:
        nums = {k.rsplit("#", 1)[1] for k in watch if k.rsplit("#", 1)[0] == repo}
        if not nums:
            continue
        # conversation comments (new + edits to older comments)
        for c in api_pages(f"repos/{repo}/issues/comments?since={q_since}"):
            u = c["user"]
            if u["login"] == me or is_bot(u):
                continue
            num = c["issue_url"].rsplit("/", 1)[-1]
            if num not in nums:
                continue
            ev = comment_event(c, q_since, seen)
            if not ev:
                continue
            kind, token = ev
            new_ids.add(token)
            when = c["updated_at"] if kind.startswith("edited") else c["created_at"]
            events.append(print_comment(repo, num, kind, u["login"], when, c["body"]))
        # inline review comments (new + edits)
        for c in api_pages(f"repos/{repo}/pulls/comments?since={q_since}"):
            u = c["user"]
            if u["login"] == me or is_bot(u):
                continue
            num = c["pull_request_url"].rsplit("/", 1)[-1]
            if num not in nums:
                continue
            ev = comment_event(c, q_since, seen)
            if not ev:
                continue
            kind, token = ev
            new_ids.add(token)
            when = c["updated_at"] if kind.startswith("edited") else c["created_at"]
            ikind = "inline" if kind == "comment" else "edited inline"
            loc = f"{c.get('path', '?')}:{c.get('line') or c.get('original_line') or '?'}"
            events.append(print_comment(repo, num, ikind, u["login"], when, c["body"], f" {loc}"))

    repos_q = "".join(f" repo:{r}" for r in repos)

    # our PRs touched since the cursor: state changes + reviews by others
    q = f"author:{me} is:pr updated:>={since[:19]}{repos_q}"
    for pr in graphql(PR_QUERY, {"q": q}):
        key = f"{pr['repository']['nameWithOwner']}#{pr['number']}"
        old = ctx["states"].get(key)
        if old is not None and old != pr["state"]:
            events.append(f"--- our PR {key} state: {old} -> {pr['state']}\n")
        elif old is None and pr["state"] != "OPEN":
            events.append(f"--- our PR {key} state: {pr['state']}\n")
        for rv in pr["reviews"]["nodes"]:
            if rv["submittedAt"] > since and rv["author"]["login"] != me:
                events.append(
                    f"--- our PR {key} [review {rv['state']}] {rv['author']['login']} {rv['submittedAt']}\n{rv['body']}\n"
                )

    # merge conflicts on our open PRs (does not bump updatedAt)
    q = f"author:{me} is:pr is:open{repos_q}"
    for pr in graphql(PR_QUERY, {"q": q}):
        key = f"{pr['repository']['nameWithOwner']}#{pr['number']}"
        if pr["mergeable"] == "CONFLICTING" and ctx["merges"].get(key) != "CONFLICTING":
            events.append(f"--- our PR {key} now has merge conflicts (was {ctx['merges'].get(key, 'new')})\n")
        ctx["merges"][key] = pr["mergeable"]

    # watched files: new commit sha
    for spec in ctx["files"]:
        repo, path = spec.split(":", 1)
        data = gh_json("api", f"repos/{repo}/commits?path={path}&per_page=1")
        if isinstance(data, list) and data:
            sha = data[0]["sha"]
            msg = data[0]["commit"]["message"].splitlines()[0]
            old = ctx["files_sha"].get(spec)
            if old and old != sha:
                events.append(f"--- {spec} updated: {sha[:10]} {msg}\n")
            ctx["files_sha"][spec] = sha

    return events, new_ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--me", default=None)
    ap.add_argument("--repos", default=None, help="space-separated owner/repo list (overrides file)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--since", default=None, help="test mode: look back to this ISO time")
    ap.add_argument("--interval", type=int, default=180)
    ap.add_argument("--rounds", type=int, default=60)
    ap.add_argument("--state", default=os.path.join(CFG, "watch-state.json"))
    args = ap.parse_args()

    try:
        me, repos, threads, files = load_config(args)
    except Exception as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    state = {}
    if os.path.exists(args.state):
        try:
            state = json.load(open(args.state))
        except Exception:
            state = {}
    if args.since:
        since_dt = datetime.strptime(args.since, ISO).replace(tzinfo=timezone.utc)
    elif state.get("since"):
        since_dt = datetime.strptime(state["since"], ISO).replace(tzinfo=timezone.utc)
    else:
        since_dt = now()  # fresh watcher: only future events
    seen = set(state.get("seen", []))

    try:
        watch = watched_threads(me, repos, threads)
        states, merges = pr_baseline(me, repos)
    except Exception as e:
        print(f"startup error: {e}", file=sys.stderr)
        return 2
    ctx = {"me": me, "repos": repos, "watch": watch, "states": states, "merges": merges,
           "files": files, "files_sha": {}}

    print(f"repos: {' '.join(repos)}", file=sys.stderr)
    print(f"watching {len(watch)} threads since {since_dt.strftime(ISO)}", file=sys.stderr)

    for _ in range(args.rounds):
        round_start = now()
        try:
            events, new_ids = round_once(ctx, since_dt, seen)
        except Exception as e:
            print(f"round error: {e}", file=sys.stderr)
            return 2

        if events:
            print(f"EVENT at {now().strftime('%H:%M:%S')}")
            print("".join(events), end="")
            seen |= new_ids
            state = {"since": round_start.strftime(ISO), "seen": list(seen)[-2000:]}
            os.makedirs(os.path.dirname(args.state), exist_ok=True)
            json.dump(state, open(args.state, "w"))
            return 0

        # advance the persisted cursor to the round start; the 60s overlap
        # is applied only to the API query, never to the saved cursor
        since_dt = round_start
        state = {"since": round_start.strftime(ISO), "seen": list(seen)[-2000:]}
        json.dump(state, open(args.state, "w"))
        if args.once:
            print("no events", file=sys.stderr)
            return 0
        if _ < args.rounds - 1:
            import time

            time.sleep(args.interval)

    print("no events this run", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
