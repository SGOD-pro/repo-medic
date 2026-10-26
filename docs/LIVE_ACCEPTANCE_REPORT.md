# Live Acceptance Report

## Summary

This report documents the live provider acceptance verification for RepoMedic using the validated `TASK-091` fixture.
All repair and verification steps executed with real cloud providers and remote Turso database persistence.

## Execution and Version Identifiers

### Current Full E2E Execution

* Application Execution Commit: `0d514093a552d6a78bd20083c4b6cd67afd102f3`
* Target Repository: `https://github.com/SGOD-pro/repo-medic.git`
* Target Commit SHA: `453a0b6c6b125177504cdd941902b8d48266ed1c`
* Task Identifier: `TASK-091` (Upgrade sqlalchemy from 1.4.48 to 2.0.19)
* Live Run Identifier: `run_93c660238e3443a6a18249167eb1939b`
* Terminal State: `succeeded`
* Browser Verification URL: `http://localhost:3000/?runId=run_93c660238e3443a6a18249167eb1939b`
* Repair Strategy: Sequential direct repair

### Historical Execution Reference

* Historical Live Run Identifier: `run_466bde7e846a494b8414e6f973df97d1`
* Historical Commit: `c44cf7c`
* Historical Verification Commit: `90b52ad3775694bb004b598d2ca6bb0ae17cf061`

## Provider Configuration

* Model Inference Provider: Nebius Token Factory
* Model Name: `nvidia/nemotron-3-super-120b-a12b`
* Sandbox Execution Provider: Nebius ConTree Sandbox
* Container Image: `python:3.12-bookworm`
* Database Storage: Remote Turso database
* Database URL: `libsql://repo-medic-swyra-07.aws-ap-south-1.turso.io`
* Storage Backend: `turso` (LibSQL client)
* Application Process: Single FastAPI backend with embedded queue worker on port 8000
* Frontend Process: Next.js production server on port 3000 with HTTP transport and proxy rewrites

## Pipeline Verification Results

1. Baseline Stage: Passed cleanly twice (1/1 tests passing on pinned commit 453a0b6c6b125177504cdd941902b8d48266ed1c).
2. Upgrade Stage: Failed as expected when upgrading sqlalchemy to 2.0.19 with `AttributeError: 'Engine' object has no attribute 'execute'`.
3. Candidate Generation: Generated single pass repair candidate modifying `src/backend/database.py` (9 additions, 7 deletions) wrapping engine queries in `engine.begin()` context.
4. Sandbox Verification: Pytest 9.1.1 on Python 3.12.15 in clean ephemeral microcontainer passed cleanly (1 passed, 0 failed, 0 regressions).
5. Post Test Checks: Zero new skips, collection node ids preserved, dependency sqlalchemy 2.0.19 verified in site packages, test file post patch hash matching `SHA-256` baseline.
6. Execution Metrics: Verification duration 20.5s, model calls 1, input tokens 613, output tokens 1114, estimated cost $0.35 USD within the $2.00 run budget ceiling.
7. Browser Diagnostics: 0 browser console errors, 0 failed network requests.

## Artifact Integrity and Hashes

All run artifacts are persisted in remote Turso storage and stored locally in `artifacts/run_93c660238e3443a6a18249167eb1939b/`:

* `patch.diff` (816 bytes)
  Artifact ID: `art_304d0a144e42`
  `SHA-256`: `f8b7f7dd3df30975b81d64b1233412d894faa5f9cd610dace92f32812a9fb41f`
* `verify.log` (358 bytes)
  Artifact ID: `art_662d905481e2`
  `SHA-256`: `5c86d3ffc18b4b915ae70d1aadb5b1b69e433546ebfb2599e99311783928837a`
* `evidence.json` (1169 bytes)
  Artifact ID: `art_7bc1767421d5`
  `SHA-256`: `2fa9368906c0e7fd6e490d244ab97b2dfff79f6f9cf0bd90521b21ca94e153e1`
* Captured Screenshots:
  * `artifacts/task_selection.png`: Task selection view with `TASK-091` selected and sequential repair strategy chosen
  * `artifacts/run_progress.png`: Live execution progress showing Server Sent Events stream and pipeline stages
  * `artifacts/live_run_results.png`: Full page verification report displaying 1/1 tests passing, 0 regressions, and change manifest
  * `artifacts/live_run_reloaded.png`: Reloaded verification view proving complete state hydration from remote Turso

## Independent Reproduction Proof

The downloaded `patch.diff` artifact was independently reproduced outside the application runtime:

1. Cloned `https://github.com/SGOD-pro/repo-medic.git` into a fresh temporary workspace in `/tmp`.
2. Checked out the pinned target commit `453a0b6c6b125177504cdd941902b8d48266ed1c`.
3. Created an isolated virtual environment and installed `sqlalchemy==2.0.19` and `pytest`.
4. Executed `pytest tests/` before patch: confirmed reproduction of `AttributeError: 'Engine' object has no attribute 'execute'` with exit code 1.
5. Applied the exact downloaded `patch.diff` via `git apply --recount --whitespace=nowarn`.
6. Inspected git diff: only `src/backend/database.py` modified, 0 test files altered.
7. Executed `pytest tests/ -v` after patch: 1/1 tests passed cleanly with exit code 0.

## Verdict

LOCAL FULL E2E PASSED:
Browser workflow execution, live Nebius sandbox and model completion, UI artifact downloads, remote Turso reload persistence, and independent patch reproduction all passed without errors.
