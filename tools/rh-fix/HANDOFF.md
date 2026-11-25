> **Authoritative snapshot:** [`CURRENT.md`](CURRENT.md) — start there.

# Handoff — RH 4.36 + Formal Conjectures

**Last updated:** 2026-11-24T16:40Z

## Formal Conjectures (`google-deepmind/formal-conjectures`)

All branches are pushed to **`maugomez77/formal-conjectures`**; the PRs are the source of truth.

| PR | Branch | Head | State |
|---|---|---|---|
| **#8214** Erdős 14 | `fix/erdos-14-status` | `cca4ea62` | ✅ Approved on latest commit; needs a 2nd approval |
| **#8215** Erdős 81 | `fix/erdos-81-status` | `f14ede6b` | ✅ Review changes addressed (qualified bound, conditional claim, no `formal_proof` tag); green |
| **#8219** Erdős 96 | `fix/erdos-96-status` | `9c385e36` | ✅ Rebased (only `96.lean`), proof links pinned to CI revision `90fd28e5` |
| **#8187** Erdős 1117 | `add-erdos-1117` | `ddc39a2f` | ✅ Approved on latest commit; needs a 2nd approval |

## Riemann Hypothesis — PR #120 (reopened 13:25Z)

- PR: `leanprover-community/riemann-hypothesis#120`. **Do not merge before step 2** (rebase gains onto `main` / #324).
- Coordination: **`rohanarun/alpoge-rh-replay#35028`**.
- Active full build: M4 container `rhreplay`, repo `/work/rh120`, SHA **`49b2bdb6a8`**, log `/work/mainbuild11.log`.
- Earlier results:
  - Baseline `376bacf238`: **96 errors / 27 modules** (terminal, `error: build failed`).
  - Rerun `2d20aa90`: **67 / 16**, **24 of 27** baseline failures fixed.
  - Board validation at `49b2bdb6a8`: **39/39** open rows build clean (board was stale).
- Step-2 upstream inputs (from Roy):
  - **#1033** — removes `Neutral.B1` copies of `G`/`IsPlaceOver`/`Dec`/`Inertia`, 38 `open … hiding` lines, 89 qualifications. Root cause for ambiguous `G`/`IsPlaceOver`/`Dec`.
  - **#1176** — `GlobalTheory.CompHt.fintypePsi` becomes a `scoped instance`; 117 `attribute [-instance]` workarounds deleted; 59 `open scoped` added. First family of #599.
  - **#968** — deletes unused `TNZ.Grp.step_spSupp` + two repair-only definitions.

## Toolchain (this folder)

`preflight.sh`, `scan-opens.py`, `regression-watch.sh`, `watch-github.py` (repo-wide comments, edits, @mentions, PR states/reviews/conflicts), config files, README.

## Resume on a new machine

1. `gh auth login` — needs `repo` and `notifications` scopes.
2. SSH key for the builder host (or provision a new one).
3. Clone `maugomez77/formal-conjectures` and check out the PR branches above; `gh pr list --author maugomez77`.
4. Copy `tools/rh-fix/` to `~/.rh-fix/`; run `watch-github.py` (needs gh auth).
5. Builds: container `rhreplay` on the M4, repo `/work/rh120`; reproduce with
   `lake build Main Challenge` at the exact SHA.
6. Gists/comments referenced in the PR threads contain the diagnostic receipts.

## Not in GitHub

- M4 build logs and artifacts (`/work`), local `~/.rh-fix` receipts, OpenCode session state.
- Everything needed to **reproduce** is: the SHA, the `lake build` command, and the gists/comments.
