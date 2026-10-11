# 0001. Provider fakes and baseline stage (rationale)

## Context

The repair engine runs as package C within the application architecture. It receives a repair request along with a task recipe, and orchestrates candidate generation and code repair using execution environments.

Before attempting repairs, the engine must confirm that the target repository baseline is genuinely green. If the original project already fails tests, attempting dependency upgrade and automated repair would lead to false diagnoses and wasted resources. Running preserved tests twice proves that test collection and test outcomes remain stable.

To develop and test the engine in isolation without waiting for remote infrastructure, the engine relies on deterministic provider fakes. The engine must remain free of HTTP routes and direct database access, communicating outward strictly through the host ports abstraction provided by package B.

## Options considered

### Option 1: Combined fake provider with hardcoded task matching

A single fake provider class implements both model prompts and sandbox commands, returning fixed responses by inspecting the task identifier string.

**Pros**:
- Requires fewer classes in the initial skeleton.
- Matches the minimal starter file already present in the repository.

**Cons**:
- Couples model inference and sandbox execution into a single object.
- Testing new edge cases requires editing task strings or fixtures rather than configuring test scenarios directly.

### Option 2: Dedicated adapter protocols with configurable fake presets

Separate ModelAdapter and SandboxAdapter protocol interfaces define distinct contracts for inference and execution. The fake sandbox adapter accepts preset scenario behaviors for test suites.

**Pros**:
- Clean separation between inference and execution contracts.
- Tests can directly inject failure, instability, and timeout presets without altering shared task fixtures.
- Simplifies swapping in real provider clients during later live integration.

**Cons**:
- Introduces distinct protocol definitions and execution result structures within the engine package.

## Rationale

Decoupling inference from sandbox execution mirrors the actual system boundaries described in the architecture documentation. Model calls communicate with NVIDIA Nemotron endpoints, while sandbox commands interact with container runtimes. Establishing clear adapter boundaries inside package C now prevents rework when live adapters arrive. Configurable scenario presets on the fake sandbox adapter allow thorough testing of baseline flakiness and failure paths without bloating shared fixtures.
