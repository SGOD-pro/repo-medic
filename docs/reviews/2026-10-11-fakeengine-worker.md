# Review, backend (fakeengine queue worker), 2026-10-11

**Reviewed by**: Gemini 3.8 inline (author also Gemini 3.8; cross-model guarantee not met - degraded review, shared author blind spots)
**Scope**: 9 files, branch `backend` vs `main` (merge base `7233139`)
**Verdict**: Changes requested

## Summary

This change delivers the full FakeEngine queue worker: a background `asyncio` task that polls D1 for queued runs, atomically transitions them to `running`, invokes `fake_engine.repair`, and records a `run.finished` event on completion. The architecture is clean, the test suite is comprehensive, and the key invariants (single concurrency, terminal state immutability, reliable final event) are all exercised. Two majors stand out: a genuine TOCTOU race in the worker claim step that allows two concurrent workers to both claim the same run, and the absence of a state allowlist guard in the `state` query parameter, which lets any string value through silently. Several minors relate to silent exception swallowing, duplicated helpers, non-atomic finish ordering, and a fragile FIFO tie-breaking assumption.

## Major

### 🟠 TOCTOU race in claim step, `backend/src/worker.py:123-136`

**Problem**: `process_one` reads the oldest queued run with `list_runs(limit=1, state="queued")`, then calls `update_run_state(run_id, "running")` in a separate HTTP round trip. If two worker instances or two concurrent calls race, both can read the same run before either writes. The D1 PATCH guard only rejects updates from terminal states; transitioning `queued -> running` twice is allowed because `running` is not terminal.

**Why it matters**: In the current single-worker setup this is latent, but the spec explicitly flags future multi-worker deployment. Any test that spawns two workers, or a restart where the old process is still draining, will silently double-process a run.

**Suggested fix**: Add a `from_state` precondition field to `PATCH /api/runs/:id` in the D1 bridge. The bridge returns `409` when the current state does not match `from_state`. The worker passes `from_state: "queued"` when claiming and treats a `409` as "claimed by another worker, skip." This upgrades the two-step fetch-then-update to a compare-and-swap.

---

### 🟠 Unvalidated `state` query parameter, `db-worker/src/index.ts:169-184`

**Problem**: The `state` query parameter is bound safely as a parameterized value, preventing SQL injection in the narrow sense. However, no allowlist check is applied, so callers can pass any string (e.g. `state=queue`, `state=bogus`). These silently return an empty list rather than a `400`. The worker passing `state=queued` is a silent contract that is never enforced, so a one-character typo in the worker would stall the queue invisibly.

**Why it matters**: Silent empty results on bad state values make bugs extremely hard to diagnose. Establishing an explicit allowlist at the bridge boundary makes the contract machine-checkable.

**Suggested fix**: Add an allowlist check before the query: valid states are `queued`, `running`, `succeeded`, `failed`, `cancelled`; return `400 invalid_state` for any other value. Mirror this in FastAPI with a `Literal` or `Enum` type annotation on the `state` query parameter instead of bare `Optional[str]`.

---

## Minor

### 🟡 Duplicated `find_task_fixture_dir`, `backend/src/worker.py:15-24` and `backend/src/main.py:44-53`

**Problem**: The two implementations are byte-for-byte identical. The duplication was introduced in this change.

**Why it matters**: One will be updated when fixture discovery evolves and the other will not, causing divergent behavior between task sync at startup and recipe loading at claim time.

**Suggested fix**: Move the function to a shared module (e.g. `src/fixtures.py`) and import it in both callers.

---

### 🟡 Silent exception swallow in `cancelled()`, `backend/src/storage/repository.py:240`

**Problem**: The bare `except Exception: pass` swallows all exceptions from `self.client.get_run(...)`, including network errors indicating the D1 bridge is down. The method returns `False` in all failure cases, telling the engine the run is not cancelled even when cancellation state cannot be determined.

**Why it matters**: If the bridge becomes temporarily unavailable mid-run, the engine continues to consume budget and execute stages. The error is invisible.

