import * as fs from 'fs';
import {
  validateTaskRecipe,
  validateRunSummary,
  validateReconnectResult,
  validateRunHistory,
  validateEventEnvelope,
} from './src/lib/validation';

function assertThrows(fn: () => void, expectedMessageSubstr: string) {
  try {
    fn();
    throw new Error(`Expected function to throw error containing "${expectedMessageSubstr}", but it did not throw.`);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    if (!message.includes(expectedMessageSubstr)) {
      throw new Error(`Expected error message to include "${expectedMessageSubstr}", got "${message}"`);
    }
  }
}

function runTests() {
  console.log("Running positive fixture validations...");

  // 1. Task Recipe fixture
  const taskJson = JSON.parse(fs.readFileSync('../fixtures/tasks/example-task-1.json', 'utf-8'));
  const task = validateTaskRecipe(taskJson);
  if (task.task_id !== "example-task-1") throw new Error("Task ID mismatch");

  // 2. Success run fixture
  const successJson = JSON.parse(fs.readFileSync('../fixtures/runs/success.json', 'utf-8'));
  const success = validateRunSummary(successJson);
  if (success.state !== "succeeded" || success.reason !== null) throw new Error("Success run invalid");

  // 3. Failure run fixture
  const failJson = JSON.parse(fs.readFileSync('../fixtures/runs/failure.json', 'utf-8'));
  const failure = validateRunSummary(failJson);
  if (failure.state !== "failed" || !failure.reason) throw new Error("Failure run invalid");

  // 4. Cancel run fixture
  const cancelJson = JSON.parse(fs.readFileSync('../fixtures/runs/cancel.json', 'utf-8'));
  const cancel = validateRunSummary(cancelJson);
  if (cancel.state !== "cancelled" || !cancel.reason) throw new Error("Cancel run invalid");

  // 5. Documented API example (Queued run)
  const queuedJson = JSON.parse(fs.readFileSync('../fixtures/runs/queued.json', 'utf-8'));
  const queued = validateRunSummary(queuedJson);
  if (queued.state !== "queued" || queued.reason !== null) throw new Error("Queued run invalid");

  // 6. Reconnect / events fixture
  const reconnectJson = JSON.parse(fs.readFileSync('../fixtures/runs/reconnect.json', 'utf-8'));
  const reconnect = validateReconnectResult(reconnectJson);
  if (reconnect.events.length !== 4) throw new Error("Expected 4 events in reconnect fixture");

  // 7. History fixture
  const historyJson = JSON.parse(fs.readFileSync('../fixtures/runs/history.json', 'utf-8'));
  const history = validateRunHistory(historyJson);
  if (history.length !== 3) throw new Error("Expected 3 items in history");

  console.log("Running negative validation checks...");

  // Missing fields in RunSummary
  assertThrows(() => validateRunSummary({ ...successJson, run_id: "" }), "run_id must be a non-empty string");
  assertThrows(() => validateRunSummary({ ...successJson, usage: undefined }), "usage must be an object");
  assertThrows(() => validateRunSummary({ ...successJson, task_id: null }), "task_id must be a non-empty string");

  // Invalid states in RunSummary
  assertThrows(() => validateRunSummary({ ...successJson, state: "flying" }), "Invalid state: flying");
  assertThrows(() => validateRunSummary({ ...successJson, mode: "unsupported" }), "Invalid mode: unsupported");
  assertThrows(() => validateRunSummary({ ...successJson, search_mode: "quantum" }), "Invalid search_mode: quantum");

  // Invalid numeric bounds
  assertThrows(
    () => validateRunSummary({ ...successJson, usage: { ...successJson.usage, estimated_usd: -5 } }),
    "usage.estimated_usd must be a non-negative number"
  );
  assertThrows(
    () => validateRunSummary({ ...successJson, usage: { ...successJson.usage, model_calls: -1 } }),
    "usage.model_calls must be a non-negative number"
  );

  // Invalid event envelopes
  assertThrows(
    () => validateEventEnvelope({ run_id: "r1", seq: 0, ts: "2026-10-09T00:00:00Z", type: "run.started", payload: {} }),
    "seq must be an integer >= 1"
  );
  assertThrows(
    () => validateEventEnvelope({ run_id: "r1", seq: 1, ts: "2026-10-09T00:00:00Z", type: "magic.completed", payload: {} }),
    "Invalid event type: magic.completed"
  );
  assertThrows(
    () => validateEventEnvelope({ run_id: "", seq: 1, ts: "2026-10-09T00:00:00Z", type: "run.started", payload: {} }),
    "run_id must be a non-empty string"
  );

  // Missing fields in TaskRecipe
  assertThrows(() => validateTaskRecipe({ ...taskJson, task_id: "" }), "task_id must be a non-empty string");
  assertThrows(() => validateTaskRecipe({ ...taskJson, test_command: [] }), "test_command must be a non-empty string array");
  assertThrows(() => validateTaskRecipe({ ...taskJson, timeout_seconds: -10 }), "timeout_seconds must be a positive number");

  console.log("All TypeScript runtime and negative validation checks passed!");
}

runTests();
