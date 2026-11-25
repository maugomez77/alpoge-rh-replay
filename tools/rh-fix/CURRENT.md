# CURRENT — single source of truth

**Last updated:** 2026-11-25T06:50Z
**Repo:** `maugomez77/alpoge-rh-replay`, branch `tools/rh-fix`
**This file is the only one you need to read to resume.**
**Maintenance:** update it at every milestone (terminal build, merge, new claim). Supporting detail:
`STATUS.md`, `HANDOFF.md`, `JOURNAL.md`, `README.md`, `NEXT-SESSION.md` (older).

## What this project is

Two parallel efforts:

1. **Riemann Hypothesis consolidation (PR #120)** — a 4.36 Lean branch that collapses
   93k modules into ~20k bundles. It is **closed temporarily** while the branch is
   repaired; work continues on `opt/collapse-and-consolidate-4.36`. Our role: independent
   full builds, fault-finding, small fixes, receipts.
2. **Formal Conjectures** — four PRs adding Erdős problem statuses/answers.

## Live state (2026-11-25T06:50Z)

| Item | Value |
|---|---|
| **PR #120** | **CLOSED** (rohanarun, 16:35Z Nov 24) to stop the un-skippable `challenge-files.yml` check re-running on every push. Reopen only after green + verification + rebase. Work continues on the **fork** branch. |
| **Full build in flight** | `884075ed`, log `/work/mainbuild13.log` on the M4; 88,987 / 114,021 jobs |
| Errors | **6 / 1 module** (`ExistsIsHaarProbabilityMaxCompactHermitian`) — but `884075ed` **removed** the `attribute [-instance]` line; the tip restores it and the module compiles **clean (exit 0)** |
| Branch tip | `94ff1f0fd0` (quiet since 06:14Z) |
| **Watcher queued** | `/work/wait-and-build.sh` (PID 854956): on build exit → snapshot → fetch tip → `probe/next` → delta build to `/work/mainbuild14.log` |
| Earlier milestone | `b9b24502` full build: **1 error / 1 module**, 3h00m; that module is fixed at the next tip |
| Trajectory | 96/27 → 67/16 → 133/20 → **1/1** → 6 on the bad commit (0 at tip for that module) |
| lean-lsp MCP | **down** (tunnel refused; server shut down 06:10). `lake env lean` over SSH works. |

### New finding: instance-shadow census (2026-11-25)

`tools/rh-fix/instance-scan.py` over the 47,885-file tree:

- **18,802** `attribute [-instance]` lines in **10,343** files (21.6% of the tree)
- 5,968 instance declarations (5,416 global) + 2,378 `attribute [instance]` promotions
- 81 distinct disabled names
- Worst: `Module 𝓞` (17 providers, 3,540 file-disables), `IsScalarTower 𝓞` (11 / 3,540),
  `MeasurableSpace GL` (4 / 1,513), `BorelSpace GL` (9 / 1,509), `MeasurableSpace Matrix` (5 / 1,196)
- Single name: `GlobalTheory.AdmLoc.modFun` disabled in **5,737** files
- Removal candidates: `BaseC.modO` (688), `BaseC.towO` (688), `subfield_valuativeRel` (191),
  `rulesCommRing`/`rulesSMul` (116 each)
- Report: `/work/instance-census.md` on the M4; JSON beside it.

This is the defect family behind the `ExistsIsHaar` regression and the old `fintypePsi`/117-patch episode.
Treat `attribute [-instance]` lines as generated patches to be eliminated, not maintained.

### New finding: change cost is the reverse-dependency cone (2026-11-25)

`import-closure.py` on the 5 files changed between `884075ed` and `94ff1f0f`:

- **20,416 / 47,885 modules (42.6%)** are in the affected closure — i.e. a 5-file,
  mostly one-line delta invalidates nearly half the tree.
- Cause: the changed instance-bearing files are imported via hubs; the largest hub has
  **1,263 direct importers**. The tree shape, not the diff size, sets the build cost.
- Consequence: for this tip a full `Main Challenge` build is the correct call; the
  delta fallback triggers above `DELTA_MAX` (default 15,000).
- Five files use `import all`; `import-closure.py` seeds them as roots (exact, cheap).

Apply: when touching an instance-bearing hub, budget a full build. Reducing hub fan-in
(or scoping the instance so hubs need not import it) is the only durable speedup.

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
| `instance-scan.py` | Instance-shadow census: class+head groups, disable lines, removal candidates, `--gate` |
| `hygiene-check.sh` | Gate: no new global instances vs a baseline (2m47s full tree; `--changed` for a diff) |
| `import-closure.py` | Reverse-dependency closure of changed modules (delta-green unit) |
| `delta-build.sh` | Build only the closure; falls back to `Main Challenge` above `DELTA_MAX` |
| `wait-and-build.sh` | Wait for a build to exit, snapshot it, advance to the tip, delta build |
| `certify.sh` | Clean-source `:olean` build + exports + comparator + independent kernels |
| `warm-cache.sh` | Try the repo's validated CI cache (exit 3 = none) |
| `stop-all.sh [--container]` | Stop watchers + M4 build/container |
| `lean-lsp-mcp-remote.sh` | stdio-over-SSH bridge to `lean-lsp-mcp` in the container |

**`lean-lsp` MCP** is configured in `~/.config/opencode/opencode.json` (local command
= the wrapper). It auto-starts `rhreplay`. Tools: `lean_goal`,
`lean_diagnostic_messages`, `lean_local_search` (ripgrep installed), `lean_loogle`,
`lean_leansearch`, `lean_multi_attempt`, `lean_profile_proof`, `lean_build`,
`lean_verify`. Restart OpenCode to reload it.

## Immediate next steps

1. **Build tail.** Wait for `mainbuild13` to terminate; read
   `/work/mainbuild13-summary.txt`. The watcher then fetches the then-current tip,
   checks out `probe/next`, and runs the delta build to `/work/mainbuild14.log`.
2. **If the tip build is green:** run `certify.sh <sha>` (fresh worktree,
   `:olean`-only build, exports, `lake comparator`, `con-leche --verified`,
   `leanchecker-paranoid`), then rebase onto `main` with `Challenge.lean` /
   `Statements.lean` unchanged → ask Rohan to reopen #120.
3. **If new errors:** build-first → claim (draft PR) → fix → `preflight.sh` →
   `critic.py` → post exact SHA/exit/first diagnostic to #35028.
4. **Instance hygiene (parallel).** Add the semantic audit (`InstanceAudit.lean`:
   import the module, group instances by class+head, flag duplicates/defeq), then
   remove the single-provider instances first (`BaseC.modO` 688, `BaseC.towO` 688,
   `subfield_valuativeRel` 191, `rulesCommRing`/`rulesSMul` 116) and convert the top
   offenders (`modFun`, `modTens`, `modProd`, `modQuot`, `subRulesModuleInt`,
   `instMeasGL`, `instBorelGL`, GL topology) to `scoped instance`.
5. **Cache benchmark.** After the tip build: same-worktree / fresh-worktree /
   fresh-container advances with `LAKE_ARTIFACT_CACHE=true`; prime with
   `lake build -o maps.json` + `lake cache add`.
6. FC: #8214/#8187 approved (need 2nd approval); #8215/#8219 re-review.

## Certification gate (next after green)

Disk reality on the M4 (2026-11-25):

| Path | Size |
|---|---:|
| `.lake/build/ir` (default `irArts`: `.ir`/`.c` per module) | **287 GB** |
| `.lake/build/lib/lean` (oleans) | **56 GB** |
| `.lake/packages` (Mathlib artifacts) | 7.3 GB |
| free on `/work` | 189 GB |

A default clean build (343 GB) **does not fit**. An `:olean`-only build does (56 GB).

`certify.sh <sha>`:
1. fresh worktree at the SHA, share only `.lake/packages` (not the project build);
2. `lake build Main:olean Challenge:olean` — no IR/C;
3. `leanexport Challenge` / `leanexport Main` with `export-targets.txt`;
4. `lake comparator --config comparator.json --challenge-from-export … --solution-from-export …`;
5. `con-leche --verified` and `leanchecker-paranoid` on the solution export;
6. receipt with SHA, build-log hash, export hashes, stage results.

`bubblewrap 0.9.0` is installed in `rhreplay`. `lake comparator` and `lake check` require it.

## Process gates now in place (2026-11-25)

- **Instance gate:** `hygiene-check.sh` (full tree 2m47s; `--changed BASE` for a diff).
  Baseline: `~/.rh-fix/instance-census-baseline.json`. Negative test verified (new
  instance → exit 1). Wire into bundle regeneration and PR preflight.
- **Delta-green:** `delta-build.sh` builds the reverse-dependency closure and writes a
  receipt with `jobs=done/total`, coverage, log sha, first error. Falls back to
  `Main Challenge` when the closure is large or a config file changed.
- **Receipts:** `preflight.sh` now records build jobs, coverage %, and the verification
  ladder (build → clean machine → comparator → con-leche), instead of just PASS/FAIL.
- **Watcher:** `wait-and-build.sh` snapshots the old build, advances to the tip, and
  starts the delta build without idle time.

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
