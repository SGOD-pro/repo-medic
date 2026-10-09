# C — repair engine handoff

Read [shared rules](../AGENTS.md), [product](PRD.md), [architecture](ARCHITECTURE.md) and [build plan](phases.md). Help the foundation owner freeze provider details; then start `feature/c-engine`. No finished UI or backend is required.

## Own and build

Own `backend/src/engine/` and `backend/tests/engine/`. Implement `repair(request,recipe,host)` using FakeHost and fake model/sandbox adapters first. Keep provider adapters and repair orchestration together. No HTTP routes, SQLite imports or second deployment service.

Stages:

1. Fetch only the curated repository/commit; prepare fixed baseline environment. Run preserved tests twice; require both green and stable collection.
2. Upgrade exactly the recipe dependency. Verify installed version and import origin; require the expected real failure.
3. Give a bounded failure context to the model. Parse the patch; reject modifications outside source allowlist, traversal, symlink escapes and test/config/lockfile edits.
4. Apply a candidate to a clean upgraded checkpoint. Run the full preserved suite in a fresh environment. Require nonempty unchanged collection, no new skip/xfail, proper exit status and expected dependency version/import origin.
5. Save patch, raw logs and evidence through HostPorts. Return success only if the hard verifier passes; otherwise a clear failed/cancelled result.

Start with one sequential candidate. Only after integration passes, add at most three candidates and at most one refinement per candidate. Keep limits and model output token caps explicit. Do not use an LLM vote to override failed tests.

Reserve cost through HostPorts before each paid operation. Check cancellation around remote calls and before accepting results. Use known idempotency support only if verified. On timeout with unknown completion, record evidence and stop; no blind resubmission.

## Acceptance checks

- Fake providers exercise success, baseline instability, wrong upgrade, unsafe patch, verifier failure, timeout, cancellation and budget denial with zero network calls.
- Tests detect changed tests/config, empty collection, newly skipped tests and wrong dependency import origin.
- Every candidate starts clean; a failed candidate cannot contaminate another.
- Evidence records task/commit, model, attempt details, source/test hashes, exact versions, logs and usage estimates. Sanitize keys and sensitive provider fields.
- Standalone harness works using the shared recipe, FakeHost and fake providers; later the same function works with B's HostPorts.

Use `/architect` only for verified provider gaps, `/develop` stages individually, `/test` verifier failure modes and `/debug` failures. Paid probes are operator-controlled. Add sanitized regression fixtures after real failures; pass offline checks before another paid attempt. Do not label mocks or replay as fresh live repairs.
