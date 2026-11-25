#!/usr/bin/env python3
"""Pre-PR critic for RH module fixes.

Option A: deterministic checklist (scope, statements, escape hatches, claims,
base freshness, minimality, receipt, error-class match).
Option B: optional local LLM review (Ollama) over the error block + diff.

Usage:
  critic.py --repo PATH --module Development....Bundle0004 [--error err.txt]
            [--receipt RECEIPT.md] [--base origin/opt/...]
            [--llm auto|ollama|none] [--model llama3.2] [--json]

Exit: 0 = PASS/WARN, 1 = FAIL (blocking), 2 = setup error.
"""
import argparse
import json
import os
import re
import subprocess
import sys

STATEMENT = re.compile(r"^\s*(?:private\s+|protected\s+|noncomputable\s+)?(theorem|lemma|def|instance|abbrev|structure|class)\b")
FORBIDDEN = {
    "sorry": "proof hole",
    "admit": "proof hole",
    "axiom ": "new axiom",
    "native_decide": "trust change",
    "unsafe ": "unsafe declaration",
}
BUDGET = re.compile(r"set_option\s+(maxHeartbeats|synthInstance\.maxHeartbeats)")


def sh(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def diff_text(repo, base):
    return sh("git", "-C", repo, "diff", "-U0", f"{base}...HEAD").stdout


def classify_error(text):
    t = text.lower()
    if any(k in t for k in ("ambiguous term", "unknown identifier", "unknown constant", "wrong name", "function expected")):
        return "name/qualification"
    if "failed to synthesize" in t or "timeout at `typeclass`" in t or "synthinstance" in t:
        return "instance/timeout"
    if "rewrite" in t and ("did not find" in t or "failed" in t):
        return "rewrite/term"
    if "type mismatch" in t or "application type mismatch" in t:
        return "term/type"
    return "unknown"


def expected_hints(kind):
    return {
        "name/qualification": ["open ", "_root_.", "GlobalTheory.", "ReciprocityTheory.", "qualif", "namespace"],
        "instance/timeout": ["maxHeartbeats", "haveI", "inferInstance", "instSFinite", "Module.Free", "letI", "@"],
        "rewrite/term": ["rw ", "simp", "conv", "exact", "refine", "show "],
        "term/type": ["exact", "refine", "show", "have", "apply", "rw "],
        "unknown": [],
    }.get(kind, [])


def have(cmd):
    return bool(sh("bash", "-lc", f"command -v {cmd}").stdout.strip())


def llm_review(prompt, model, prefer):
    if prefer in ("auto", "grok") and have("grok"):
        try:
            p = subprocess.run(
                ["grok", "--single", prompt, "--permission-mode", "dontAsk",
                 "--output-format", "plain"],
                capture_output=True, text=True, timeout=240,
            )
            if p.returncode == 0 and p.stdout.strip():
                return "grok: " + p.stdout.strip()
        except Exception:
            pass
    if prefer in ("auto", "ollama") and have("ollama"):
        try:
            p = subprocess.run(["ollama", "run", model], input=prompt,
                               capture_output=True, text=True, timeout=180)
            if p.returncode == 0 and p.stdout.strip():
                return "ollama: " + p.stdout.strip()
        except Exception:
            pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("RH_REPO", "/Volumes/Storage/Riemmann/rh120"))
    ap.add_argument("--module", required=True, help="module name or src/ path")
    ap.add_argument("--error", default=None, help="file containing the error block")
    ap.add_argument("--receipt", default=None, help="preflight RECEIPT.md")
    ap.add_argument("--base", default="origin/opt/collapse-and-consolidate-4.36")
    ap.add_argument("--llm", choices=["auto", "grok", "ollama", "none"], default="auto")
    ap.add_argument("--model", default="llama3.2")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = args.repo
    module_path = args.module if args.module.endswith(".lean") else "src/" + args.module.replace(".", "/") + ".lean"
    base_sha = sh("git", "-C", repo, "merge-base", "HEAD", args.base).stdout.strip()
    if not base_sha:
        print(f"critic: cannot find merge-base with {args.base}", file=sys.stderr)
        return 2

    changed = sh("git", "-C", repo, "diff", "--name-only", f"{base_sha}..HEAD").stdout.splitlines()
    diff = diff_text(repo, base_sha)
    added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    stmts = [l for l in diff.splitlines() if l[:1] in "+-" and STATEMENT.match(l[1:])]

    checks = {}
    fails = []

    if module_path not in changed:
        fails.append(f"claimed module not in diff ({module_path})")
    checks["module_touched"] = module_path in changed

    if stmts:
        fails.append(f"{len(stmts)} statement line(s) changed")
    checks["statements_unchanged"] = not stmts

    found = []
    for tok, why in FORBIDDEN.items():
        if any(tok in l for l in added):
            found.append(f"{tok.strip()} ({why})")
    if found:
        fails.append("forbidden addition: " + ", ".join(found))
    checks["no_escape_hatches"] = not found

    budgets = [l for l in added if BUDGET.search(l)]
    checks["budget_bump"] = bool(budgets)

    # duplicate claims
    name = os.path.basename(module_path)[:-5]
    prs = gh("search", "prs", "--repo", "rohanarun/riemann-hypothesis", "--state", "open", name,
             "--json", "number,title")
    try:
        pr_list = json.loads(prs.stdout) if prs.stdout.strip() else []
    except Exception:
        pr_list = []
    checks["open_prs_same_module"] = [f"#{p['number']}" for p in pr_list]

    behind = sh("git", "-C", repo, "rev-list", "--count", f"HEAD..{args.base}").stdout.strip()
    checks["commits_behind_base"] = int(behind or 0)

    shortstat = sh("git", "-C", repo, "diff", "--shortstat", f"{base_sha}..HEAD").stdout.strip()
    checks["diff"] = shortstat

    err_kind = "unknown"
    if args.error and os.path.exists(args.error):
        err_kind = classify_error(open(args.error, encoding="utf-8", errors="ignore").read())
    checks["error_class"] = err_kind
    hints = expected_hints(err_kind)
    hint_hit = any(h.lower() in diff.lower() for h in hints) if hints else True
    checks["fix_matches_error_class"] = hint_hit
    if not hint_hit:
        fails.append(f"patch does not look like a {err_kind} fix")

    receipt_ok = None
    if args.receipt and os.path.exists(args.receipt):
        txt = open(args.receipt, encoding="utf-8", errors="ignore").read()
        receipt_ok = "result: PASS" in txt or "result: pass" in txt.lower()
        checks["receipt_pass"] = receipt_ok
        if not receipt_ok:
            fails.append("preflight receipt is not PASS")

    verdict = "FAIL" if fails else ("WARN" if (budgets or int(behind or 0) > 0 or checks["open_prs_same_module"]) else "PASS")

    llm = None
    if args.llm != "none":
        err_txt = ""
        if args.error and os.path.exists(args.error):
            err_txt = open(args.error, encoding="utf-8", errors="ignore").read()[:2000]
        prompt = f"""You are a strict Lean 4 pull-request critic. Review this fix.
Answer with VERDICT: APPROVE or WARN or REJECT, then 3 short bullets.

ERROR:
{err_txt}

CHECKLIST:
{json.dumps(checks, indent=1)}

DIFF (truncated):
{diff[:6000]}
"""
        try:
            llm = llm_review(prompt, args.model, args.llm)
        except Exception as e:
            llm = f"(llm review failed: {e})"

    out = {"module": args.module, "verdict": verdict, "fails": fails, "checks": checks, "llm": llm}
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"CRITIC {verdict} — {args.module}")
        if fails:
            print("blocking:")
            for f in fails:
                print("  -", f)
        print("checks:", json.dumps(checks, indent=1))
        if llm:
            print("\nLLM review:\n" + llm)
    return 1 if verdict == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
