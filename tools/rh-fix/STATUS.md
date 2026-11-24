# Status — 2026-11-24T18:10Z

Live handoff for another OpenCode session. Pull `maugomez77/alpoge-rh-replay`, branch `tools/rh-fix`.

## RH 4.36

- **#120 is closed** (16:35Z, temporary, to save CI); work continues on `opt/collapse-and-consolidate-4.36`.
- **Tip:** `ecce788d81` (moving rapidly; was `20193c2836` at 18:03Z).
- **Live board is stale:** updated 18:03Z with 29 rows, but all 29 modules were built clean at `49b2bdb6a8` and are unchanged since. The work-finder excludes them.
- **Last full build:** `49b2bdb6a8` → `error: build failed`, **133 errors / 20 modules**. 18 of those 20 files changed since; the two unchanged ones are being built at `7127dd68`:
  - `Development.AutomorphicArithmetic…GeometricFlagBases.Bundle0004`
  - `Development.AutomorphicSpectrum.Proofs.GeometryProofs.Bundle0224`
  - **Status: still building at `7127dd68`** (a large cone rebuild; the tip has since moved to `7b3e06bd1e`).
- Earlier results: baseline `376bacf238` → 96/27; rerun `2d20aa90` → 67/16, **24 of 27** baseline failures fixed.
- **Work queue:** see [`WORK-QUEUE.md`](WORK-QUEUE.md) — currently **1 M4** candidate and **20 mini** triage items (18 marked `VERIFY` because the file changed since the log SHA), with 28 stale board rows excluded.

## Formal Conjectures

| PR | State |
|---|---|
| #8214 Erdős 14 | ✅ Approved on latest commit; needs a 2nd approval |
| #8187 Erdős 1117 | ✅ Approved on latest commit; needs a 2nd approval |
| #8215 Erdős 81 | ✅ Review changes addressed; CI green; re-review pending |
| #8219 Erdős 96 | ✅ Only `96.lean`; proof links pinned to CI revision; re-review pending |

## Monitor from another session

```sh
git clone -b tools/rh-fix git@github.com:maugomez77/alpoge-rh-replay.git
# read tools/rh-fix/STATUS.md and WORK-QUEUE.md
```

Regenerate the queue:

```sh
python3 tools/rh-fix/work-finder.py --once \
  --repo /path/to/riemann-hypothesis \
  --validated tools/rh-fix/data/validated-49b2.txt \
  --validated-sha 49b2bdb6a8ca653a83fbd2ab25ca16ad9e261f7f \
  --build-log tools/rh-fix/data/mb11-errors.txt \
  --log-sha 49b2bdb6a8ca653a83fbd2ab25ca16ad9e261f7f
```

Watch mode: add `--interval 300` (exits when the queue changes).

## Links

- RH PR: https://github.com/leanprover-community/riemann-hypothesis/pull/120
- Coordination: https://github.com/rohanarun/alpoge-rh-replay/issues/35028
- FC PRs: [#8214](https://github.com/google-deepmind/formal-conjectures/pull/8214) · [#8215](https://github.com/google-deepmind/formal-conjectures/pull/8215) · [#8219](https://github.com/google-deepmind/formal-conjectures/pull/8219) · [#8187](https://github.com/google-deepmind/formal-conjectures/pull/8187)

## Not in the repo

- M4 build logs/artifacts (`/work`), local watcher PIDs/state, OpenCode session state.
- Reproduction needs only the SHA, `lake build Main Challenge`, and the gists/comments.

## Stopping

```sh
tools/rh-fix/stop-watchers.sh          # local GitHub watcher + work-finder
tools/rh-fix/stop-m4-build.sh          # kill lake/lean on the M4
tools/rh-fix/stop-m4-build.sh --container   # also stop rhreplay
tools/rh-fix/stop-all.sh               # everything
```
