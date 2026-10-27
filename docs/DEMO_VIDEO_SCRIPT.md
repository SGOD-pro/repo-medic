# RepoMedic Submission Demo Video Script

## Overview

* Target Duration: 2 minutes 30 seconds
* Application Target: `TASK-091` (Upgrade sqlalchemy from 1.4.48 to 2.0.19)
* Live Providers: Nebius Token Factory (`nvidia/nemotron-3-super-120b-a12b`), Nebius ConTree Sandbox (`python:3.12-bookworm`), and remote Turso libSQL database
* Public Deployment: Vercel frontend at `https://repo-medic-gamma.vercel.app` and AWS Lambda HTTP API with SQS queue worker

## Scene Breakdown

### Scene 1: Introduction and Problem Overview (0:00 to 0:30)

* Visual: Open the RepoMedic public dashboard at `https://repo-medic-gamma.vercel.app`. Show the task discovery grid displaying available upgrade challenges.
* Narration:
  "Welcome to RepoMedic, an autonomous dependency upgrade and self repair engine. Upgrading core libraries often breaks production code due to breaking API removals. Here, we see curated benchmark tasks pinned to real repository commits. We focus on `TASK-091`, migrating sqlalchemy from version 1.4.48 to 2.0.19 in the official repository fixture."

### Scene 2: Configuration and Task Initiation (0:30 to 0:55)

* Visual: Click on `TASK-091`. Show the right hand sidebar with the pre flight summary: pinned commit SHA `453a0b6c6b125177504cdd941902b8d48266ed1c`, target dependency `sqlalchemy==2.0.19`, and budget ceiling. Select Sequential Direct strategy and click Start repair run.
* Narration:
  "The application runs on AWS Serverless with an SQS queue worker and remote Turso storage. When we launch the repair, a strict budget cap of two dollars is reserved. The run starts and transitions immediately to our live progress interface."

### Scene 3: Live Pipeline Execution (0:55 to 1:35)

* Visual: Show the active pipeline view. The Server Sent Events stream displays real time stage progression:
  1. Baseline Check: Verifying the pinned commit passes tests cleanly.
  2. Dependency Bump: Installing sqlalchemy 2.0.19 and capturing the intended failure: `AttributeError: 'Engine' object has no attribute 'execute'`.
  3. Candidate Synthesis: The Nebius Token Factory model generates a unified source diff.
  4. Post Upgrade Verification: Running pytest in an ephemeral Nebius ConTree microcontainer.
* Narration:
  "RepoMedic executes a four stage pipeline. First, baseline tests pass twice to verify stability. Next, bumping sqlalchemy to 2.0.19 confirms the expected engine execution error. Our live model then generates a targeted source patch. Finally, the patch is applied inside an isolated sandbox with the target dependency installed."

### Scene 4: Verification and Evidence Report (1:35 to 2:05)

* Visual: Click Inspect Results and Diff. Show the verification report with metric cards:
  * Tests Pass / Total: 1 / 1
  * 0 Regressions badge
  * Test files unchanged badge
  * Unified change manifest showing `src/backend/database.py` updated with `with engine.begin() as conn:`
  * Download buttons for `patch.diff`, `verify.log`, and `evidence.json`
* Narration:
  "The repair succeeded. All tests pass with zero regressions. Crucially, the test suite itself remained completely untouched, as confirmed by our post patch `SHA-256` hash checks. The change manifest highlights the clean fix, wrapping queries in the modern engine begin context."

### Scene 5: Persistence and Independent Reproduction (2:05 to 2:30)

* Visual: Reload the browser page at the run URL to show instant hydration from remote Turso. Transition to the terminal to show `git apply` of the downloaded patch and `pytest` passing on a fresh clone.
* Narration:
  "Reloading the page proves full persistence from remote Turso libSQL. To guarantee integrity, we independently applied the downloaded patch against a clean clone of the repository, confirming the test suite passes with exit code zero. RepoMedic delivers provable, deterministic dependency repairs on deployed cloud infrastructure."
