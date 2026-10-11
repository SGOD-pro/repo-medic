# Rationale: 0004. Bounded branch and refine search

## Context

Following the completion of sequential repair and safe candidate verification in specs 0002 and 0003, the repair engine requires bounded tree search capability for harder repairs. In many real world dependency regressions, an initial patch may fail due to a secondary assertion or a slight syntax error. In other cases, the initial hypothesis may be completely flawed, requiring exploration of an alternative branch.

Guidelines in docs/WORK_PACKAGE_C_ENGINE.md establish strict bounds for this capability:
1. Candidate search must be capped at at most three candidate branches.
2. Each candidate branch may receive at most one refinement attempt.
3. Every verification evaluation must run in a clean environment derived from an upgraded checkpoint, never reusing contaminated generation sandboxes or relying on git reset.
4. Token budgets and model generation limits must stay explicit, capping completions at 2048 tokens.
5. Search must never use language model votes or heuristics to override failed tests.
6. Cost must be reserved through HostPorts before each paid operation, with cancellation checked around remote calls and before accepting results.
7. Acceptance testing in checkpoint K1 must run entirely offline against deterministic fake providers with zero credit consumption.

## Options considered

### Option 1: Depth first search with immediate single refinement and checkpoint isolation (Recommended)

Explore branches sequentially in depth first order. When branch 1 candidate fails verification with actionable error logs, immediately prompt the model for refinement 1 incorporating the test failure output. If refinement 1 succeeds, stop search immediately. If refinement 1 fails, move to branch 2. Each verification executes in a fresh sandbox handle created via `create_execution(checkpoint_id)`.

**Pros**:
- Minimizes token consumption and overall latency on straightforward fixes by terminating upon the first passing candidate.
- Provides immediate feedback context for refinement while the error logs and diff are fresh.
- Enforces strict checkpoint isolation so that failed runs cannot leak state into subsequent candidate evaluations.
- Implements simple deterministic scheduling without complex asynchronous coordination or thread pools.

**Cons**:
- Does not explore branches in parallel, which is acceptable for offline testing and bounded single worker tasks.

### Option 2: Breadth first candidate generation with post verification reranking

Generate all three candidate branches up front, verify each in separate sandboxes, and then select failing candidates for refinement before ranking outcomes.

**Pros**:
- Collects multiple independent patch hypotheses before investing in refinements.

**Cons**:
- Wastes significant token and inference budget generating branches 2 and 3 when candidate 1 could succeed immediately.
- Increases provider reservation requirements up front, making budget management less granular.
- Complicates stopping logic and artifact collection.

### Option 3: Unbounded beam search with model based voting

Maintain a pool of top k candidates, generate multiple refinements per node, and ask a model to vote on the best candidates when test signals are ambiguous.

**Pros**:
- Maximizes search space exploration for research benchmarks.

**Cons**:
- Violates work package rules explicitly prohibiting model votes to override test verifier results.
- Exceeds the strict provider caps of 3 candidates and 1 refinement per candidate.
- Incurs unpredictable cloud costs and risks non deterministic repair outcomes.

## Rationale

We selected Option 1 because it strictly complies with the constraints in docs/WORK_PACKAGE_C_ENGINE.md and docs/PHASES.md while providing the highest efficiency.

In automated program repair, the majority of fixable issues either succeed on the first plausible patch or require a single refinement to adjust an import, signature, or assertion. By evaluating candidates in depth first order with immediate refinement, Repo Medic saves substantial provider quota on easy and medium tasks. Generating all branches up front would consume three times the token budget even when the first patch is fully correct.

Crucially, Option 1 enforces clean sandbox isolation across all candidate and refinement attempts. By provisioning an independent execution handle from the immutable upgraded checkpoint for every single verification attempt, candidates cannot accidentally pass or fail due to lingering files, modified dependencies, or intermediate build artifacts from previous attempts.

Budget reservations through host ports before each generation or refinement call ensure that search stops cleanly if cost thresholds are reached. Cooperative cancellation checks around all operations prevent orphaned background tasks.

## References

**Project sources**:
- `docs/WORK_PACKAGE_C_ENGINE.md`: work package C bounds capping search to 3 candidates and 1 refinement per candidate
- `docs/ARCHITECTURE.md`: engine adapter boundaries and HostPorts interaction contracts
- `docs/specs/0002-sequential-repair/index.md`: sequential repair loop baseline and patch validation
- `docs/specs/0003-safe-verifier-and-evidence/index.md`: immutable checkpoint execution and three point hash invariants

**Practices & standards**:
- Bounded depth first tree search with early termination for automated repair
- Checkpoint based isolated execution environments to prevent state contamination
- Granular budget reservation and settlement via host ports
