# 0006. Live provider integration and sequential repair: Rationale

## Context

RepoMedic has validated offline pipeline mechanics, database persistence, and bounded branch search using simulated provider fakes across milestones K0 through K3. Milestone K4 transitions the repair engine to real external infrastructure: Nebius Token Factory for chat completions and ConTree Sandbox for remote execution.

Connecting real providers introduces operational hazards that offline simulation tests cannot fully reproduce:
1. Model completions and sandbox execution generate real cloud expenses that must remain strictly inside team budget caps.
2. Silent fallbacks to simulated responses during live runs could mask authentication failures, giving operators a false impression of success.
3. Network interruptions, rate limits, or container provisioning errors must not leave orphan compute resources running indefinitely or corrupt state in Cloudflare D1.
4. Repositories must be pinned to exact commit hashes so that test suites run against reproducible baseline environments.

Establishing explicit adapter selection, fail closed credential checks, immutable sandbox snapshots, and guaranteed cleanup ensures that live testing proceeds safely and reliably.

## Options considered

### Option 1: Explicit live adapters with ConTree SDK, snapshot checkpointing, and fail closed selection (Chosen)

This option implements a dedicated `ConTreeSandboxAdapter` wrapping `contree-sdk`, connects the existing `TokenFactoryModelAdapter`, and enforces strict mode switching in `QueueWorker`. Live runs require valid credentials and fail closed immediately if any credential is missing or unverified. Sandbox execution leverages snapshot checkpointing to branch candidate verifications from an immutable upgraded baseline image.

**Pros**:
- Guarantees complete fidelity by running tests and model completions on real provider infrastructure.
- Snapshot checkpoints isolate candidate evaluation from environment drift and ensure baseline runs are never polluted.
- Fail closed enforcement eliminates the risk of silent fake fallback during live verification runs.
- Automatic cleanup in `finally` blocks prevents abandoned container instances and unexpected billing.

**Cons**:
- Requires active cloud credentials and network access for live test runs.
- Container snapshot and provisioning operations add latency compared to local in memory execution.

### Option 2: Automatic fallback to simulated fakes when live credentials are absent

Under this approach, if a live run is initiated but provider credentials or network access fail, the engine falls back to simulated fake adapters and logs a warning.

**Pros**:
- Avoids test crashes when running in environments with partial or absent credentials.

**Cons**:
- Defeats the primary purpose of live integration testing by obscuring infrastructure defects.
- Creates dangerous ambiguity where operators cannot distinguish whether a repair succeeded on a real cloud model or in simulated memory.
- Violates core project safety rules requiring explicit mode selection.

### Option 3: Local Docker container execution instead of remote ConTree sandboxes

This option would run candidate evaluations in local Docker containers on the host machine rather than using remote Nebius ConTree sandboxes.

**Pros**:
- Removes reliance on the external ConTree cloud service and network availability.
- Lowers execution latency for local container operations.

**Cons**:
- Fails to validate the real Nebius ConTree sandbox environment mandated by the project architecture.
- Requires Docker daemon access on the host, introducing local environment discrepancies and security risks.
- Does not test the actual ConTree SDK APIs and token lifetimes planned for production deployment.

## Rationale

Option 1 is selected because it strictly satisfies the milestone K4 requirements without compromising security, observability, or budget compliance.

Silent fake fallback is fundamentally incompatible with verifiable acceptance: if an operator requests a live run, the system must either execute live against authentic providers or fail with a clear explanation. Wrapping `contree-sdk` with snapshot checkpointing mirrors the immutable tree search design specced in milestone K2, allowing candidate evaluations to run in parallel or sequence without shared mutable filesystem state.

Furthermore, enforcing atomic budget reservations before model completions (0.05 USD) and sandbox sessions (0.20 USD) guarantees that cumulative expenditures will never breach the team ceiling of 25.00 USD, even under unexpected pipeline retries or network errors.
