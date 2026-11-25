# Event journal

**Time:** all timestamps are **UTC** (`Z`). Local Pacific time = **UTC−8h** (PST, standard time); in summer = UTC−7h (PDT).

- 2026-11-24T10:44Z #120 closed by maintainer Deicyde as "superseded by #324" (which consolidated modules on main); reopened 13:18Z by Deicyde (Rohan confirmed the plan at 13:25Z); 4.36 lane active.
- 2026-11-24T14:04Z Board validation: 39/39 rows build clean at 49b2bdb6a8.
- 2026-11-24T15:04Z Full Main Challenge started at 49b2bdb6a8.
- 2026-11-24T16:35Z #120 closed temporarily (CI); work continues on the branch.
- 2026-11-24T18:03Z Board refreshed (29 rows) but stale vs tip.
- 2026-11-24T18:20Z Work-finder paused during merge wave.
- 2026-11-24T18:23Z test journal entry
- 2026-11-24T18:23Z Architecture deployed: content-hash ledger, stability gate, supervisor, claims, journal, receipts, sync.
- 2026-11-25T01:29Z Published 49b2 full-build terminal (133/20) and 7127 targeted results (Bundle0004 real, Bundle0224 stale).
- 2026-11-25T01:39Z Bundle0004 and Bundle0224 both compile clean at tip ab2ded12 (direct lean exit 0); @[expose] refactor fixed the private-declaration issue; no PR.
- 2026-11-25T02:51Z Calibrated full Main Challenge started at b9b24502 (predicted must_build=20012, jobs=191540, est ~6.5h).
- 2026-11-25T05:54Z b9b24502 full build: 1 error/1 module (ShortThetaValueComplexPointEqClassicalTheta:276), 3h; fixed at next tip (exact key). New full build started at 884075ed.
- 2026-11-25T07:09Z 884075ed full build: 1 module/6 errors in 22m; fixed at 94ff1f0f (attribute [-instance]); next build at 94ff1f0f.
- 2026-11-25T09:17Z Provenance recorded: PR #120 head frozen at 67edc6403 (Nov 23 11:27Z), 823 commits behind fork tip 94ff1f0f. M4 worktree is on local branch probe/next2, HEAD == origin/opt/collapse-and-consolidate-4.36 == 94ff1f0fd0. Build at 94,445/114,021, 0 errors.
- 2026-11-25T11:56Z mainbuild14 @94ff1f0f terminal: 113,995/114,021, `error: build failed`, 2 modules / 7 errors — ReBaseZeta (4: type mismatch 40/72/80, unknown `zeta_change` 272), HodgeTateFromSandwich (3: synthesized instance not defeq). Log sha256 7cfbd1c0…. Monitor-only watcher caught the exit; no auto-build.
- 2026-11-25T13:57Z Tip moved +10 to b35a3239c4 with fixes for both: #1414 ReBaseZeta, #1411/#1412 restore original instMeasGL disables in 12 modules. Targeted build of the two failures: 80,107 jobs, 0 errors, exit 0 (~2h01m).
- 2026-11-25T13:58Z mainbuild15 started at 7fb6893d70 (+8 commits / 13 files since b35a3239c4). Monitor-only watcher armed → /work/mainbuild15-summary.txt.
