# Engine (Package C)

## Slice C: Engine implementation

### 1. Provider fakes and baseline · needs a decision
Fake models and execution host mapping to HostPorts.
**Done when:** The engine runs a successful baseline double-check via fake providers.
- [ ] Design it (spec): `/architect provider fakes and baseline`

### 2. Sequential repair · needs a decision
The core sequential upgrade and repair loop using candidate generation.
**Done when:** A single candidate is proposed and verified against the fake host.
- [ ] Design it (spec): `/architect sequential repair`

### 3. Safe verifier and evidence · needs a decision
Verification of the patch against tests, and collection of evidence logs.
**Done when:** Verification proves the fix and writes complete evidence artifacts.
- [ ] Design it (spec): `/architect safe verifier and evidence`

### 4. Bounded branch and refine · needs a decision
Tree search (max 3 candidates, 1 refinement) for tougher repairs.
**Done when:** The engine explores branches within strict provider caps.
- [ ] Design it (spec): `/architect bounded branch and refine`
