# CURRENT — single source of truth

**Last updated:** 2026-11-25T21:22Z (13:22 PST)
**Time:** all timestamps are **UTC** (`Z`). Local Pacific time = **UTC−8h** (PST, standard time); in summer = UTC−7h (PDT).
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

## Live state (2026-11-25T21:05Z)

| Item | Value |
|---|---|
| **PR #120** | **CLOSED** (rohanarun, 16:35Z Nov 24) to stop the un-skippable `challenge-files.yml` check re-running on every push. Reopen only after green + verification + rebase. Work continues on the **fork** branch. **Provenance:** first closed by *Deicyde* at 10:44Z Nov 24 as "superseded by #324", reopened 13:18Z by Deicyde (Rohan confirmed the plan at 13:25Z), re-closed by the author at 16:35Z. The PR head is frozen at `67edc6403` (Nov 23 11:27Z) — **900+ commits behind** the current fork tip `e497a6603e`. |
| **mainbuild14** | `884075ed`…`94ff1f0f`, terminal 11:56Z Nov 25: **113,995 / 114,021**, `error: build failed`, **7 errors / 2 modules**: `ReBaseZeta` (4) and `ArchimedeanSchwartz.HodgeTateFromSandwich` (3). Log `/work/mainbuild14.log`, sha256 `7cfbd1c0…`. |
| **mainbuild15** | `7fb6893d70`, started 13:58Z. **Killed at 20:02Z by host-disk exhaustion** (see Disk). Was 105,280/105,967, **0 errors**. A resume (`mainbuild15b`) also died; superseded by mainbuild16b. |
| **mainbuild16b in flight** | **`e497a6603e`**, started 21:01Z (13:01 PST); **`lake build Main:elabArts Challenge:elabArts`** (olean/ilean only — no IR/C). Log `/work/mainbuild16b.log`. |
| Branch tip | `e497a6603e` (+29 commits since `7fb6893d70`). M4 worktree checked out as `probe/next5`. |
| Targeted check | `b35a3239c4`: build of the two mainbuild14 failures → **80,107 jobs, exit 0** (13:57Z). Fixes: #1414 (`ReBaseZeta`), #1411/#1412 (`instMeasGL` disables restored in 12 files). |
| **Disk (recovered)** | Root cause of the 20:02Z VM force-stop: **host disk 100% full** (118 MB free); OrbStack `data.img.raw` had grown to **792 GB**, and `.lake/build/ir` was **450 GB**. Cleanup: caches + stale Docker Desktop (~20 GB host), deleted `ir` (450 GB). OrbStack auto-reclaimed: image **366 GB**, host **445 GB free**, `/work` 43% used. |
| Watcher | monitor-only `/work/watch-build.sh` armed for mainbuild16b → `/work/mainbuild16b-summary.txt`; matches any `lake build`. |
| Earlier milestone | `b9b24502` full build: **1 error / 1 module**, 3h00m; fixed at the next tip |
| Trajectory | 96/27 → 67/16 → 133/20 → **1/1** → **2/7** at `94ff1f0f` → **0** for those two at `b35a3239c4` |
| lean-lsp MCP | **removed** from the OpenCode catalog (2026-11-25 system update); no MCP tools available. `lake env lean` over SSH works. |

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

### Mini disk (2026-11-25)

- Was **96%** (21 G free) → **82%** (81 G free).
- Hugging Face cache 54 G moved to `/Volumes/Storage/caches/huggingface` + symlink.
- npm cache 6.4 G freed.
- **`~/dev` (61 G) held** — an external symlink would break remote SSH ownership/permissions.
- **uv 194 G pending** — `archive-v0` is locked by 7 live MCP servers. After an
  OpenCode restart: `uv cache clean` (the tool environments themselves are only 242 MB).
- Remaining candidates: OrbStack 65 G, Ollama 22 G, Claude/Google app data ~21 G,
  `~/Library/Caches` 15 G.
