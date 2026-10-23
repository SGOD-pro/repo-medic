# 0006. Live provider integration and sequential repair

**Date**: 2026-10-22
**Status**: Accepted

## Summary

This specification defines how RepoMedic integrates live artificial intelligence models and isolated remote sandboxes for milestone K4. It replaces simulated responses with live Nebius Token Factory completions and ConTree sandbox containers when a run specifies live execution mode. The engine enforces explicit adapter selection with zero fallback to fakes, failing closed immediately if live credentials are missing or provider operations fail. This enables one verified sequential repair of a pinned repository while keeping provider spend strictly inside bounded budget caps.

## Requirements

**User stories**:
- As an operator initiating a live repair run, I want explicit live adapter selection without silent fake fallback so that I can be certain all model inferences and test executions run against real external providers.
- As an operator managing cloud budgets, I want strict per run and global budget caps atomically reserved before every provider call so that total spend never exceeds our twenty five dollar limit.
- As a reviewer evaluating generated repairs, I want fresh candidate verification inside isolated sandbox snapshots so that candidate patches are proven against real test runners without environment drift.

**Acceptance criteria**:
- **AC-1**: Explicit live adapter selection: When `run.mode == "live"`, `QueueWorker` and the repair engine select live `TokenFactoryModelAdapter` and `ConTreeSandboxAdapter`. If mode is live and any required credential (`TOKEN_FACTORY_API_KEY`, `NEBIUS_API_KEY`, `NEBIUS_PROJECT_ID`) is missing, execution halts immediately in terminal state `failed` with an informative error reason and zero fallback to fakes.
- **AC-2**: ConTree sandbox SDK integration: The live sandbox adapter wraps the official asynchronous `contree-sdk` client (`Contree`), managing remote container lifecycles from the base container image configured in `NEBIUS_SANDBOX_IMAGE` (`python:3.12-bookworm`, ensuring git and compilation tools are preinstalled).
- **AC-3**: Pinned repository preparation: Inside the sandbox container, the repository specified by `recipe.repository_url` is cloned and checked out at the exact `recipe.commit_sha` with `GIT_TERMINAL_PROMPT=0`. The working tree commit is verified with `git rev-parse HEAD`, and dependencies are installed for the base version.
- **AC-4**: Baseline stability double check: Baseline tests execute twice in the prepared sandbox environment. Both executions must return exit code zero and identical test collection counts parsed from pytest execution output. If baseline fails or is unstable, the run fails immediately.
- **AC-5**: Dependency upgrade and failure reproduction: The sandbox updates the target dependency to `recipe.to_version` and executes tests. The sandbox queries installed package metadata via `python -c "import <pkg>; print(<pkg>.__version__)"` to record `installed_version`, and verifies the failure output contains `recipe.expected_failure`.
- **AC-6**: Immutable snapshot checkpointing: Upon successful upgrade reproduction, the sandbox image state is captured as a named snapshot checkpoint UUID (`disposable=False`) via `capture_checkpoint()`. Candidate evaluations branch off this checkpoint as ephemeral executions (`disposable=True`).
- **AC-7**: Live model candidate generation: The live model adapter invokes `nvidia/nemotron-3-super-120b-a12b` via Nebius Token Factory chat completions with zero SDK retries and bounded token limits.
- **AC-8**: Patch safety validation and injection: The generated patch is strictly validated against `recipe.allowed_source_paths` and path traversal attacks before sandbox application. The sandbox uploads the patch file via `apply_patch()` and executes `git apply /tmp/candidate.patch`.
- **AC-9**: Fresh verification and tamper detection: Candidate patches are applied to fresh ephemeral sandbox instances branching from the upgrade snapshot. File hashes (`hash_files`) are compared against baseline, explicitly excluding `.git`, `__pycache__`, and `.pytest_cache` directories, to guarantee test files were not modified.
- **AC-10**: Atomic budget reservation and settlement: Before each model call, 0.05 USD is atomically reserved via `host.reserve()`. Before baseline/upgrade setup, 0.20 USD is atomically reserved; before candidate verification, 0.10 USD is atomically reserved. After completion, actual usage is settled with `host.settle()`. If reservations exceed `max_run_usd` (2.00 USD) or the global ceiling (25.00 USD), the run fails closed.
- **AC-11**: Responsive cancellation: Between each major pipeline phase (baseline, upgrade, model generation, verification), `host.cancelled()` is checked. If cancellation is signaled, the run halts cleanly in state `cancelled`.
- **AC-12**: Guaranteed sandbox resource cleanup and remote TTL: The live sandbox adapter implements an asynchronous `cleanup()` method wrapped in a `finally` block in worker execution, terminating remote sandbox containers and snapshots on success, failure, timeout, or cancellation. All container executions configure a remote timeout of 600 seconds to protect against orphaned cloud resources.
- **AC-13**: Preflight provider inspection CLI: `scripts/preflight_check.py --live-providers` validates provider credentials, endpoint URLs, required packages, and executes lightweight connectivity checks offline before any live run is scheduled.

