# 0003. Safe verifier and evidence · Rationale

## Context

When automated repair engines evaluate generated patches, a common failure mode is declaring success on an invalid, partial, or deceptive repair. Large language models frequently attempt to resolve test failures by altering test files, deleting failing test assertions, adding skip decorators, or modifying test runner configuration. Without strict verification invariants, an automated pipeline can accept a patch that appears to pass while having silenced the very tests intended to guard system correctness.

Furthermore, running candidate verification in the same execution environment where upgrade commands, failure reproduction, and patch generation occurred introduces state contamination. Background processes, residual files, mutated site packages, or modified configuration from earlier steps can mask regressions or produce false positive verification results. Relying on git checkout or git clean is insufficient because git operations do not reset installed Python packages, environment variables, or lingering filesystem changes.

Finally, verification evidence must be auditable, structured, and resilient. If verification tests pass but artifact persistence fails silently, operators and evaluation benchmarks receive a success signal without the evidence required to inspect or reproduce the fix. The verifier must persist a structured manifest (`evidence.json`), the patch diff, and the test execution log, while treating artifact storage failures as a hard block against declaring a candidate verified.

## Options considered

### Option 1: Immutable checkpoint execution with three point hash invariants and typed evidence manifest

Under this option, the sandbox adapter provisions an independent execution handle derived from the immutable upgraded checkpoint for each candidate evaluation. The verifier verifies test and configuration file hashes at three checkpoints (pre patch, post patch, post test) and compares pytest collected node identifiers against the baseline set. A typed `EvidenceManifest` is serialized to `evidence.json`, and failure to persist required artifacts marks verification as failed with an explicit `artifact_persistence_failed` reason.

**Pros**:
- Guarantees complete execution isolation with zero state leakage from prior stages.
- Detects test tampering, assertion removal, and pytest collection suppression.
- Provides a structured, machine readable evidence record for offline audit and evaluation.
- Prevents declaring success when durable artifacts fail to save.

**Cons**:
- Requires computing sha256 hashes of test files and running an additional pytest collection command.

### Option 2: In place sandbox cleanup with git reset and basic test output parsing

Under this option, the engine reuses the existing sandbox instance from the upgrade stage, runs git checkout and git clean to reset the tree, applies the patch, and inspects only exit codes and collected test counts from standard test output.

**Pros**:
- Avoids implementing checkpoint execution handles on sandbox adapters.
- Slightly faster execution by omitting explicit file hashing.

**Cons**:
- Fails to reset mutated Python packages, lingering cache files, or background processes.
- Vulnerable to deceptive patches that delete tests or introduce skip decorators while preserving total counts.
- Produces no structured evidence manifest for downstream audit or replay.

### Option 3: External container provisioner with cryptographic attestation

Under this option, the verifier spins up full isolated Docker containers or VM instances for each candidate and computes asymmetric cryptographic signatures over evidence artifacts.

**Pros**:
- Provides OS level kernel isolation between candidate evaluations.
- Implements tamper evident cryptographic signatures on exported evidence.

**Cons**:
- Introduces excessive runtime overhead and dependency on container daemons.
- Overcomplicates offline testing and exceeds the requirements for Package C engine responsibilities.
- Shared contract changes and cryptographic signing are not needed for this slice.

## Rationale

Option 1 is selected because it delivers rigorous verification correctness without unnecessary external infrastructure.

Reusing dirty execution environments (Option 2) introduces subtle bugs where package side effects or lingering bytecode files produce false passes. Creating a fresh execution handle from the immutable upgraded checkpoint guarantees that each candidate starts from an identical, clean baseline state.

Evaluating only test exit codes is inadequate against language models capable of modifying test code. Enforcing identical test node identifiers and three point hash checks (pre patch, post patch, post test) guarantees that the test suite remains completely intact.

Persisting a typed `EvidenceManifest` ensures that Repo Medic produces verifiable proof of repair. Gating success on artifact storage prevents silent evidence loss, while preserving the actual test results in the outcome record ensures operators know the test suite passed even if host storage failed.

## References

**Project sources**:
- `AGENTS.md`: team ownership boundaries and architectural guidelines.
- `backend/src/engine/AGENTS.md`: conventions for engine logic, baseline double check, and fake provider adapters.
- `docs/specs/0001-provider-fakes-and-baseline/index.md`: baseline double check runner and adapter protocols.
- `docs/specs/0002-sequential-repair/index.md`: sequential repair loop and initial verification runner.
- `backend/src/engine/adapters.py`: SandboxAdapter and ModelAdapter interface definitions.

**Practices & standards**:
- Immutable checkpoint isolation for deterministic test execution.
- Defense in depth test preservation via cryptographic file hashing and test collection node matching.
- Structured manifest auditing for automated repair evaluation.
- Explicit failure classification distinguishing test regression from infrastructure storage failure.