- `/Volumes/Storage`: 1.8 TiB total, **1.5 TiB free**.

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
| `times-extract.py` | Per-module compile-time history → `build-costs.json` + `times-rich.txt` |
| `dep-graph.py [--level 1\|2]` | Render the real import graph from `src/` (SVG/PNG/JSON) |
| `module-graph-layout.py` | Force layout (DrL) of all modules → `npz/json` cache |
| `module-graph-{render,density,layers}.py` | Galaxy, density-reveal, and layered-BFS renders |
| `module-graph-interactive.py` | Self-contained Plotly WebGL HTML (pan/zoom/hover) |
| `module-graph-buildtime.py` | Layout coloured by measured per-module compile cost |
| `module-graph-structure.py` | k-core portrait + longest-chain critical path |
| `module-graph-treemap.py` | Interactive namespace treemap + sunburst |
| `module-graph-semantic.py` | TF-IDF→SVD→t-SNE semantic map of module source |
| `module-graph-instances.py` | `attribute [-instance]` debt map on the layout |
| `module-graph-duplicates2.py` | Strict near-duplicate census (rare IDs kept + token Jaccard) |
| `module-graph-ricci.py` | Exact Ollivier–Ricci curvature on namespace-cluster graphs |
| `module-graph-forman.py` | Full-graph Forman–Ricci curvature map |
| `ricci_sample_job.py` + `ricci_merge.py` | Sharded Ollivier–Ricci on GitHub Actions (pairwise paths); full 495k-edge pass |
| `module-graph-ricci-map.py` | Render the full-graph ORC map from shard artifacts |
| `graph-export.py` + `module-graph-layout-tsv.py` | Export a tree's names/edges and lay it out (current-tip images) |
| `build-timeline-extract.py` + `module-graph-timeline.py` | Real build Gantt from a log + olean mtimes |
| `preflight.sh <Module>` | Receipt: scope, open scan, statements, importers, build log digest, axioms |
| `critic.py --module … --error …` | Deterministic checks + Grok CLI review before `gh pr ready` |
| `post-receipt.sh <Module> <PR>` | Post the preflight receipt once (marker-deduped) |
| `build-fast.sh [--check\|--ir]` | Cache preflight + disk guard; `:elabArts` by default, `--ir` for default facets |
| `disk-guard.sh` | Shared guard: abort builds below 100G (VM) / 80G (host); sourced by build scripts |
| `pin-build.sh [stable_s] [branch]` | Quiescence gate + pinned-SHA `elabArts` build + JSON/Markdown receipt |
| `instance-scan.py` | Instance-shadow census: class+head groups, disable lines, removal candidates, `--gate` |
| `hygiene-check.sh` | Gate: no new global instances vs a baseline (2m47s full tree; `--changed` for a diff) |
| `import-closure.py` | Reverse-dependency closure of changed modules (delta-green unit) |
| `delta-build.sh` | Build only the closure as `:elabArts`; falls back to `Main Challenge` above `DELTA_MAX` (`DELTA_IR=1` for IR) |
| `wait-and-build.sh` | Wait for a build to exit, snapshot it, advance to the tip, `elabArts` build |
| `certify.sh` | Clean-source `:elabArts` build + exports + comparator + independent kernels |
| `InstanceAudit.lean` | Semantic instance audit: reads `Meta.instanceExtension` (keys, priority, module), not source text |
| `warm-cache.sh` | Try the repo's validated CI cache (exit 3 = none) |
| `stop-all.sh [--container]` | Stop watchers + M4 build/container |
| `lean-lsp-mcp-remote.sh` | stdio-over-SSH bridge to `lean-lsp-mcp` in the container |

**`lean-lsp` MCP** is configured in `~/.config/opencode/opencode.json` (local command
= the wrapper). It auto-starts `rhreplay`. Tools: `lean_goal`,
`lean_diagnostic_messages`, `lean_local_search` (ripgrep installed), `lean_loogle`,
`lean_leansearch`, `lean_multi_attempt`, `lean_profile_proof`, `lean_build`,
`lean_verify`. Restart OpenCode to reload it.

## Immediate next steps

1. **Tip build.** `mainbuild16b` at `e497a6603e` (started 21:01Z), `elabArts` only.
   The two mainbuild14 failures are already confirmed clean at `b35a3239c4`
   (80,107 jobs, exit 0). On exit: if green → `certify.sh e497a6603e`; if errors →
   triage and delta-build. Do **not** run plain `lake build Main Challenge` on
   this machine without space headroom: IR is 450 GB and previously filled the host.
   **Next cycle:** use `pin-build.sh 600` (quiescence gate + pinned SHA + JSON
   receipt) instead of starting ad-hoc builds at a moving tip.
2. **If the tip build is green:** run `certify.sh <sha>` (fresh worktree,
   `elabArts`-only build, exports, `lake comparator`, `con-leche --verified`,
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
7. **Deferred — graph-analysis recommendations.** Ollivier–Ricci findings and
   the interface/dedupe/instance-debt proposals live in
   `evidence/curvature/RECOMMENDATIONS.md`. Analysis only: validate each with a
   delta-build before touching the tree; do not start refactors until green +
   certification are stable.

## Certification gate (next after green)

Disk reality on the M4 (2026-11-25, after cleanup):

| Path | Size |
|---|---:|
| `.lake/build/ir` (default `irArts`: `.ir`/`.c` per module) | **450 GB → deleted** |
| `.lake/build/lib/lean` (oleans) | 73 GB |
| `.lake/packages` (Mathlib artifacts) | 0.5 GB |
| `/work` in use / free | 342 GB / 469 GB |
| OrbStack image / host free | 366 GB / 445 GB |

A default clean build's IR (450 GB) does **not fit safely**. Use **`elabArts`**
(olean/ilean only). Lake 5.0 library facets are `elabArts` / `irArts`; the
`:olean` facet exists only on modules — `Main:olean` fails with
"unknown lean_lib facet `olean`". `certify.sh` was fixed accordingly.

`certify.sh <sha>`:
1. fresh worktree at the SHA, share only `.lake/packages` (not the project build);
2. `lake build Main:elabArts Challenge:elabArts` — no IR/C;
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