## Decision

**Chosen option**: Option 1: Live ConTree sandbox and Token Factory model adapters with explicit selection, snapshot branching, structured metadata parsing, and fail closed budget enforcement.

RepoMedic connects directly to Nebius Token Factory and ConTree Sandbox SDK when running in live mode. It completely disallows fake fallback for live runs, structures execution around immutable image checkpoints, provides explicit patch injection and snapshot capture, and guarantees clean teardown across all terminal states.

## Rationale

See [rationale.md](rationale.md) for full context, options considered, and tradeoff analysis.

## Feature design

### Component architecture

The K4 integration introduces the live sandbox adapter and connects live adapters into the worker execution loop:

```
+-------------------------------------------------------------------------------+
|                                 QueueWorker                                   |
|                                                                               |
|  Claim run (mode="live") to Validate credentials to Resolve live adapters     |
+-------------------------------------------------------------------------------+
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
+-----------------------------+                           +---------------------+
|   TokenFactoryModelAdapter  |                           |ConTreeSandboxAdapter|
|                             |                           |                     |
| Chat completions via HTTP   |                           | Wraps Contree async |
| Zero SDK automatic retries  |                           | Snapshot checkpoints|
| Model: Nemotron-3 Super     |                           | Ephemeral branches  |
+-----------------------------+                           +---------------------+
         |                                                         |
         v                                                         v
Nebius Token Factory API                                  Nebius ConTree Service
```

### Sandbox protocol extension

The `SandboxAdapter` protocol in `backend/src/engine/adapters.py` is extended with explicit operations:

```python
class SandboxAdapter(Protocol):
    async def execute_command(
        self, command: List[str], timeout_seconds: int = 60
    ) -> CommandResult: ...

    async def create_execution(
        self, checkpoint_id: str
    ) -> "SandboxAdapter": ...

    async def apply_patch(
        self, diff_content: str
    ) -> CommandResult: ...

    async def capture_checkpoint(
        self, tag: Optional[str] = None
    ) -> str: ...

    async def cleanup(self) -> None: ...

    async def hash_files(
        self, paths_or_patterns: Optional[List[str]] = None
    ) -> Dict[str, str]: ...
```

### Sandbox lifecycle and checkpoint progression

1. **Base provision**: Initialize asynchronous `Contree` client using `NEBIUS_API_KEY` and `NEBIUS_PROJECT_ID`. Resolve base image from `NEBIUS_SANDBOX_IMAGE` (`python:3.12-bookworm`).
2. **Repository setup**: Execute `git clone <repository_url>`, `git checkout <commit_sha>` with `GIT_TERMINAL_PROMPT=0`, verify `git rev-parse HEAD == commit_sha`, and run dependency installation (`pip install -r requirements.txt`).
3. **Baseline verification**: Run `pytest tests/` twice. Parse terminal output for collected test counts, and assert exit code zero and matching counts across both executions.
4. **Upgrade reproduction**: Run `pip install <dependency>==<to_version>`. Query `python -c "import <pkg>; print(<pkg>.__version__)"` to record installed version. Execute `pytest tests/` and verify failure output contains `expected_failure`.
5. **Snapshot checkpoint**: Invoke `capture_checkpoint()` on the adapter (`disposable=False`). Capture the resulting immutable image UUID as `checkpoint_id`.
6. **Candidate evaluation**: For candidate verification, invoke `create_execution(checkpoint_id)`. The adapter creates an ephemeral execution instance (`disposable=True`). Call `apply_patch(candidate.diff_content)`, run verification command, verify test collection counts and test node identifiers match baseline, and hash source files excluding `.git`, `__pycache__`, and `.pytest_cache` to ensure tests were not altered.
7. **Cleanup**: Explicitly call `cleanup()` on the adapter in a `finally` block to terminate active sessions and remove intermediate images. All remote execution calls configure a 600 second safety timeout.

