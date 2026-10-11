# Engine (Package C)

## Slice C: Engine implementation

### 1. Provider fakes and baseline · done
Fake models and execution host mapping to HostPorts.
**Done when:** The engine runs a successful baseline double check via fake providers.
- [x] Design it (spec): [0001](../specs/0001-provider-fakes-and-baseline/index.md)
- [x] Build it: /develop provider fakes and baseline
  - [x] Recipe validation and adapter interfaces (AC-1, AC-2, AC-3, AC-4)
  - [x] Fake provider implementations with preset behaviors (AC-3, AC-4)
  - [x] Baseline double check runner, repair wiring, and offline unit tests (AC-5, AC-6, AC-7, AC-8, AC-9, AC-10)
  code in `backend/src/engine/`
- [x] Verify it: /check verify provider fakes and baseline

### 2. Sequential repair · done
The core sequential upgrade and repair loop using candidate generation.
**Done when:** A single candidate is proposed and verified against the fake host.
- [x] Design it (spec): [0002](../specs/0002-sequential-repair/index.md)
- [x] Build it: /develop sequential repair
  - [x] Upgrade runner and error context extractor (AC-2, AC-3, AC-4)
  - [x] Candidate generator and patch safety validator (AC-5, AC-6, AC-7)
  - [x] Candidate verifier and artifact persistence (AC-8, AC-9)
  - [x] Repair pipeline wiring and offline unit tests (AC-1, AC-10, AC-11)
  code in `backend/src/engine/`
- [x] Verify it: /check verify sequential repair

### 3. Safe verifier and evidence · done
Verification of the patch against tests, and collection of evidence logs.
**Done when:** Verification proves the fix and writes complete evidence artifacts.
- [x] Design it (spec): [0003](../specs/0003-safe-verifier-and-evidence/index.md)
- [x] Build it: /develop safe verifier and evidence
  - [x] Data models and baseline preservation recorder (AC-1, AC-8)
  - [x] Checkpoint execution handle and sandbox adapter protocol (AC-2, AC-10)
  - [x] Invariant hash checks, collection matching, and evidence manifest persistence (AC-3, AC-5, AC-8, AC-9)
  - [x] Verifier pipeline refactor, repair coordination, and unit tests (AC-4, AC-6, AC-7, AC-10)
  code in `backend/src/engine/`
- [x] Verify it: /check verify safe verifier and evidence

### 4. Bounded branch and refine · done
Tree search (max 3 candidates, 1 refinement) for tougher repairs.
**Done when:** The engine explores branches within strict provider caps.
- [x] Design it (spec): [0004](../specs/0004-bounded-branch-and-refine/index.md)
- [x] Build it: /develop bounded branch and refine
  - [x] Branch search data models and refinement prompt generators (AC-1, AC-2, AC-4, AC-7)
  - [x] Branch search coordinator with depth first traversal and early stopping (AC-2, AC-3, AC-6, AC-8, AC-9, AC-10, AC-11)
  - [x] Engine repair entrypoint routing and offline fake adapter enhancements (AC-1, AC-6, AC-12)
  code in `backend/src/engine/`
- [x] Verify it: /check verify bounded branch and refine
