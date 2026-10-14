import assert from "node:assert";
import worker from "./src/index.ts";

// A lightweight in-memory D1Database simulation for Worker smoke testing
class MockD1 {
  constructor() {
    this.runs = new Map();
    this.events = [];
    this.artifacts = [];
    this.operations = [];
  }

  prepare(query) {
    const q = query.replace(/\s+/g, " ").trim();
    const mock = this;
    return {
      bind(...args) {
        return {
          async first() {
            if (q.includes("FROM runs WHERE run_id = ?") && q.includes("SELECT")) {
              return mock.runs.get(args[0]) || null;
            }
            if (q.includes("SELECT state FROM runs WHERE run_id = ?")) {
              const r = mock.runs.get(args[0]);
              return r ? { state: r.state } : null;
            }
            if (q.includes("SELECT 1 FROM runs WHERE run_id = ?")) {
              return mock.runs.has(args[0]) ? { 1: 1 } : null;
            }
            if (q.includes("SELECT max_run_micro_usd FROM runs WHERE run_id = ?")) {
              const r = mock.runs.get(args[0]);
              return r ? { max_run_micro_usd: r.max_run_micro_usd } : null;
            }
            if (q.includes("INSERT INTO events") && q.includes("RETURNING seq, ts")) {
              const runId = args[0];
              const prevEvents = mock.events.filter(e => e.run_id === runId);
              const seq = prevEvents.length + 1;
              const ts = args[2];
              const type = args[3];
              const payload_json = args[4];
              mock.events.push({ run_id: runId, seq, ts, type, payload_json });
              return { seq, ts };
            }
            if (q.includes("SELECT COALESCE(SUM(size_bytes), 0) AS total_bytes FROM artifacts WHERE run_id = ?")) {
              const runId = args[0];
              const total = mock.artifacts.filter(a => a.run_id === runId).reduce((s, a) => s + a.size_bytes, 0);
              return { total_bytes: total };
            }
            if (q.includes("SELECT artifact_id, kind, filename, sha256, size_bytes, content_base64 FROM artifacts WHERE run_id = ? AND artifact_id = ?")) {
              const a = mock.artifacts.find(x => x.run_id === args[0] && x.artifact_id === args[1]);
              return a || null;
            }
            if (q.includes("SELECT COALESCE(SUM(CASE WHEN status = 'settled' THEN settled_micro_usd ELSE reserved_micro_usd END), 0) AS committed FROM operations WHERE run_id = ?")) {
              const runId = args[0];
              const committed = mock.operations.filter(o => o.run_id === runId && ["reserved", "settled", "uncertain"].includes(o.status)).reduce((s, o) => {
                return s + (o.status === "settled" ? o.settled_micro_usd : o.reserved_micro_usd);
              }, 0);
              return { committed };
            }
            if (q.includes("SELECT operation_id, status, settled_micro_usd, provider_ref FROM operations WHERE operation_id = ?")) {
              const op = mock.operations.find(o => o.operation_id === args[0]);
              return op ? {
                operation_id: op.operation_id,
                status: op.status,
                settled_micro_usd: op.settled_micro_usd,
                provider_ref: op.provider_ref,
              } : null;
            }
            if (q.includes("SELECT operation_id FROM operations WHERE operation_id = ?")) {
              const op = mock.operations.find(o => o.operation_id === args[0]);
              return op ? { operation_id: op.operation_id } : null;
            }
            return null;
          },
          async all() {
            if (q.includes("SELECT artifact_id, kind, filename FROM artifacts WHERE run_id = ? ORDER BY created_at ASC")) {
              const arts = mock.artifacts.filter(a => a.run_id === args[0]).map(a => ({
                artifact_id: a.artifact_id,
                kind: a.kind,
                filename: a.filename,
              }));
              return { results: arts };
            }
            if (q.includes("SELECT seq, type, payload_json, ts FROM events WHERE run_id = ? AND seq > ? ORDER BY seq ASC")) {
              const runId = args[0];
              const after = args[1];
              const evts = mock.events.filter(e => e.run_id === runId && e.seq > after).map(e => ({
                seq: e.seq,
                type: e.type,
                payload_json: e.payload_json,
                ts: e.ts,
              }));
              return { results: evts };
            }
            return { results: [] };
          },
          async run() {
            if (q.includes("INSERT INTO runs")) {
              mock.runs.set(args[0], {
                run_id: args[0],
                task_id: args[1],
                mode: args[2],
                search_mode: args[3],
                state: args[4],
                reason: null,
                usage_json: args[5],
                created_at: args[6],
                updated_at: args[7],
                max_run_micro_usd: args[8],
              });
              return { success: true, meta: { changes: 1 } };
            }
            if (q.includes("UPDATE runs SET state = ?")) {
              const runId = args[3];
              const r = mock.runs.get(runId);
              if (r) {
                if (q.includes("AND state = ?") && r.state !== args[4]) {
                  return { success: true, meta: { changes: 0 } };
                }
                if (q.includes("AND state NOT IN") && ["succeeded", "failed", "cancelled"].includes(r.state)) {
                  return { success: true, meta: { changes: 0 } };
                }
                r.state = args[0];
                r.reason = args[1];
                r.updated_at = args[2];
                return { success: true, meta: { changes: 1 } };
              }
              return { success: true, meta: { changes: 0 } };
            }
            if (q.includes("INSERT INTO artifacts")) {
              const runId = args[1];
              const sizeBytes = args[5];
              const total = mock.artifacts.filter(a => a.run_id === runId).reduce((s, a) => s + a.size_bytes, 0);
              if (total + sizeBytes > 8388608) {
                return { success: true, meta: { changes: 0 } };
              }
              mock.artifacts.push({
                artifact_id: args[0],
                run_id: args[1],
                kind: args[2],
                filename: args[3],
                sha256: args[4],
                size_bytes: args[5],
                content_base64: args[6],
                created_at: args[7],
              });
              return { success: true, meta: { changes: 1 } };
            }
            if (q.includes("INSERT INTO operations")) {
              const runId = args[1];
              const reserved = args[3];
              const maxRun = args[8];
              const committed = mock.operations.filter(o => o.run_id === runId && ["reserved", "settled", "uncertain"].includes(o.status)).reduce((s, o) => {
                return s + (o.status === "settled" ? o.settled_micro_usd : o.reserved_micro_usd);
              }, 0);
              if (committed + reserved > maxRun) {
                return { success: true, meta: { changes: 0 } };
              }
              mock.operations.push({
                operation_id: args[0],
                run_id: args[1],
                kind: args[2],
                status: "reserved",
                reserved_micro_usd: args[3],
                settled_micro_usd: null,
                provider_ref: null,
                created_at: args[4],
                updated_at: args[5],
              });
              return { success: true, meta: { changes: 1 } };
            }
            if (q.includes("UPDATE operations") && q.includes("SET settled_micro_usd = ?")) {
              const op = mock.operations.find(o => o.operation_id === args[3]);
              if (op) {
                op.settled_micro_usd = args[0];
                op.status = "settled";
                op.updated_at = args[1];
                if (args[2]) op.provider_ref = args[2];
              }
              return { success: true, meta: { changes: 1 } };
            }
            if (q.includes("UPDATE operations SET provider_ref = ?")) {
              const op = mock.operations.find(o => o.operation_id === args[2]);
              if (op) {
                op.provider_ref = args[0];
                op.updated_at = args[1];
              }
              return { success: true, meta: { changes: 1 } };
            }
            return { success: true, meta: { changes: 1 } };
          },
        };
      },
    };
  }
}

