# Live Acceptance Report

## Summary

This report documents the live provider acceptance verification for RepoMedic on deployed cloud infrastructure using the validated TASK-091 fixture.
All repair and verification steps executed with real cloud providers, AWS Serverless architecture, Vercel frontend hosting, and remote Turso database persistence.

## Execution and Version Identifiers

### Deployed Production Execution

* Application Execution Commit: `328e733`
* Frontend Public URL: `https://repo-medic-gamma.vercel.app`
* Backend Public API URL: `https://oflqusaa1e.execute-api.ap-south-1.amazonaws.com`
* AWS SAM Stack: `repo-medic` in AWS region `ap-south-1`
* Target Repository: `https://github.com/SGOD-pro/repo-medic.git`
* Target Commit SHA: `453a0b6c6b125177504cdd941902b8d48266ed1c`
* Task Identifier: `TASK-091` (Upgrade sqlalchemy from 1.4.48 to 2.0.19)
* Demo Repository Status: Dedicated demo repository registration is pending; registered approved TASK-091 fixture used.
* Live Run Identifier: `run_08ae760f834140b18b03605d1adcd22d`
* Terminal State: `succeeded`
* Browser Verification URL: `https://repo-medic-gamma.vercel.app/?runId=run_08ae760f834140b18b03605d1adcd22d`
* Repair Strategy: Sequential direct repair

### Saved Validated Run Reference

* Saved Live Run Identifier: `run_93c660238e3443a6a18249167eb1939b`
* Saved Browser URL: `https://repo-medic-gamma.vercel.app/?runId=run_93c660238e3443a6a18249167eb1939b`
* Saved State: `succeeded`

## Provider Configuration

* Model Inference Provider: Nebius Token Factory
* Model Name: `nvidia/nemotron-3-super-120b-a12b`
* Sandbox Execution Provider: Nebius ConTree Sandbox
* Container Image: `python:3.12-bookworm`
* Database Storage: Remote Turso database
* Database URL: `libsql://repo-medic-swyra-07.aws-ap-south-1.turso.io`
* Storage Backend: `turso` (LibSQL client)
* Backend Architecture: AWS HTTP API Gateway proxying to AWS Lambda with asynchronous SQS queue worker
* Frontend Architecture: Vercel serverless deployment with proxy rewrites to AWS API

## Pipeline Verification Results

1. Baseline Stage: Passed cleanly twice (1/1 tests passing on pinned commit 453a0b6c6b125177504cdd941902b8d48266ed1c).
2. Upgrade Stage: Failed as expected when upgrading sqlalchemy to 2.0.19 with AttributeError Engine object has no attribute execute.
3. Candidate Generation: Generated single pass repair candidate modifying src/backend/database.py (9 additions, 7 deletions) wrapping engine queries in engine.begin connection context.
4. Sandbox Verification: Pytest in clean ephemeral microcontainer passed cleanly (1 passed, 0 failed, 0 regressions).
5. Post Test Checks: Zero new skips, collection node ids preserved, dependency sqlalchemy 2.0.19 verified in site packages, test file post patch hash matching SHA-256 baseline.
6. Execution Metrics: Verification duration 8.8s, model calls 1, input tokens 613, output tokens 1651, estimated cost $0.35 USD within the $2.00 run budget ceiling.
7. Browser Diagnostics: 0 browser console errors, 0 failed network requests during smoke and run checks.

## Artifact Integrity and Hashes

All run artifacts are persisted in remote Turso storage:

* `patch.diff` (816 bytes)
  Artifact ID: `art_272bf1ffe309`
  SHA-256: `29fc61f36d821d72a47df0a5c2824a3c2665cac0882af0707ec986147a8c7e50`
* `verify.log` (358 bytes)
  Artifact ID: `art_2c5820e63606`
  SHA-256: `3899400b48af5b417b23bf70ab72224603f70e2168e9ea1792c023cbd337bdbb`
* `evidence.json` (1169 bytes)
  Artifact ID: `art_6cf1a5e49035`
  SHA-256: `cf91d105c48e657b8d8f2c83b440a499fb573ce308c524496ac89952bbc208bf`
* Captured Screenshots:
  * `artifacts/deployed_saved_run_acceptance.png`: Hydrated saved benchmark run acceptance view
  * `artifacts/deployed_task_selection.png`: Public task discovery view with TASK-091 selected
  * `artifacts/deployed_live_task_selected.png`: Public repair configuration pane before run execution
  * `artifacts/deployed_live_run_completed.png`: Public live execution terminal state showing 4/4 stages complete
  * `artifacts/deployed_live_run_results.png`: Public verification view displaying 1/1 tests passing and diff

## Independent Reproduction Proof

The downloaded patch.diff artifact was independently reproduced outside the application runtime:

1. Cloned https://github.com/SGOD-pro/repo-medic.git into a fresh temporary workspace in /tmp.
2. Checked out the pinned target commit 453a0b6c6b125177504cdd941902b8d48266ed1c.
3. Created an isolated virtual environment with uv and installed sqlalchemy==2.0.19 and pytest.
4. Executed pytest tests before patch: confirmed reproduction of AttributeError Engine object has no attribute execute with exit code 1.
5. Applied the exact downloaded patch.diff via git apply.
6. Inspected git diff: only src/backend/database.py modified, 0 test files altered.
7. Executed pytest tests after patch: 1/1 tests passed cleanly with exit code 0.

## Verdict

PUBLIC DEPLOYED E2E PASSED:
Public browser workflow, AWS Lambda API and SQS worker execution, live Nebius Token Factory inference and ConTree sandbox microcontainer execution, Vercel proxy transport, remote Turso persistence, and independent patch reproduction all passed without errors.