**Suggested fix**: Narrow the catch to `httpx.HTTPStatusError` and handle only 404 returns as "unknown, assume not cancelled." Let other errors propagate so the worker can handle them at a higher level.

---

### 🟡 Non-atomic `finish_run` ordering, `backend/src/storage/repository.py:134-137`

**Problem**: `finish_run` appends the `run.finished` event and then updates the run state in two separate HTTP calls. A crash or bridge failure between the two leaves a run with a `run.finished` event in state `running`.

**Why it matters**: A client polling events sees `run.finished` and assumes the state column reflects completion, but a follow-up GET shows state `running`. The event-first ordering produces the most misleading partial failure.

**Suggested fix**: Reverse the order: write final state first, then emit the event. A run in state `succeeded` with no `run.finished` event is less confusing than the inverse. Document the intended ordering invariant in the method docstring. The full atomicity fix belongs in the planned "Budget enforcement and restart" slice.

---

### 🟡 `created_at` FIFO tie-breaking not guaranteed, `db-worker/src/index.ts:185-189`

**Problem**: Queue ordering uses `ORDER BY created_at ASC`. Two runs submitted within the same second get identical `created_at` strings, and their relative order is undefined. The test avoids this by passing explicit timestamps spread five minutes apart.

**Why it matters**: In production, runs submitted in rapid succession are processed in arbitrary order, violating the FIFO contract the test appears to assert.

**Suggested fix**: Add a secondary sort key: `ORDER BY created_at ASC, run_id ASC` for deterministic tie-breaking. Alternatively, use a monotonic integer sequence column for insertion order.

---

### 🟡 `max_run_usd` read from global settings, ignoring per-run value, `backend/src/worker.py:138`

**Problem**: `process_one` reads `max_run_usd` from `settings.repomedic_max_run_usd` rather than from the claimed run's own `max_run_micro_usd` stored in D1. The D1 schema stores this field per-run to allow variation; the worker ignores it entirely.

**Why it matters**: A run created via any future path with a custom budget will have that budget silently overridden by the global setting.

**Suggested fix**: Expose `max_run_micro_usd` on `RunSummary` and compute `max_run_usd = run.max_run_micro_usd / 1_000_000` in `process_one`. Fall back to the global setting only if the per-run value is absent or zero.

---

## Nits

- ⚪ `backend/src/worker.py:5`, `List` and `Dict` imported from `typing` — unnecessary on Python 3.10+; use built-in `list[...]` and `dict[...]`.
- ⚪ `backend/src/worker.py:155`, `f"Unhandled error: {e}"` — `str(e)` on some exception types produces an empty string; `repr(e)` is more diagnostic in logs.
- ⚪ `backend/src/worker.py:179`, `getattr(settings, "repomedic_worker_poll_interval_seconds", 1.0)` is duplicated in `run_standalone` and `lifespan`; a single settings accessor would be cleaner.
- ⚪ `db-worker/src/index.ts:250`, `max_run_micro_usd` defaults to `0` when absent. A zero-budget run exhausts its budget immediately on the first operation; default to a sensible minimum or return `400` when the field is missing.

## Strengths

- The test suite is thorough and behavioral: FIFO ordering, unhandled exception recovery, lifespan lifecycle, and standalone mode are all covered with a real SQLite transport rather than pure mocks. This is exactly the right testing strategy for an async worker.
- `_scoped_op_id` in `D1HostPorts` is a clean, correct, and obvious solution to the cross-run `UNIQUE` constraint problem.
- `QueueWorker` exposes `process_one` as a discrete unit of work that tests can drive directly without the polling loop, which is the right shape for a testable worker.
- Error paths are deliberate: the worker catches engine exceptions and records them rather than crashing, and the D1 bridge rejects terminal-state mutations, giving the system meaningful resilience properties.

## Test coverage

`TESTS = configured`. Coverage is strong. Two gaps: (1) no test exercises concurrent `process_one` calls on the same run, which would expose the TOCTOU Major; (2) the D1 bridge tests do not assert that `state=bogus` returns `400`, which would catch the allowlist Major. Both gaps should be added alongside the fixes.