async function runTests() {
  const db = new MockD1();
  const env = { DB: db, DB_BRIDGE_TOKEN: "my-secret-token" };
  const ctx = {};

  const req = (path, method = "GET", body = null, auth = "Bearer my-secret-token") => {
    const headers = {};
    if (auth) headers["Authorization"] = auth;
    if (body) headers["Content-Type"] = "application/json";
    return new Request(`http://localhost${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });
  };

  console.log("1. Testing GET /health");
  const resHealth = await worker.fetch(new Request("http://localhost/health"), env, ctx);
  assert.strictEqual(resHealth.status, 200);
  const healthJson = await resHealth.json();
  assert.strictEqual(healthJson.ok, true);

  console.log("2. Testing Auth enforcement");
  const resNoAuth = await worker.fetch(req("/api/runs", "POST", { run_id: "r1" }, null), env, ctx);
  assert.strictEqual(resNoAuth.status, 401);
  const resBadAuth = await worker.fetch(req("/api/runs", "POST", { run_id: "r1" }, "Bearer wrong"), env, ctx);
  assert.strictEqual(resBadAuth.status, 401);

  console.log("3. Testing POST /api/runs");
  const resCreate = await worker.fetch(req("/api/runs", "POST", {
    run_id: "run-100",
    task_id: "task-100",
    mode: "offline",
    search_mode: "sequential",
    max_run_micro_usd: 1500000,
  }), env, ctx);
  assert.strictEqual(resCreate.status, 201);
  const createJson = await resCreate.json();
  assert.strictEqual(createJson.run_id, "run-100");

  // Invalid run_id with illegal characters -> 400
  const resBadId = await worker.fetch(req("/api/runs", "POST", {
    run_id: "run/invalid/path",
    task_id: "task-100",
    mode: "offline",
    search_mode: "sequential",
  }), env, ctx);
  assert.strictEqual(resBadId.status, 400);
  const badIdJson = await resBadId.json();
  assert.strictEqual(badIdJson.error.code, "invalid_request");

  // Invalid run_id exceeding length 128 -> 400
  const resTooLongId = await worker.fetch(req("/api/runs", "POST", {
    run_id: "a".repeat(129),
    task_id: "task-100",
    mode: "offline",
    search_mode: "sequential",
  }), env, ctx);
  assert.strictEqual(resTooLongId.status, 400);

  console.log("4. Testing GET /api/runs/:run_id");
  const resGet = await worker.fetch(req("/api/runs/run-100"), env, ctx);
  assert.strictEqual(resGet.status, 200);
  const getJson = await resGet.json();
  assert.strictEqual(getJson.run_id, "run-100");
  assert.strictEqual(getJson.state, "queued");

  console.log("5. Testing PATCH /api/runs/:run_id (state transition)");
  // from_state mismatch -> 409
  const resFromMismatch = await worker.fetch(req("/api/runs/run-100", "PATCH", { state: "running", from_state: "failed" }), env, ctx);
  assert.strictEqual(resFromMismatch.status, 409);

  // from_state match -> 200
  const resFromMatch = await worker.fetch(req("/api/runs/run-100", "PATCH", { state: "running", from_state: "queued" }), env, ctx);
  assert.strictEqual(resFromMatch.status, 200);

  // Transition to terminal
  const resTerminal = await worker.fetch(req("/api/runs/run-100", "PATCH", { state: "succeeded" }), env, ctx);
  assert.strictEqual(resTerminal.status, 200);

  // Attempt transition from terminal state -> 409
  const resImm = await worker.fetch(req("/api/runs/run-100", "PATCH", { state: "running" }), env, ctx);
  assert.strictEqual(resImm.status, 409);

  // Testing GET /api/runs state allowlist validation
  const resBogusState = await worker.fetch(req("/api/runs?state=bogus"), env, ctx);
  assert.strictEqual(resBogusState.status, 400);
  const bogusJson = await resBogusState.json();
  assert.strictEqual(bogusJson.error.code, "invalid_state");

  console.log("6. Testing POST /api/runs/:run_id/events");
  const resEv1 = await worker.fetch(req("/api/runs/run-100/events", "POST", {
    type: "stage.completed",
    payload: { stage: "baseline", passed: true, summary: "ok" },
  }), env, ctx);
  assert.strictEqual(resEv1.status, 201);
  const ev1Json = await resEv1.json();
  assert.strictEqual(ev1Json.seq, 1);

  const resEv2 = await worker.fetch(req("/api/runs/run-100/events", "POST", {
    type: "stage.completed",
    payload: { stage: "upgrade", passed: false, summary: "red" },
  }), env, ctx);
  assert.strictEqual(resEv2.status, 201);
  const ev2Json = await resEv2.json();
  assert.strictEqual(ev2Json.seq, 2);

  console.log("7. Testing GET /api/runs/:run_id/events?after=1");
  const resEvList = await worker.fetch(req("/api/runs/run-100/events?after=1"), env, ctx);
  assert.strictEqual(resEvList.status, 200);
  const evListJson = await resEvList.json();
  assert.strictEqual(evListJson.events.length, 1);
  assert.strictEqual(evListJson.events[0].seq, 2);

  console.log("8. Testing POST /api/runs/:run_id/artifacts");
  const resArt = await worker.fetch(req("/api/runs/run-100/artifacts", "POST", {
    artifact_id: "art-1",
    kind: "patch",
    filename: "fix.patch",
    sha256: "abc",
    size_bytes: 100,
    content_base64: "ZmlsZQ==",
  }), env, ctx);
  assert.strictEqual(resArt.status, 201);

  // Artifact individual size limit (>1MB)
  const resArtLarge = await worker.fetch(req("/api/runs/run-100/artifacts", "POST", {
    artifact_id: "art-large",
    kind: "log",
    filename: "large.log",
    sha256: "abc",
    size_bytes: 1048577,
    content_base64: "abc",
  }), env, ctx);
  assert.strictEqual(resArtLarge.status, 413);

  // Artifact cumulative volume limit (>8MB)
  const resArtCumulative = await worker.fetch(req("/api/runs/run-100/artifacts", "POST", {
    artifact_id: "art-huge",
    kind: "log",
    filename: "huge.log",
    sha256: "abc",
    size_bytes: 8388600,
    content_base64: "abc",
  }), env, ctx);
  assert.strictEqual(resArtCumulative.status, 413);

  console.log("9. Testing Budget Operations");
  // max_run_micro_usd is 1,500,000
  // Reserve 1,000,000
  const resOp1 = await worker.fetch(req("/api/runs/run-100/operations", "POST", {
    operation_id: "model:1",
    kind: "model",
    reserved_micro_usd: 1000000,
  }), env, ctx);
  assert.strictEqual(resOp1.status, 201);

  // Attempt to reserve another 600,000 (total 1,600,000 > 1,500,000) -> 409
  const resOpOver = await worker.fetch(req("/api/runs/run-100/operations", "POST", {
    operation_id: "model:2",
    kind: "model",
    reserved_micro_usd: 600000,
  }), env, ctx);
  assert.strictEqual(resOpOver.status, 409);

  // Empty PATCH body -> 400
  const resEmptyPatch = await worker.fetch(req("/api/operations/model:1", "PATCH", {}), env, ctx);
  assert.strictEqual(resEmptyPatch.status, 400);

  // Settle operation 1 to 500,000 with provider_ref
  const resSettle = await worker.fetch(req("/api/operations/model:1", "PATCH", {
    settled_micro_usd: 500000,
    provider_ref: "provider-initial",
  }), env, ctx);
  assert.strictEqual(resSettle.status, 200);

  // Idempotent re-settlement with exact same amount -> 200, provider_ref remains immutable
  const resIdempotentSettle = await worker.fetch(req("/api/operations/model:1", "PATCH", {
    settled_micro_usd: 500000,
    provider_ref: "provider-tampered",
  }), env, ctx);
  assert.strictEqual(resIdempotentSettle.status, 200);

  const op1 = db.operations.find(o => o.operation_id === "model:1");
  assert.strictEqual(op1.provider_ref, "provider-initial");

  // Conflicting re-settlement with different amount -> 409
  const resConflictSettle = await worker.fetch(req("/api/operations/model:1", "PATCH", {
    settled_micro_usd: 600000,
  }), env, ctx);
  assert.strictEqual(resConflictSettle.status, 409);

  // Guard against settling non-active operation:
  op1.status = "cancelled";
  const resCancelledSettle = await worker.fetch(req("/api/operations/model:1", "PATCH", {
    settled_micro_usd: 500000,
  }), env, ctx);
  assert.strictEqual(resCancelledSettle.status, 409);
  const cancelJson = await resCancelledSettle.json();
  assert.strictEqual(cancelJson.error.code, "invalid_state");

  // Restore model:1 to settled with 500,000 for budget math below
  op1.status = "settled";

  // Now reserve 600,000 (500,000 + 600,000 = 1,100,000 <= 1,500,000) -> 201
  const resOp2 = await worker.fetch(req("/api/runs/run-100/operations", "POST", {
    operation_id: "model:2",
    kind: "model",
    reserved_micro_usd: 600000,
  }), env, ctx);
  assert.strictEqual(resOp2.status, 201);

  console.log("All Worker bridge tests passed successfully!");
}

runTests().catch(err => {
  console.error("Test failed:", err);
  process.exit(1);
});
