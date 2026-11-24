# ~/.rh-fix — repair toolchain for the Riemann-Hypothesis consolidation

Build-first, claim-second. Every fix gets a receipt before it becomes `ready for review`.

## Scripts

| Script | Purpose |
|---|---|
| `preflight.sh <Module> [--importers] [--axioms "Ns.thm"]` | Full receipt for one fix: changed-input count, `open … _root_.` scan, statement diff, direct-importer list, build log, optional `#print axioms`, log SHA-256 → `receipts/<ts>-<module>/RECEIPT.md` |
| `scan-opens.py <files…>` | The systemic consolidation bug: `_root_.N.foo` inside a selective `open N (…)` list becomes `N._root_.N.foo` and kills the whole open. Exit 1 on hit. |
| `regression-watch.sh [repo]` | Rebuild every module in `watch-modules.txt` at the current tip; catches reversions (the `Bundle0295` class of bug). |
| `watch-modules.txt` | Modules we fixed — the regression guard list. |

## Workflow (the part that actually matters)

1. **Validate before claiming.** Build the module at the *latest tip*. If it already builds, do not open a PR — close any stale claim.
2. **Draft claim immediately**, one module/family per PR, body states diagnosis + planned fix.
3. **Fix, preflight, build.**
4. **`gh pr ready` the moment the build is green.** A verified draft sits in limbo: the auto-merger only processes ready PRs, and rohanarun's rule is that drafts are claims, not submissions. This bit us on #790/#796.
5. **Report the exact SHA**, never "latest": `lake build` receipts name the commit they ran at.
6. **Regression-watch after coordinator merges** touching our modules.

## Receipt fields (what the community checks)

- exact tested SHA
- changed project inputs (count, ideally the one file)
- build command + result + log digest
- `#print axioms` on the touched theorems (should be the three permitted only)
- statement diff: none
- direct importers built, not just the target

## Gotchas

- `PR120-BUGS.md` is generated from a **private snapshot**; rows can be stale or from a different commit. Always rebuild to confirm.
- `set_option maxHeartbeats` / `synthInstance.maxHeartbeats` bumps are acceptable *when the search terminates* — say so in the PR body, and stay near the file's existing local budget.
- Prefer root causes: a wrong `open` entry explains dozens of cascading errors; do not patch the cascades.
- Duplicates and wrong-name resolutions (`mulB`, `Dec`) are usually one qualification, not N bugs.
