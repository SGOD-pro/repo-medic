export interface Env {
  DB: D1Database;
  DB_BRIDGE_TOKEN?: string;
  ENVIRONMENT?: string;
  ALLOW_LOCAL_DUMMY_TOKEN?: string | boolean;
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

const DEFAULT_BRIDGE_TOKEN = "local-bridge-token";

function errorResponse(code: string, message: string, status = 400): Response {
  return jsonResponse({ error: { code, message } }, status);
}

function isExplicitLocal(env: Env): boolean {
  if (env.ENVIRONMENT === "local") {
    return true;
  }
  if (
    env.ALLOW_LOCAL_DUMMY_TOKEN === true ||
    env.ALLOW_LOCAL_DUMMY_TOKEN === "true" ||
    env.ALLOW_LOCAL_DUMMY_TOKEN === "1"
  ) {
    return true;
  }
  return false;
}

function timingSafeEqual(a: string, b: string): boolean {
  const aLen = a.length;
  const bLen = b.length;
  let diff = aLen ^ bLen;
  const maxLen = Math.max(aLen, bLen);
  for (let i = 0; i < maxLen; i++) {
    const charA = i < aLen ? a.charCodeAt(i) : 0;
    const charB = i < bLen ? b.charCodeAt(i) : 0;
    diff |= charA ^ charB;
  }
  return diff === 0;
}

function checkAuth(request: Request, env: Env): Response | null {
  const rawToken = env.DB_BRIDGE_TOKEN;
  const configuredToken = typeof rawToken === "string" ? rawToken.trim() : "";

  let expectedToken: string;

  if (configuredToken.length > 0) {
    expectedToken = configuredToken;
  } else if (isExplicitLocal(env)) {
    expectedToken = DEFAULT_BRIDGE_TOKEN;
  } else {
    return errorResponse("auth_unconfigured", "Worker authentication secret is not configured", 500);
  }

  const authHeader = request.headers.get("Authorization");
  if (!authHeader) {
    return errorResponse("unauthorized", "Missing or invalid authorization token", 401);
  }

  const match = authHeader.match(/^bearer\s+(.+)$/i);
  if (!match) {
    return errorResponse("unauthorized", "Missing or invalid authorization token", 401);
  }

  const token = match[1].trim();
  if (!timingSafeEqual(token, expectedToken)) {
    return errorResponse("unauthorized", "Missing or invalid authorization token", 401);
  }

  return null;
}

async function updateOperationProviderRef(
  db: D1Database,
  operationId: string,
  providerRef: string,
  updatedAt: string
): Promise<D1Result> {
  return db.prepare(
    "UPDATE operations SET provider_ref = ?, updated_at = ? WHERE operation_id = ?"
  ).bind(providerRef, updatedAt, operationId).run();
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();
    const pathname = url.pathname.replace(/\/+$/, "") || "/";

    // 1. Health check (no auth required)
    if (method === "GET" && pathname === "/health") {
      return jsonResponse({ ok: true, status: "healthy" });
    }

    // Auth gate for all other endpoints
    const authError = checkAuth(request, env);
    if (authError) {
      return authError;
    }

    try {
      // --- TASKS ENDPOINTS ---

      // GET /api/tasks
      if (method === "GET" && pathname === "/api/tasks") {
        const tasksResult = await env.DB.prepare(
          "SELECT task_id, title, repository_url, commit_sha, dependency, from_version, to_version, recipe_json FROM tasks ORDER BY created_at ASC"
        ).all<{
          task_id: string;
          title: string;
          repository_url: string;
          commit_sha: string;
          dependency: string;
          from_version: string;
          to_version: string;
          recipe_json: string | null;
        }>();

        return jsonResponse({ tasks: tasksResult.results || [] }, 200);
      }

      // POST /api/tasks
      if (method === "POST" && pathname === "/api/tasks") {
        const body = await request.json() as {
          task_id?: string;
          title?: string;
          repository_url?: string;
          commit_sha?: string;
          dependency?: string;
          from_version?: string;
          to_version?: string;
          recipe_json?: unknown;
        };

        if (!body.task_id || !body.title || !body.repository_url || !body.commit_sha || !body.dependency || !body.from_version || !body.to_version) {
          return errorResponse("invalid_request", "Missing required task fields", 400);
        }

        let recipeObj = body.recipe_json;
        if (!recipeObj && (body as Record<string, unknown>).test_command) {
          recipeObj = {
            test_command: (body as Record<string, unknown>).test_command,
            allowed_source_paths: (body as Record<string, unknown>).allowed_source_paths || ["src/"],
            expected_failure: (body as Record<string, unknown>).expected_failure || "",
            timeout_seconds: (body as Record<string, unknown>).timeout_seconds || 600,
            max_candidates: (body as Record<string, unknown>).max_candidates || 3,
            max_refinements: (body as Record<string, unknown>).max_refinements || 1,
          };
        }
        const recipeJsonStr = typeof recipeObj === "string"
          ? recipeObj
          : recipeObj ? JSON.stringify(recipeObj) : null;
        const now = new Date().toISOString();

        await env.DB.prepare(
          `INSERT INTO tasks (task_id, title, repository_url, commit_sha, dependency, from_version, to_version, recipe_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(task_id) DO UPDATE SET
             title = excluded.title,
             repository_url = excluded.repository_url,
             commit_sha = excluded.commit_sha,
             dependency = excluded.dependency,
             from_version = excluded.from_version,
             to_version = excluded.to_version,
             recipe_json = excluded.recipe_json`
        ).bind(
          body.task_id,
          body.title,
          body.repository_url,
          body.commit_sha,
          body.dependency,
          body.from_version,
          body.to_version,
          recipeJsonStr,
          now
        ).run();

        return jsonResponse({ ok: true, task_id: body.task_id }, 201);
      }

      // GET /api/tasks/:task_id
      const getTaskMatch = pathname.match(/^\/api\/tasks\/([^/]+)$/);
      if (method === "GET" && getTaskMatch) {
        const taskId = decodeURIComponent(getTaskMatch[1]);
        const task = await env.DB.prepare(
          "SELECT task_id, title, repository_url, commit_sha, dependency, from_version, to_version, recipe_json FROM tasks WHERE task_id = ?"
        ).bind(taskId).first<{
          task_id: string;
          title: string;
          repository_url: string;
          commit_sha: string;
          dependency: string;
          from_version: string;
          to_version: string;
          recipe_json: string | null;
        }>();

        if (!task) {
          return errorResponse("not_found", "Task not found", 404);
        }

        return jsonResponse(task, 200);
      }

      // --- RUNS ENDPOINTS ---

      // GET /api/runs (history list and queue query)
      if (method === "GET" && pathname === "/api/runs") {
        const limitParam = parseInt(url.searchParams.get("limit") || "50", 10);
        const limit = Math.min(Math.max(isNaN(limitParam) ? 50 : limitParam, 1), 100);
        const taskId = url.searchParams.get("task_id") || null;
        const stateParam = url.searchParams.get("state") || null;
        const runPrefix = url.searchParams.get("run_prefix") || url.searchParams.get("prefix") || null;

        if (stateParam) {
          const allowedStates = ["queued", "running", "succeeded", "failed", "cancelled"];
          if (!allowedStates.includes(stateParam)) {
            return errorResponse("invalid_state", `Invalid state filter '${stateParam}'`, 400);
          }
        }

        let query = "SELECT run_id, task_id, mode, search_mode, state, reason, usage_json, created_at, max_run_micro_usd FROM runs";
        const params: unknown[] = [];
        const conditions: string[] = [];
        if (taskId) {
          conditions.push("task_id = ?");
          params.push(taskId);
        }
        if (stateParam) {
          conditions.push("state = ?");
          params.push(stateParam);
        }
        if (runPrefix) {
          const escapedPrefix = runPrefix.replace(/([%_\\])/g, "\\$1");
          conditions.push("run_id LIKE ? ESCAPE '\\'");
          params.push(`${escapedPrefix}%`);
        }
        if (conditions.length > 0) {
          query += " WHERE " + conditions.join(" AND ");
        }
        if (stateParam === "queued") {
          // FIFO for the work queue: oldest queued run is claimed first.
          query += " ORDER BY created_at ASC, run_id ASC LIMIT ?";
        } else {
          query += " ORDER BY created_at DESC, run_id ASC LIMIT ?";
        }
        params.push(limit);

        const runsResult = await env.DB.prepare(query).bind(...params).all<{
          run_id: string;
          task_id: string;
          mode: string;
          search_mode: string;
          state: string;
          reason: string | null;
          usage_json: string;
          created_at: string;
          max_run_micro_usd: number;
        }>();

        const runsList = runsResult.results || [];
        const runsWithArtifacts = await Promise.all(
          runsList.map(async (run) => {
            const artifactsResult = await env.DB.prepare(
              "SELECT artifact_id, kind, filename FROM artifacts WHERE run_id = ? ORDER BY created_at ASC"
            ).bind(run.run_id).all<{
              artifact_id: string;
              kind: string;
              filename: string;
            }>();
            let usage = { model_calls: 0, input_tokens: 0, output_tokens: 0, estimated_usd: 0 };
            try {
              usage = JSON.parse(run.usage_json);
            } catch {
              // fallback default
            }
            return {
              run_id: run.run_id,
              task_id: run.task_id,
              mode: run.mode,
              search_mode: run.search_mode,
              state: run.state,
              reason: run.reason,
              max_run_micro_usd: run.max_run_micro_usd,
              usage,
              artifacts: artifactsResult.results || [],
            };
          })
        );

        return jsonResponse({ runs: runsWithArtifacts }, 200);
      }

      // POST /api/runs
      if (method === "POST" && pathname === "/api/runs") {
        const body = await request.json() as {
          run_id?: string;
          task_id?: string;
          mode?: string;
          search_mode?: string;
          state?: string;
          max_run_micro_usd?: number;
        };

        if (!body.run_id || !body.task_id || !body.mode || !body.search_mode) {
          return errorResponse("invalid_request", "Missing required run fields", 400);
        }

        const RUN_ID_REGEX = /^[a-zA-Z0-9_-]{1,128}$/;
        if (typeof body.run_id !== "string" || !RUN_ID_REGEX.test(body.run_id)) {
          return errorResponse("invalid_request", "Invalid run_id format: must be 1-128 characters matching [a-zA-Z0-9_-]", 400);
        }

        const maxMicroUsd = typeof body.max_run_micro_usd === "number" ? body.max_run_micro_usd : 2000000;
        if (maxMicroUsd < 0) {
          return errorResponse("invalid_request", "max_run_micro_usd must be non-negative", 400);
        }

        const state = body.state || "queued";
        const now = new Date().toISOString();
        const initialUsage = JSON.stringify({
          model_calls: 0,
          input_tokens: 0,
          output_tokens: 0,
          estimated_usd: 0,
        });

        const existing = await env.DB.prepare("SELECT run_id FROM runs WHERE run_id = ?").bind(body.run_id).first();
        if (existing) {
          return errorResponse("run_already_exists", `Run with ID '${body.run_id}' already exists`, 409);
        }

        await env.DB.prepare(
          `INSERT INTO runs (run_id, task_id, mode, search_mode, state, reason, usage_json, created_at, updated_at, max_run_micro_usd)
           VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)`
        ).bind(body.run_id, body.task_id, body.mode, body.search_mode, state, initialUsage, now, now, maxMicroUsd).run();

        return jsonResponse({ ok: true, run_id: body.run_id }, 201);
      }

      // GET /api/runs/:run_id
      const getRunMatch = pathname.match(/^\/api\/runs\/([^/]+)$/);
      if (method === "GET" && getRunMatch) {
        const runId = decodeURIComponent(getRunMatch[1]);
        const run = await env.DB.prepare(
          "SELECT run_id, task_id, mode, search_mode, state, reason, usage_json, max_run_micro_usd FROM runs WHERE run_id = ?"
        ).bind(runId).first<{
          run_id: string;
          task_id: string;
          mode: string;
          search_mode: string;
          state: string;
          reason: string | null;
          usage_json: string;
          max_run_micro_usd: number;
        }>();

        if (!run) {
          return errorResponse("not_found", "Run not found", 404);
        }

        const artifactsResult = await env.DB.prepare(
          "SELECT artifact_id, kind, filename FROM artifacts WHERE run_id = ? ORDER BY created_at ASC"
        ).bind(runId).all<{
          artifact_id: string;
          kind: string;
          filename: string;
        }>();

        let usage = { model_calls: 0, input_tokens: 0, output_tokens: 0, estimated_usd: 0 };
        try {
          usage = JSON.parse(run.usage_json);
        } catch {
          // fallback default
        }

        return jsonResponse({
          run_id: run.run_id,
          task_id: run.task_id,
          mode: run.mode,
          search_mode: run.search_mode,
          state: run.state,
          reason: run.reason,
          max_run_micro_usd: run.max_run_micro_usd,
          usage,
          artifacts: artifactsResult.results || [],
        }, 200);
      }

      // PATCH /api/runs/:run_id
      if (method === "PATCH" && getRunMatch) {
        const runId = decodeURIComponent(getRunMatch[1]);
        const body = await request.json() as { state?: string; reason?: string | null; from_state?: string };

        if (!body.state) {
          return errorResponse("invalid_request", "State is required", 400);
        }

        const allowedStates = ["queued", "running", "succeeded", "failed", "cancelled"];
        if (!allowedStates.includes(body.state)) {
          return errorResponse("invalid_state", `Invalid state '${body.state}'`, 400);
        }

        const run = await env.DB.prepare("SELECT state FROM runs WHERE run_id = ?").bind(runId).first<{ state: string }>();
        if (!run) {
          return errorResponse("not_found", "Run not found", 404);
        }

        const terminalStates = ["succeeded", "failed", "cancelled"];
        if (terminalStates.includes(run.state)) {
          return errorResponse("terminal_state_immutable", `Cannot transition run from terminal state '${run.state}'`, 409);
        }

        if (body.from_state && run.state !== body.from_state) {
          return errorResponse("state_conflict", `Run state '${run.state}' does not match expected from_state '${body.from_state}'`, 409);
        }

        const now = new Date().toISOString();
        const reason = body.reason !== undefined ? body.reason : null;

        if (body.from_state) {
          const updateRes = await env.DB.prepare(
            "UPDATE runs SET state = ?, reason = ?, updated_at = ? WHERE run_id = ? AND state = ?"
          ).bind(body.state, reason, now, runId, body.from_state).run();
          if (updateRes.meta.changes === 0) {
            return errorResponse("state_conflict", "State conflict during transition", 409);
          }
        } else {
          // Atomic terminal-state guard: even without from_state, the UPDATE
          // must not silently overwrite a terminal state that another caller
          // set between the pre-read above and this write.
          const nonCasRes = await env.DB.prepare(
            "UPDATE runs SET state = ?, reason = ?, updated_at = ? WHERE run_id = ? AND state NOT IN ('succeeded','failed','cancelled')"
          ).bind(body.state, reason, now, runId).run();
          if (nonCasRes.meta.changes === 0) {
            return errorResponse("terminal_state_immutable", "Run is in a terminal state and cannot be updated", 409);
          }
        }

        return jsonResponse({ ok: true }, 200);
      }

      // --- EVENTS ENDPOINTS ---

      // POST /api/runs/:run_id/events
      const eventsMatch = pathname.match(/^\/api\/runs\/([^/]+)\/events$/);
      if (method === "POST" && eventsMatch) {
        const runId = decodeURIComponent(eventsMatch[1]);
        const body = await request.json() as { type?: string; payload?: unknown };

        if (!body.type || typeof body.type !== "string") {
          return errorResponse("invalid_request", "Event type is required", 400);
        }
        if (!body.payload || typeof body.payload !== "object") {
          return errorResponse("invalid_request", "Event payload must be a non-empty object", 400);
        }

        const run = await env.DB.prepare("SELECT 1 FROM runs WHERE run_id = ?").bind(runId).first();
        if (!run) {
          return errorResponse("not_found", "Run not found", 404);
        }

        const now = new Date().toISOString();
        const payloadJson = JSON.stringify(body.payload);

        // Atomic sequence generation
        const res = await env.DB.prepare(
          `INSERT INTO events (run_id, seq, ts, type, payload_json)
           VALUES (?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE run_id = ?), ?, ?, ?)
           RETURNING seq, ts`
        ).bind(runId, runId, now, body.type, payloadJson).first<{ seq: number; ts: string }>();

        if (!res) {
          return errorResponse("internal_error", "Failed to insert event", 500);
        }

        return jsonResponse({ ok: true, seq: res.seq, ts: res.ts }, 201);
      }

      // GET /api/runs/:run_id/events?after=0
      if (method === "GET" && eventsMatch) {
        const runId = decodeURIComponent(eventsMatch[1]);
        const run = await env.DB.prepare("SELECT 1 FROM runs WHERE run_id = ?").bind(runId).first();
        if (!run) {
          return errorResponse("not_found", "Run not found", 404);
        }

        const afterParam = url.searchParams.get("after") || "0";
        const after = parseInt(afterParam, 10);
        if (isNaN(after) || after < 0) {
          return errorResponse("invalid_cursor", "after must be a non-negative integer", 400);
        }

        const result = await env.DB.prepare(
          "SELECT seq, type, payload_json, ts FROM events WHERE run_id = ? AND seq > ? ORDER BY seq ASC"
        ).bind(runId, after).all<{
          seq: number;
          type: string;
          payload_json: string;
          ts: string;
        }>();

        const events = (result.results || []).map(row => {
          let payload: unknown = {};
          try {
            payload = JSON.parse(row.payload_json);
          } catch {
            payload = row.payload_json;
          }
          return {
            seq: row.seq,
            type: row.type,
            payload,
            ts: row.ts,
          };
        });

        return jsonResponse({ events }, 200);
      }

      // --- ARTIFACTS ENDPOINTS ---

      // POST /api/runs/:run_id/artifacts
      const artifactsMatch = pathname.match(/^\/api\/runs\/([^/]+)\/artifacts$/);
      if (method === "POST" && artifactsMatch) {
        const runId = decodeURIComponent(artifactsMatch[1]);
        const body = await request.json() as {
          artifact_id?: string;
          kind?: string;
          filename?: string;
          sha256?: string;
          size_bytes?: number;
          content_base64?: string;
        };

        if (!body.artifact_id || !body.kind || !body.filename || !body.sha256 || typeof body.size_bytes !== "number" || !body.content_base64) {
          return errorResponse("invalid_request", "Missing required artifact fields", 400);
        }

        // Limit 1: Individual artifact <= 1,048,576 bytes (1 MB)
        if (body.size_bytes > 1048576) {
          return errorResponse("artifact_size_limit_exceeded", "Individual artifact exceeds limit of 1048576 bytes", 413);
        }

        const run = await env.DB.prepare("SELECT 1 FROM runs WHERE run_id = ?").bind(runId).first();
        if (!run) {
          return errorResponse("not_found", "Run not found", 404);
        }

        // Limit 2: Cumulative run volume <= 8,388,608 bytes (8 MB)
        // Enforced atomically via conditional INSERT
        const now = new Date().toISOString();
        const insertResult = await env.DB.prepare(
          `INSERT INTO artifacts (artifact_id, run_id, kind, filename, sha256, size_bytes, content_base64, created_at)
           SELECT ?, ?, ?, ?, ?, ?, ?, ?
           WHERE (
             SELECT COALESCE(SUM(size_bytes), 0)
             FROM artifacts
             WHERE run_id = ?
           ) + ? <= 8388608`
        ).bind(
          body.artifact_id,
          runId,
          body.kind,
          body.filename,
          body.sha256,
          body.size_bytes,
          body.content_base64,
          now,
          runId,
          body.size_bytes
        ).run();

        if (!insertResult.meta || insertResult.meta.changes === 0) {
          return errorResponse("run_artifact_volume_limit_exceeded", "Total run artifact volume exceeds limit of 8388608 bytes", 413);
        }

        return jsonResponse({ ok: true, artifact_id: body.artifact_id }, 201);
      }

      // GET /api/runs/:run_id/artifacts/:artifact_id
      const artifactDetailMatch = pathname.match(/^\/api\/runs\/([^/]+)\/artifacts\/([^/]+)$/);
      if (method === "GET" && artifactDetailMatch) {
        const runId = decodeURIComponent(artifactDetailMatch[1]);
        const artifactId = decodeURIComponent(artifactDetailMatch[2]);

        const artifact = await env.DB.prepare(
          "SELECT artifact_id, kind, filename, sha256, size_bytes, content_base64 FROM artifacts WHERE run_id = ? AND artifact_id = ?"
        ).bind(runId, artifactId).first<{
          artifact_id: string;
          kind: string;
          filename: string;
          sha256: string;
          size_bytes: number;
          content_base64: string;
        }>();

        if (!artifact) {
          return errorResponse("not_found", "Artifact not found", 404);
        }

        return jsonResponse(artifact, 200);
      }

      // --- OPERATIONS / BUDGET ENDPOINTS ---

      // GET /api/budget/usage
      if (method === "GET" && pathname === "/api/budget/usage") {
        const usage = await env.DB.prepare(
          `SELECT
             COALESCE(SUM(CASE WHEN status = 'settled' THEN settled_micro_usd ELSE 0 END), 0) as settled_micro_usd,
             COALESCE(SUM(CASE WHEN status = 'reserved' THEN reserved_micro_usd ELSE 0 END), 0) as reserved_micro_usd,
             COALESCE(SUM(CASE WHEN status IN ('reserved', 'settled', 'uncertain') THEN
               CASE WHEN status = 'settled' THEN settled_micro_usd ELSE reserved_micro_usd END
             ELSE 0 END), 0) as total_micro_usd
           FROM operations`
        ).first<{ settled_micro_usd: number; reserved_micro_usd: number; total_micro_usd: number }>();
        return jsonResponse(usage || { settled_micro_usd: 0, reserved_micro_usd: 0, total_micro_usd: 0 }, 200);
      }

      // POST /api/runs/:run_id/operations
      const opsMatch = pathname.match(/^\/api\/runs\/([^/]+)\/operations$/);
      if (method === "POST" && opsMatch) {
        const runId = decodeURIComponent(opsMatch[1]);
        const body = await request.json() as {
          operation_id?: string;
          kind?: string;
          reserved_micro_usd?: number;
          global_budget_micro_usd?: number;
        };

        if (!body.operation_id || !body.kind || typeof body.reserved_micro_usd !== "number") {
          return errorResponse("invalid_request", "Missing required operation fields", 400);
        }

        if (body.reserved_micro_usd < 0) {
          return errorResponse("invalid_request", "reserved_micro_usd must be non-negative", 400);
        }

        const run = await env.DB.prepare(
          "SELECT max_run_micro_usd FROM runs WHERE run_id = ?"
        ).bind(runId).first<{ max_run_micro_usd: number }>();

        if (!run) {
          return errorResponse("not_found", "Run not found", 404);
        }

        const globalCap = typeof body.global_budget_micro_usd === "number"
          ? body.global_budget_micro_usd
          : 25000000;

        // Atomic budget reservation check against both run cap and global budget cap
        const now = new Date().toISOString();
        const insertResult = await env.DB.prepare(
          `INSERT INTO operations (operation_id, run_id, kind, status, reserved_micro_usd, settled_micro_usd, provider_ref, created_at, updated_at)
           SELECT ?, ?, ?, 'reserved', ?, NULL, NULL, ?, ?
           WHERE (
             SELECT COALESCE(SUM(CASE WHEN status = 'settled' THEN settled_micro_usd ELSE reserved_micro_usd END), 0)
             FROM operations
             WHERE run_id = ? AND status IN ('reserved', 'settled', 'uncertain')
           ) + ? <= ?
           AND (
             SELECT COALESCE(SUM(CASE WHEN status = 'settled' THEN settled_micro_usd ELSE reserved_micro_usd END), 0)
             FROM operations
             WHERE status IN ('reserved', 'settled', 'uncertain')
           ) + ? <= ?`
        ).bind(
          body.operation_id,
          runId,
          body.kind,
          body.reserved_micro_usd,
          now,
          now,
          runId,
          body.reserved_micro_usd,
          run.max_run_micro_usd,
          body.reserved_micro_usd,
          globalCap
        ).run();

        if (!insertResult.meta || insertResult.meta.changes === 0) {
          return errorResponse("budget_limit_exceeded", "Requested reservation exceeds available budget cap", 409);
        }

        return jsonResponse({ ok: true }, 201);
      }

      // PATCH /api/operations/:operation_id
      const opDetailMatch = pathname.match(/^\/api\/operations\/([^/]+)$/);
      if (method === "PATCH" && opDetailMatch) {
        const operationId = decodeURIComponent(opDetailMatch[1]);
        const body = await request.json() as {
          settled_micro_usd?: number;
          provider_ref?: string;
        };

        const settled = typeof body.settled_micro_usd === "number" ? body.settled_micro_usd : null;
        const providerRef = typeof body.provider_ref === "string" ? body.provider_ref : null;

        if (settled === null && providerRef === null) {
          return errorResponse("invalid_request", "Must provide settled_micro_usd or provider_ref", 400);
        }

        if (settled !== null && settled < 0) {
          return errorResponse("invalid_request", "settled_micro_usd must be non-negative", 400);
        }

        const op = await env.DB.prepare(
          "SELECT operation_id, status, settled_micro_usd, provider_ref FROM operations WHERE operation_id = ?"
        ).bind(operationId).first<{
          operation_id: string;
          status: string;
          settled_micro_usd: number | null;
          provider_ref: string | null;
        }>();

        if (!op) {
          return errorResponse("not_found", "Operation not found", 404);
        }

        const now = new Date().toISOString();

        if (settled !== null) {
          if (op.status === "settled") {
            if (op.settled_micro_usd !== settled) {
              return errorResponse("operation_already_settled", "Operation is already settled with a different amount", 409);
            }
            // Idempotent settlement retry: do not mutate provider_ref on already settled operation
            return jsonResponse({ ok: true }, 200);
          }

          // Guard against settling non-active operations (e.g. cancelled)
          if (op.status !== "reserved" && op.status !== "uncertain") {
            return errorResponse("invalid_state", `Cannot settle operation in '${op.status}' state`, 409);
          }

          await env.DB.prepare(
            `UPDATE operations
             SET settled_micro_usd = ?, status = 'settled', updated_at = ?, provider_ref = COALESCE(?, provider_ref)
             WHERE operation_id = ?`
          ).bind(settled, now, providerRef, operationId).run();
        } else if (providerRef !== null) {
          // Guard against updating provider_ref on non-active operations
          if (op.status !== "reserved" && op.status !== "uncertain") {
            return errorResponse("invalid_state", `Cannot update provider_ref for operation in '${op.status}' state`, 409);
          }
          await updateOperationProviderRef(env.DB, operationId, providerRef, now);
        }

        return jsonResponse({ ok: true }, 200);
      }

      // PATCH /api/operations/:operation_id/provider_ref
      // Dedicated endpoint for async provider callbacks updating only the external provider reference.
      const opProviderRefMatch = pathname.match(/^\/api\/operations\/([^/]+)\/provider_ref$/);
      if (method === "PATCH" && opProviderRefMatch) {
        const operationId = decodeURIComponent(opProviderRefMatch[1]);
        const body = await request.json() as { provider_ref?: string };

        if (!body.provider_ref || typeof body.provider_ref !== "string") {
          return errorResponse("invalid_request", "provider_ref must be a string", 400);
        }

        const op = await env.DB.prepare("SELECT operation_id, status FROM operations WHERE operation_id = ?").bind(operationId).first<{
          operation_id: string;
          status: string;
        }>();
        if (!op) {
          return errorResponse("not_found", "Operation not found", 404);
        }

        if (op.status !== "reserved" && op.status !== "uncertain") {
          return errorResponse("invalid_state", `Cannot update provider_ref for operation in '${op.status}' state`, 409);
        }

        const now = new Date().toISOString();
        await updateOperationProviderRef(env.DB, operationId, body.provider_ref, now);

        return jsonResponse({ ok: true }, 200);
      }

      // POST /api/cleanup (exact manifest cleanup)
      if (method === "POST" && pathname === "/api/cleanup") {
        const body = (await request.json().catch(() => null)) as {
          tasks?: unknown;
          runs?: unknown;
          operations?: unknown;
          artifacts?: unknown;
        } | null;

        if (!body || typeof body !== "object") {
          return errorResponse("invalid_request", "Invalid JSON payload for cleanup", 400);
        }

        const taskIds = Array.isArray(body.tasks) ? body.tasks.filter((x): x is string => typeof x === "string") : [];
        const runIds = Array.isArray(body.runs) ? body.runs.filter((x): x is string => typeof x === "string") : [];
        const opIds = Array.isArray(body.operations) ? body.operations.filter((x): x is string => typeof x === "string") : [];
        const artIds = Array.isArray(body.artifacts) ? body.artifacts.filter((x): x is string => typeof x === "string") : [];

        // Exact deletion order: operations -> artifacts -> events -> runs -> tasks
        const deletedCounts = {
          operations: 0,
          artifacts: 0,
          events: 0,
          runs: 0,
          tasks: 0,
        };

        const chunk = <T>(arr: T[], size: number): T[][] => {
          const res: T[][] = [];
          for (let i = 0; i < arr.length; i += size) {
            res.push(arr.slice(i, i + size));
          }
          return res;
        };

        for (const opBatch of chunk(opIds, 50)) {
          const placeholders = opBatch.map(() => "?").join(",");
          const res = await env.DB.prepare(`DELETE FROM operations WHERE operation_id IN (${placeholders})`).bind(...opBatch).run();
          deletedCounts.operations += res.meta?.changes ?? 0;
        }

        for (const artBatch of chunk(artIds, 50)) {
          const placeholders = artBatch.map(() => "?").join(",");
          const res = await env.DB.prepare(`DELETE FROM artifacts WHERE artifact_id IN (${placeholders})`).bind(...artBatch).run();
          deletedCounts.artifacts += res.meta?.changes ?? 0;
        }

        for (const runBatch of chunk(runIds, 50)) {
          const placeholders = runBatch.map(() => "?").join(",");
          const resEvents = await env.DB.prepare(`DELETE FROM events WHERE run_id IN (${placeholders})`).bind(...runBatch).run();
          deletedCounts.events += resEvents.meta?.changes ?? 0;

          const resRuns = await env.DB.prepare(`DELETE FROM runs WHERE run_id IN (${placeholders})`).bind(...runBatch).run();
          deletedCounts.runs += resRuns.meta?.changes ?? 0;
        }

        for (const taskBatch of chunk(taskIds, 50)) {
          const placeholders = taskBatch.map(() => "?").join(",");
          const res = await env.DB.prepare(`DELETE FROM tasks WHERE task_id IN (${placeholders})`).bind(...taskBatch).run();
          deletedCounts.tasks += res.meta?.changes ?? 0;
        }

        return jsonResponse({ ok: true, deleted: deletedCounts }, 200);
      }

      return errorResponse("not_found", `Route '${method} ${pathname}' not found`, 404);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Internal database worker error";
      return errorResponse("internal_error", message, 500);
    }
  },
};
