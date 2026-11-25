> **Authoritative snapshot:** [`CURRENT.md`](CURRENT.md) — start there.

# Next session — start here

**Last updated:** 2026-11-25T06:15Z

## Read first

- `STATUS.md` — current snapshot (builds, PRs, machines)
- `HANDOFF.md` — repo/PR map and resume steps
- `JOURNAL.md` — event timeline

## Live state at handoff

| Item | Value |
|---|---|
| RH PR | https://github.com/leanprover-community/riemann-hypothesis/pull/120 (closed temporarily; lane active) |
| Coordination | https://github.com/rohanarun/alpoge-rh-replay/issues/35028 |
| Branch tip at handoff | `22f1682e9f` (moving) |
| Full build in flight | `884075ed`, log `/work/mainbuild13.log` on the M4, ~84k/114k jobs, **6 errors / 1 module** (`ExistsIsHaarProbabilityMaxCompactHermitian`) |
| Earlier milestone | `b9b24502`: full build with **1 error / 1 module**, runtime 3h; that module is fixed at the next tip |
| M4 | `maugomez77@mauricios-macbook-pro-1`, container `rhreplay`, repo `/work/rh120` |

## Machines & tooling

- **M4** is the builder (16 cores, 64 GB, Lean 4.36, warm `.lake`).
- **`lean-lsp` MCP** is configured in `~/.config/opencode/opencode.json` as a local
  server: `~/.rh-fix/lean-lsp-mcp-remote.sh` (stdio over SSH into the container).
  It auto-starts `rhreplay`. Tools: `lean_goal`, `lean_diagnostic_messages`,
  `lean_local_search` (needs `rg`, installed), `lean_loogle`, `lean_leansearch`,
  `lean_multi_attempt`, `lean_profile_proof`, `lean_build`, `lean_verify`.
- Watchers: `~/.rh-fix/supervise.sh start|stop|status|daemon` (GitHub watcher + work-finder).
- Queue: `~/.rh-fix/work-finder.py` (uses ledger, times, claims, stability gate).
- Estimator: `~/.rh-fix/plan.py` (`--elab-only` for intermediate checks).
- Critic: `~/.rh-fix/critic.py` (deterministic checks + Grok CLI review).
- Receipts: `~/.rh-fix/preflight.sh`, `~/.rh-fix/post-receipt.sh`.
- Stop: `~/.rh-fix/stop-watchers.sh`, `stop-m4-build.sh`, `stop-all.sh`.

## Immediate next steps

1. Check the terminal state of `/work/mainbuild13.log`; extract the full failure list.
2. For each failing module at the latest tip:
   - build-first (`lake build <module>` or `lake env lean` if artifacts match),
   - claim with a draft PR,
   - fix, run `preflight.sh`, run `critic.py`,
   - mark ready and post the exact SHA + exit + first diagnostic to #35028.
3. Re-check the FC PRs: #8214/#8187 (approved, need 2nd approval), #8215/#8219 (re-review).
4. Do **not** start full builds during merge bursts; wait for a quiet tip (10 min) or use
   `build-fast.sh --check` for `:elabArts`.

## Suggested opening prompt for a new session

> Continue the Riemann Hypothesis 4.36 consolidation work. Read
> `tools/rh-fix/NEXT-SESSION.md`, `STATUS.md`, and `HANDOFF.md` from
> `maugomez77/alpoge-rh-replay` (branch `tools/rh-fix`). The M4
> (`maugomez77@mauricios-macbook-pro-1`, container `rhreplay`) is the builder.
> A full `Main Challenge` build was running at `884075ed` (log
> `/work/mainbuild13.log`) with 6 errors in 1 module; check its terminal
> state, then work the failing modules using build-first, a draft claim,
> `preflight.sh`, and `critic.py`. Use the `lean-lsp` MCP tools for goals,
> diagnostics, local search, and profiler. Report the exact SHA, exit code,
> and first diagnostic to rohanarun/alpoge-rh-replay#35028. Also monitor
> FC PRs #8214/#8187/#8215/#8219. No full builds during merge bursts.
