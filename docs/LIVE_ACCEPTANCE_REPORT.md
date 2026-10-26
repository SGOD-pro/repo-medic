# Live Acceptance Report

## Summary

This report documents the live provider acceptance verification for RepoMedic using the validated TASK-091 fixture.
All repair and verification steps executed with real cloud providers and remote Turso database persistence.

## Execution and Version Identifiers

* Application Execution Commit: `c44cf7c`
* Application Verification Commit: `90b52ad3775694bb004b598d2ca6bb0ae17cf061`
* Target Repository: `https://github.com/SGOD-pro/repo-medic.git`
* Target Commit SHA: `453a0b6c6b125177504cdd941902b8d48266ed1c`
* Task Identifier: `TASK-091` (Upgrade sqlalchemy from 1.4.48 to 2.0.19)
* Live Run Identifier: `run_466bde7e846a494b8414e6f973df97d1`
* Terminal State: `succeeded`
* Browser Verification URL: `http://localhost:3000/?runId=run_466bde7e846a494b8414e6f973df97d1`

## Provider Configuration

* Model Inference Provider: Nebius Token Factory
* Model Name: `nvidia/nemotron-3-super-120b-a12b`
* Sandbox Execution Provider: Nebius ConTree Sandbox
* Container Image: `python:3.12-bookworm`
* Database Storage: Remote Turso database
* Database URL: `libsql://repo-medic-swyra-07.aws-ap-south-1.turso.io`
* Storage Backend: `turso` (LibSQL client)

## Pipeline Verification Results

1. Baseline Stage: Passed (1 test passing on pinned commit 453a0b6c6b125177504cdd941902b8d48266ed1c).
2. Upgrade Stage: Failed as expected when upgrading sqlalchemy to 2.0.19 (removed execute method on Engine).
3. Candidate Generation: Generated single pass repair candidate modifying src/backend/database.py (+8 additions, -6 deletions) wrapping statements in engine.begin() context.
4. Sandbox Verification: Pytest 9.1.1 on Python 3.12.15 passed cleanly (1 passed in 0.18s, 0 regressions).
5. Post Test Check: Zero new skips, collection node ids preserved, dependency sqlalchemy 2.0.19 verified in site-packages.
6. Execution Metrics: Verification duration 10.3s, model calls 1, input tokens 613, output tokens 1803, estimated cost $0.35 USD.

## Artifact Integrity and Hashes

All run artifacts are persisted in remote Turso storage and stored locally in artifacts/:

* `artifacts/live_patch.diff` (767 bytes)
  SHA-256: `1c07be13a086c8711df4312e57fc14676b32a126f5d855c9285d833020cac85f`
* `artifacts/live_verify.log` (358 bytes)
  SHA-256: `c2f695bba8fe2f3c4c63260dc5078f92fec38a855b83081e671799236df4e753`
* `artifacts/live_evidence.json` (1259 bytes)
  SHA-256: `8b95bbad5150ecc2d6a7d277adb51edfe869d1ed292e6bd3d5e4db1451d4d984`
* Verification Screenshots:
  * `artifacts/live_results.png`
  * `artifacts/live_reload_results.png`
  * `artifacts/live_task_selection.png`
  * `artifacts/live_execution.png`

## Explicit Evidence Gaps

The following known evidence gaps are recorded explicitly:

1. Persistence Boolean in Historical Evidence File:
   In the saved historical file `artifacts/live_evidence.json`, `checks.artifacts_persisted` is recorded as `false`. This occurred because the original code serialized the JSON manifest before updating its internal status. The artifacts exist in remote Turso storage and on disk. The engine code in `backend/src/engine/verifier.py` was updated in commit `90b52ad` to persist external artifacts first so that subsequent executions write `artifacts_persisted: true`.
2. Self Hash in Historical Evidence File:
   In the saved historical file `artifacts/live_evidence.json`, `artifact_hashes["evidence.json"]` contains an internal hash computed over an earlier dictionary state. The true external SHA-256 hash is `8b95bbad5150ecc2d6a7d277adb51edfe869d1ed292e6bd3d5e4db1451d4d984`. The engine verifier was corrected to exclude internal self hashes from the manifest and rely on external storage metadata.
3. Deployment Boundary:
   This acceptance was executed with frontend and backend processes running locally while communicating with remote Turso and live Nebius cloud endpoints. Public deployment URL verification remains to be performed once the public host is active.
4. Search Strategy Scope:
   This run validated the sequential direct repair strategy. Branch and refine with multiple generation candidates and iterative refinement loops was not executed during this run to conserve project budget.