### Data model

The existing Cloudflare D1 schema fully supports K4 without alterations:
- `runs`: Stores execution mode (`mode="live"`), search strategy (`search_mode="sequential"`), and terminal states.
- `tasks`: Holds curated task recipes including pinned `repository_url`, `commit_sha`, and `expected_failure`.
- `events`: Captures chronological execution envelopes for baseline, upgrade, and verification stages.
- `artifacts`: Persists patch diffs, container logs, and verification evidence manifests.
- `budget_reservations`: Tracks per operation reservations with `provider_ref` linkage and settled micro dollar amounts.

### API surface

Existing public and worker endpoints remain unchanged:
- `POST /api/runs`: Submits run with `mode="live"`, `search_mode="sequential"`.
- `GET /api/runs/:run_id`: Inspects run state and budget consumption.
- `POST /api/runs/:run_id/cancel`: Triggers responsive run cancellation.
- `GET /api/runs/:run_id/events`: Streams execution timeline events.

### Value sourcing

| Action | Value produced or displayed | Source |
|---|---|---|
| Initialize live sandbox | Container image handle | `NEBIUS_SANDBOX_IMAGE` configuration setting |
| Clone target repository | Working tree source files | `recipe.repository_url` and `recipe.commit_sha` |
| Record upgraded version | Installed package version string | Sandbox command `python -c "import <pkg>; print(<pkg>.__version__)"` |
| Parse test collections | Collected, passed, failed test counts | Structured output parser of pytest terminal summary |
| Capture snapshot checkpoint | Checkpoint image UUID | ConTree image UUID returned by `capture_checkpoint()` |
| Inject candidate patch | Patch application exit code and stderr | `apply_patch()` uploading diff to `/tmp/candidate.patch` |
| Generate candidate patch | Unified git diff proposal | `TokenFactoryModelAdapter.complete()` output |
| Validate patch boundaries | Validation result boolean | Syntax analysis against `recipe.allowed_source_paths` |
| Verify candidate patch | Execution result and file hashes | Ephemeral execution in sandbox branching from `checkpoint_id` |
| Settle budget reservations | Settled micro USD | Flat fee per phase or actual container duration settlement |

### Key invariants

- Live execution mode never falls back to fakes. If any credential or provider operation is unavailable, the run fails closed immediately.
- Spend cannot exceed 2.00 USD per run or 25.00 USD globally across all runs.
- Sandbox candidate execution occurs strictly in isolated ephemeral instances branching from immutable checkpoint snapshots.
- Test files and runner configurations must not be altered by candidate patches. Any modification detected via file hashing rejects the candidate immediately.
- Execution cache directories (`.git`, `__pycache__`, `.pytest_cache`) are excluded from file hash comparison.

### Security model

- Provider API credentials (`NEBIUS_API_KEY`, `TOKEN_FACTORY_API_KEY`) are read from environment variables or `.env` and are strictly sanitized from error messages and logs.
- Sandbox execution runs in remote containers isolated from the host server. No host filesystem mounts or host network sockets are shared.
- Task recipes only clone pinned repositories and explicit commit SHAs. Arbitrary repository URLs from untrusted sources are disallowed.

### Configuration required

- `REPOMEDIC_MODE`: Execution mode, set to `"live"` for live provider runs.
- `TOKEN_FACTORY_API_KEY`: Authentication key for Nebius Token Factory model completions.
- `TOKEN_FACTORY_BASE_URL`: Inference endpoint URL (`https://api.tokenfactory.us-central1.nebius.com/v1/`).
- `TOKEN_FACTORY_MODEL`: Inference model identifier (`nvidia/nemotron-3-super-120b-a12b`).
- `NEBIUS_API_KEY`: Authentication key for Nebius ConTree Sandbox SDK.
- `NEBIUS_PROJECT_ID`: Cloud project identifier for sandbox resource allocation.
- `NEBIUS_SANDBOX_IMAGE`: Base container image for sandboxes (`python:3.12-bookworm`).
- `REPOMEDIC_MAX_RUN_USD`: Maximum spend allowed per individual run (2.00 USD).
- `REPOMEDIC_TOTAL_BUDGET_USD`: Total global spend budget ceiling (25.00 USD).

