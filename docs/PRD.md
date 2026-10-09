# RepoMedic — Product requirements

Version 0.4 · 2026-10-09 · Status: proposed behavior; no measured results.

## 1. User and job

Primary user: maintainer or developer of a supported Python repository with a reproducible pytest suite. Job: repair a specified dependency upgrade, inspect the patch, and reproduce its verification before manually applying it.

MVP public users choose a curated repository/task. Additional public repositories are supported only through an operator/local recipe, not an unrestricted URL box. Private code and automated repository writes are excluded.

The user gets a downloadable patch, evidence JSON, readable report and verification instructions. A branch animation without those outputs is not a finished product.

## 2. Product claims

Allowed after observed execution: “This patch passed the preserved suite with target version X installed in the recorded environment.”

Not allowed: tamper-proof, guaranteed safe, zero regressions outside test coverage, repairs any repository, or branching superiority before results. An LLM review cannot override failed verification.

## 3. Core journey

1. Explore a labeled recorded run without signing in.
2. Enter a supplied access code to create a live session; no email, account or GitHub OAuth.
3. Select a task; inspect repository commit, upgrade, supported recipe and resource budget.
4. Start repair. The app queues work and returns the run view promptly.
5. Watch baseline validation, breakage reproduction, strategies, candidate results and refinement.
6. Inspect the selected candidate and fresh verification.
7. Download artifacts or inspect an honest failure report.
8. Apply manually in the user's own checkout and rerun tests. RepoMedic never merges or pushes.

Detailed screens, judge flow and video are in USER_FLOW_AND_DEMO.md.

## 4. Acceptance gates

A successful run requires all of the following:

- Pinned reference suite is reproducibly green, with a recorded test manifest and explicit original skip/xfail expectations.
- Applying the requested upgrade reproducibly breaks that suite; setup failures are distinct from test failures.
- Candidate changes satisfy the recipe's source-path policy; no tests, fixtures, runner or unrelated dependency manipulation.
- Target package version is confirmed through trusted environment inspection; inspect import origin to detect obvious shadowing and disallow recipe-incompatible compatibility fallbacks.
- Candidate diff is reapplied to a clean upgraded checkpoint; no search-branch environmental mutations are inherited.
- Preserved tests, fixtures and runner configuration are restored and checked against hashes before and after execution.
- No missing collected tests, unexpected skips/xfails, collection failures or previously passing test regressions.
- Full required suite completes within limits and yields a verifier-owned record with exit status, test identities and logs.

Passing these checks is evidence about this suite and recipe. Python code can alter runtime behavior; absolute adversarial resistance is not claimed.

Hard-failed candidates cannot win through a favorable score or model review. No candidate meeting every gate means `failed`, even if a partial patch is useful.

## 5. Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | List pinned curated tasks and immutable recipe versions | P0 |
| FR-02 | Access-code exchange into scoped session; enforce ownership on every live run endpoint | P0 |
| FR-03 | Start run with idempotency key; enforce budgets before queueing | P0 |
| FR-04 | Persist jobs/events before acknowledging; process in bounded worker | P0 |
| FR-05 | Verify baseline, requested dependency installation and red upgraded state | P0 |
| FR-06 | Run sequential repair and branch-and-refine under the same verifier | P0 |
| FR-07 | Generate structurally valid diffs restricted to recipe-approved paths | P0 |
| FR-08 | Fresh final verification and protected test-manifest checks | P0 |
| FR-09 | Select valid candidates by reproducible correctness/maintainability policy | P0 |
| FR-10 | SSE events with sequence IDs and reconnect; snapshot view remains available | P0 |
| FR-11 | Cancel work; prevent late operation results from accepting a cancelled run | P0 |
| FR-12 | Export patch, evidence and readable failure/success report | P0 |
| FR-13 | Playback real immutable recorded runs, visibly labeled | P0 |
| FR-14 | Matched-budget held-out evaluation; raw paired results and methodology | P0 |
| FR-15 | Recover tracked operations after restart or fail clearly; no blind duplicate submission | P0 |
| FR-16 | Independent-candidate baseline | P1; required before claiming refinement lift |
| FR-17 | Optional review model; human-readable rationale | P1 |
| FR-18 | Saved migration references grounding diagnosis | P1 |

## 6. Selection and stop policy

Start with three strategies maximum and one refinement round per retained branch; defaults are tuning parameters. Avoid one branch per failure cluster if fixes must interact: each candidate addresses the complete task, with clusters used to organize context.

During search, use fewer failures and no newly introduced failures as progress indicators; log timeouts separately. Retain diverse promising candidates within remaining budget. Fixed round barriers initially keep allocation reproducible.

Final order: hard verification eligibility, known forbidden-pattern checks, migration/maintainability assessment, then smaller diff as a secondary preference. Reviewer disagreement creates a warning or an explicit review-required failure according to a frozen policy; it cannot silently approve a failed gate. Stop after fresh verification of an acceptable candidate or budget/deadline exhaustion, using identical stopping policy in comparable arms.

## 7. UX states

Run: `queued`, `provisioning`, `baseline_check`, `bump_check`, `diagnosing`, `searching`, `final_verification`, then `succeeded`, `failed`, `aborted`, `cancelled`, or `budget_exhausted`.

No breakage after upgrade is `aborted` with reason `no_breakage`, not a counted repair success. Nonreproducible baseline is `aborted` with `baseline_unstable`; do not silently remove tests to make it green.

Candidate: `planned`, `generating`, `patch_invalid`, `testing`, `partial`, `rejected`, `candidate`, `verifying`, `verified`, `winner`, `pruned`.

UI uses text/icons as well as color. Show original/upgraded test results, actual installed dependency, selected strategy, elapsed time and budgets. Model decision summaries are concise explanations, not exposed private reasoning transcripts.

## 8. Performance and reliability targets

Targets, not guarantees: queue acknowledgement within two seconds on a warm host; visible progress during setup; chosen video task completes within a measured practical budget. Do not promise an end-to-end time before profiling provisioning, inference and tests.

Refresh/reconnect must retain events and ownership. A restart must not erase run records or mark abandoned work successful. Artifact download is deterministic and works after worker restart. Recorded examples remain available even when live inference is unavailable, with the outage shown honestly.

## 9. Evaluation and impact

Use EVALUATION.md. Report solved/eligible tasks, invalid/environment failures, regressions observed, new skip/xfail events, tokens, actual/estimated spend, sandbox time, wall time and manual interventions.

Interview or obtain feedback from a few maintainers using real patches. Record whether they would accept the patch and what they changed; do not fabricate adoption or hours saved. A maintainer review is useful beyond passing tests.

## 10. Infrastructure requirements

SQLite and durable local artifact storage are required for this deployment. S3, PostgreSQL, Redis and full user accounts are not. Live execution requires lightweight auth, ownership, resource ceilings and verified sandbox isolation. Open replay does not need auth.

Retention: persist pinned public demo/evaluation artifacts through judging; temporary live artifacts default to seven days, configurable and disclosed. Purge temporary artifacts only after terminal state and never while operations remain active. Separate frozen submission artifacts from expiring user-run data.

## 11. Definition of done

- A judge can start a fresh curated repair and download a real patch/report.
- A developer can run documented setup from a clean clone.
- Integrity fixtures reject downgrade, deleted tests, changed collection and new skips.
- Restart, timeout, cancellation and reconnect have exercised behavior.
- Evaluation protocol and raw results are published; claims match results.
- English video shows actual execution, with sped-up sections labeled.
- Secrets and unrestricted commands cannot be supplied through public inputs.
