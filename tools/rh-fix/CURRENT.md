# CURRENT — single source of truth

**Last updated:** 2026-11-25T06:15Z
**Repo:** `maugomez77/alpoge-rh-replay`, branch `tools/rh-fix`
**This file is the only one you need to read to resume.** Supporting detail:
`STATUS.md`, `HANDOFF.md`, `JOURNAL.md`, `README.md`, `NEXT-SESSION.md` (older).

## What this project is

Two parallel efforts:

1. **Riemann Hypothesis consolidation (PR #120)** — a 4.36 Lean branch that collapses
   93k modules into ~20k bundles. It is **closed temporarily** while the branch is
   repaired; work continues on `opt/collapse-and-consolidate-4.36`. Our role: independent
   full builds, fault-finding, small fixes, receipts.
2. **Formal Conjectures** — four PRs adding Erdős problem statuses/answers.

## Live state (at handoff)

| Item | Value |
|---|---|
| **Full build in flight** | `884075ed`, log `/work/mainbuild13.log` on the M4 |
| Progress | **84,597 / 114,021 jobs**, **6 errors / 1 module** (`ExistsIsHaarProbabilityMaxCompactHermitian`), still running |
| Branch tip | `94ff1f0fd0` (moving; was `22f1682e9f` at handoff) |
| Earlier milestone | `b9b24502` full build: **1 error / 1 module**, 3h00m; that module is fixed at the next tip |
| Trajectory | 96/27 → 67/16 → 133/20 → **1/1** |

**Important:** the full build stops at the first blocking module; “1 error” means the
frontier, not the whole tree. Fixing it reveals the next layer.

## Links

- RH PR: https://github.com/leanprover-community/riemann-hypothesis/pull/120
- Coordination: https://github.com/rohanarun/alpoge-rh-replay/issues/35028
- FC PRs: [#8214](https://github.com/google-deepmind/formal-conjectures/pull/8214) · [#8215](https://github.com/google-deepmind/formal-conjectures/pull/8215) · [#8219](https://github.com/google-deepmind/formal-conjectures/pull/8219) · [#8187](https://github.com/google-deepmind/formal-conjectures/pull/8187)

## Machines

- **M4** `maugomez77@mauricios-macbook-pro-1`, container `rhreplay`, repo `/work/rh120`
  (16 cores, 64 GB, Lean 4.36, warm `.lake`). Builder.
- **Mini** (this machine) — control plane: OpenCode, watchers, MCP bridge, logs.

## Tooling (all in `~/.rh-fix`, mirrored in this folder)

| Tool | Use |
|---|---|
| `supervise.sh start\|stop\|status\|daemon` | Manage GitHub watcher + work-finder |
| `work-finder.py` | Queue of small unclaimed fixes (ledger, times, claims, stability gate) |
| `plan.py [--elab-only]` | Beforehand estimate: closure, jobs, must-build, critical path, wall |
| `preflight.sh <Module>` | Receipt: scope, open scan, statements, importers, build log digest, axioms |
| `critic.py --module … --error …` | Deterministic checks + Grok CLI review before `gh pr ready` |
| `post-receipt.sh <Module> <PR>` | Post the preflight receipt once (marker-deduped) |
| `build-fast.sh [--check]` | Cache preflight + full build, or `:elabArts` intermediate check |
| `warm-cache.sh` | Try the repo's validated CI cache (exit 3 = none) |
| `stop-all.sh [--container]` | Stop watchers + M4 build/container |
| `lean-lsp-mcp-remote.sh` | stdio-over-SSH bridge to `lean-lsp-mcp` in the container |

**`lean-lsp` MCP** is configured in `~/.config/opencode/opencode.json` (local command
= the wrapper). It auto-starts `rhreplay`. Tools: `lean_goal`,
`lean_diagnostic_messages`, `lean_local_search` (ripgrep installed), `lean_loogle`,
`lean_leansearch`, `lean_multi_attempt`, `lean_profile_proof`, `lean_build`,
`lean_verify`. Restart OpenCode to reload it.

## Immediate next steps

1. Check `/work/mainbuild13.log` terminal state; extract the full failure list.
2. For each failing module at the latest tip: build-first → claim (draft PR) →
   fix → `preflight.sh` → `critic.py` → mark ready → post exact SHA/exit/first
   diagnostic to #35028.
3. FC: #8214/#8187 approved (need 2nd approval); #8215/#8219 re-review.
4. **No full builds during merge bursts**; wait for a quiet tip (10 min) or use
   `build-fast.sh --check` (`:elabArts`, no IR/C).

## Opening prompt for a new session

> Continue the Riemann Hypothesis 4.36 consolidation work. Read
> `tools/rh-fix/CURRENT.md` from `maugomez77/alpoge-rh-replay` (branch `tools/rh-fix`).
> The M4 (`maugomez77@mauricios-macbook-pro-1`, container `rhreplay`) is the builder.
> A full `Main Challenge` build was running at `884075ed` (log `/work/mainbuild13.log`)
> with 6 errors in 1 module; check its terminal state, then work the failing modules
> using build-first, a draft claim, `preflight.sh`, and `critic.py`. Use the `lean-lsp`
> MCP tools for goals, diagnostics, local search, and profiling. Report the exact SHA,
> exit code, and first diagnostic to rohanarun/alpoge-rh-replay#35028. Also monitor FC
> PRs #8214/#8187/#8215/#8219. No full builds during merge bursts.

## Local vs GitHub

- **On GitHub:** everything in `tools/rh-fix` — scripts, docs, queue, ledger,
  times, claims, journal.
- **Local only:** `~/.config/opencode/opencode.json` (MCP entry), `~/.rh-fix` live
  state, and the M4's `/work` logs/artifacts.
- **Reproduce:** exact SHA + `lake build Main Challenge` + the gists/comments.