### Critical test scenarios

- **Happy path sequential repair**: With live credentials configured, run sequential repair on a pinned repository task. Proves baseline double check passes, upgrade reproduces regression, model produces valid patch, verification passes in fresh sandbox, and artifacts are stored. Verifies **AC-1** through **AC-10**, **AC-12**.
- **Missing credentials fail closed**: Run with `mode="live"` when `NEBIUS_API_KEY` is empty. Execution aborts immediately in state `failed` with zero fake fallback. Verifies **AC-1**.
- **Per run budget rejection**: Attempting reservations exceeding 2.00 USD rejects with HTTP 409 and transitions run to `failed`. Verifies **AC-10**.
- **Global budget rejection**: When cumulative reservations reach 25.00 USD ceiling, subsequent reservations fail closed. Verifies **AC-10**.
- **Responsive cancellation**: Issuing run cancellation during sandbox execution halts further stages and terminates the remote sandbox. Verifies **AC-11**, **AC-12**.
- **Tampered test rejection**: Candidate patch attempting to modify a test file or collection configuration is rejected by verifier hash check. Verifies **AC-8**, **AC-9**.
- **Cache noise immunity**: Verifier hash comparison confirms that generated pytest cache files do not trigger false positive tamper alerts. Verifies **AC-9**.

## Build plan

1. Add `contree-sdk` dependency to `backend/pyproject.toml` and extend `backend/src/preflight.py` with provider preflight verification, satisfies **AC-1**, **AC-13**
2. Extend `SandboxAdapter` protocol in `backend/src/engine/adapters.py` with `apply_patch` and `capture_checkpoint`, and implement `ConTreeSandboxAdapter` in `backend/src/engine/contree_sandbox.py`, satisfies **AC-2**, **AC-6**, **AC-8**, **AC-12**
3. Implement live adapter resolver in `backend/src/worker.py` and engine `repair()` enforcing fail closed live selection with zero fake fallback, satisfies **AC-1**, **AC-7**, **AC-8**
4. Implement pinned repository preparation, baseline verification, and package version inspection routines in `ConTreeSandboxAdapter`, satisfies **AC-3**, **AC-4**, **AC-5**
5. Wire atomic budget reservations, cache path hash filtering, and responsive cancellation checks across live model and sandbox lifecycles, satisfies **AC-9**, **AC-10**, **AC-11**, **AC-12**
6. Create pinned fixture repository recipe and offline unit test suite with mock ConTree SDK responses in `backend/tests/engine/test_contree_sandbox.py`, satisfies **AC-2**, **AC-3**, **AC-6**, **AC-8**, **AC-9**, **AC-12**
7. Execute operator gated live sequential repair test script validating end to end live execution against real Nebius and ConTree endpoints, satisfies **AC-1** through **AC-12**

## Consequences

**Positive**:
- Validates the entire RepoMedic repair pipeline end to end against real external inference and container runtimes.
- Proves actual dependency upgrade regressions can be identified, patched, and verified automatically.
- Enforces strict spend bounds that protect team allocations from runaway loops.
- Structured output parsing and explicit patch injection eliminate execution ambiguity.

**Negative / tradeoffs**:
- Live remote sandbox operations incur network latency and container startup overhead compared to instant in memory fakes.
- Requires active cloud credentials and quota on Nebius Token Factory and ConTree platforms.

**Neutral**:
- Zero database migrations or schema alterations required.
- Offline tests remain fully functional with zero reliance on external network connectivity or paid API keys.

## Follow-up

- [ ] Operator provisions live Nebius API key and project identifier.
- [ ] Run `python scripts/preflight_check.py --live-providers` to confirm credential readiness.
- [ ] Execute single live sequential repair milestone before commencing branch and refine search integration.
