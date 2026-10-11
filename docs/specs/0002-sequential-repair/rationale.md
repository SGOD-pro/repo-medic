# Rationale: 0002. Sequential repair loop

## Context

Following completion of spec 0001 (provider fakes and baseline stage), the repair engine must implement Slice C Feature 2: sequential dependency upgrade, candidate generation, patch validation, and verification.

Work package guidelines in docs/WORK_PACKAGE_C_ENGINE.md specify that candidate generation must start with a single sequential candidate before moving to tree search. Every operation must run offline against deterministic fake providers in checkpoint K1, reserving live provider credentials and real Nebius Token Factory calls for checkpoint K4.

The user clarified key operational choices:
1. Upgrade verification must confirm both package installation and reproduction of expected failure indicators.
2. Error extraction should use regex matching on tracebacks and file names, falling back to execution logs when regex extraction finds nothing.
3. Patch safety must be strictly enforced by parsing unified diffs and rejecting changes outside allowed source paths or modifying test files, configs, or lockfiles.
4. Candidate verification must run on a clean sandbox environment, comparing test collection counts, skip counts, and dependency versions against baseline evidence.
5. Offline fakes must drive test suites first, with clean adapter interfaces ready to accept Nebius API keys when live mode is configured.

## Options considered

### Option 1: Modular stage pipeline with strict diff validation and fresh sandbox verification (Recommended)

Structure the sequential repair loop into dedicated, composable stage modules:
- Upgrade runner verifying package version and reproduction of failure output.
- Regex error context extractor with bounded log fallback.
- Candidate generator enforcing budget reservations and token caps.
- Strict diff validator rejecting unauthorized paths before sandbox modification.
- Verifier runner enforcing clean sandbox state, collection consistency, and artifact persistence.

**Pros**:
- Each stage is independently unit testable with specific failure modes.
- Strict security model blocks prompt injections and unsafe patches before sandbox modification.
- Deterministic fake presets enable thorough offline test suites with zero cloud spend.
- Seamlessly transitions to live Nebius adapters when operator credentials are provided.

**Cons**:
- Requires several focused helper files in backend/src/engine/.

### Option 2: Monolithic repair function without dedicated stage helpers

Implement the entire sequential flow in a single repair routine inside repair.py, performing upgrade, model prompt formatting, patch application, and verification inline.

**Pros**:
- Fewer internal files.

**Cons**:
- Difficult to unit test failure branches in isolation (e.g. upgrade failure versus patch validation failure).
- Harder to reuse verifier logic in subsequent branch and refine stages.
- Higher risk of state leakage between candidate attempts.

### Option 3: Direct live provider execution without offline fake presets

Connect live Nebius Token Factory and sandbox APIs directly, requiring live API credentials for unit tests and local development.

**Pros**:
- Eliminates fake preset maintenance.

**Cons**:
- Violates K1 milestone rules in docs/PHASES.md requiring zero credit consumption.
- Makes local unit tests dependent on network availability, remote credentials, and paid quotas.
- Fails when developers or CI systems lack active provider keys.

## Rationale

We selected Option 1 because it satisfies all architectural requirements in docs/ARCHITECTURE.md, docs/WORK_PACKAGE_C_ENGINE.md, and docs/PHASES.md.

Separating upgrade, generation, validation, and verification into discrete helpers allows comprehensive test coverage across every failure mode:
1. Verifying that the upgraded dependency reproduces the expected failure prevents the engine from attempting repairs on incorrect environments.
2. Regex based error extraction keeps prompt context compact and focused, avoiding prompt bloat while retaining high quality error traces.
3. Parsing unified diff headers directly guarantees that only authorized source files are modified, safeguarding test suites and configuration from unauthorized edits.
4. Testing in a fresh clean sandbox ensures that a candidate patch cannot pass simply because artifacts or state leaked from a prior execution.
5. Providing configurable fake presets in FakeSandboxAdapter and FakeModelAdapter allows offline tests to execute swiftly and reliably, while adhering to the ModelAdapter and SandboxAdapter protocol interfaces that Nebius adapters will satisfy.

## References

- docs/PROJECT.md: product context and repair objectives
- docs/PRD.md: provider details and sequential candidate requirements
- docs/ARCHITECTURE.md: adapter boundaries and engine host ports contracts
- docs/PHASES.md: checkpoint milestones, budget caps, and offline testing requirements
- docs/WORK_PACKAGE_C_ENGINE.md: work package C engine responsibilities and acceptance checks
- docs/specs/0001-provider-fakes-and-baseline/index.md: baseline verification stage and adapter protocols
