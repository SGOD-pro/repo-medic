import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  MockTransport,
  HttpTransport,
  createApiClient,
  CURATED_TASKS,
  MOCK_PATCH,
  MOCK_EVIDENCE,
  MOCK_LOG,
} from "../src/lib/api";

describe("api client: MockTransport", () => {
  it("getTasks returns all curated tasks (covers: AC-10)", async () => {
    const transport = new MockTransport();
    const tasks = await transport.getTasks();
    assert.equal(tasks.length, 3);
    assert.equal(tasks[0].task_id, "TASK-084");
    assert.equal(tasks[1].task_id, "TASK-091");
    assert.equal(tasks[2].task_id, "TASK-097");
  });

  it("startRun creates a running live run with initial usage and artifacts (covers: AC-1, AC-2, AC-9)", async () => {
    const transport = new MockTransport();
    const run = await transport.startRun("TASK-084", "branch_refine");

    assert.ok(run.run_id.startsWith("run_task_084_"));
    assert.equal(run.task_id, "TASK-084");
    assert.equal(run.state, "running");
    assert.equal(run.mode, "live");
    assert.equal(run.search_mode, "branch_refine");
    assert.equal(run.reason, null);

    // Verify usage tracking (AC-2)
    assert.equal(run.usage.model_calls, 3);
    assert.equal(run.usage.estimated_usd, 0.18);

    // Verify artifacts list (AC-9)
    assert.equal(run.artifacts.length, 3);
    assert.equal(run.artifacts[0].kind, "patch");
    assert.equal(run.artifacts[1].kind, "evidence");
    assert.equal(run.artifacts[2].kind, "log");
  });

  it("getRun returns active run or starts default when not found (covers: AC-10)", async () => {
    const transport = new MockTransport();
    const started = await transport.startRun("TASK-091", "sequential");
    const retrieved = await transport.getRun(started.run_id);
    assert.equal(retrieved.run_id, started.run_id);
    assert.equal(retrieved.task_id, "TASK-091");

    // Fallback for unknown id
    const fallback = await transport.getRun("unknown_run_xyz");
    assert.equal(fallback.task_id, "TASK-084");
  });

  it("cancelRun transitions run state to cancelled with reason (covers: AC-10)", async () => {
    const transport = new MockTransport();
    const run = await transport.startRun("TASK-084", "branch_refine");
    assert.equal(run.state, "running");

    const cancelled = await transport.cancelRun(run.run_id);
    assert.equal(cancelled.state, "cancelled");
    assert.equal(cancelled.reason, "User initiated cancellation");
  });

  it("getRunEvents streams stage and usage event envelopes (covers: AC-1, AC-2, AC-3)", async () => {
    const transport = new MockTransport();
    const events = await transport.getRunEvents("test_run_123");

    assert.ok(events.length >= 6);
    assert.equal(events[0].type, "run.started");
    assert.equal(events[1].type, "stage.completed");
    assert.equal(events[2].type, "stage.completed");
    assert.equal(events[3].type, "stage.completed");
    assert.equal(events[4].type, "candidate.completed");
    assert.equal(events[5].type, "usage.updated");

    // Validate sequence monotonicity
    for (let i = 0; i < events.length; i++) {
      assert.equal(events[i].seq, i + 1);
      assert.equal(events[i].run_id, "test_run_123");
    }
  });

  it("getArtifact returns valid patch diff blob (covers: AC-7, AC-9)", async () => {
    const transport = new MockTransport();
    const patch = await transport.getArtifact("run_1", "patch");
    assert.equal(patch, MOCK_PATCH);
    assert.ok(patch.includes("--- a/src/app/schemas.py"));
    assert.ok(patch.includes("+++ b/src/app/schemas.py"));
    assert.ok(patch.includes("ConfigDict(from_attributes=True)"));
  });

  it("getArtifact returns valid JSON evidence blob (covers: AC-6, AC-8, AC-9)", async () => {
    const transport = new MockTransport();
    const evidenceRaw = await transport.getArtifact("run_1", "evidence");
    const evidence = JSON.parse(evidenceRaw);
    assert.equal(evidence.task_id, "TASK-084");
    assert.equal(evidence.status, "PASSED");
    assert.equal(evidence.tests_passed, 42);
    assert.equal(evidence.tests_failed, 0);
    assert.equal(evidence.cost_usd, 0.04);
  });

  it("getArtifact returns container log (covers: AC-4)", async () => {
    const transport = new MockTransport();
    const log = await transport.getArtifact("run_1", "log");
    assert.equal(log, MOCK_LOG);
    assert.ok(log.includes("candidate A verified successfully"));
  });
});

describe("api client: factory & HttpTransport", () => {
  it("createApiClient defaults to MockTransport in mock mode", () => {
    delete process.env.NEXT_PUBLIC_API_TRANSPORT;
    const client = createApiClient();
    assert.ok(client instanceof MockTransport);
  });

  it("createApiClient instantiates HttpTransport when NEXT_PUBLIC_API_TRANSPORT=http", () => {
    process.env.NEXT_PUBLIC_API_TRANSPORT = "http";
    const client = createApiClient();
    assert.ok(client instanceof HttpTransport);
    delete process.env.NEXT_PUBLIC_API_TRANSPORT;
  });

  it("HttpTransport propagates error messages on non-200 responses", async () => {
    const client = new HttpTransport("http://127.0.0.1:59999/api");
    await assert.rejects(
      async () => {
        await client.getTasks();
      },
      (err: Error) => {
        return err.message.length > 0;
      }
    );
  });
});
