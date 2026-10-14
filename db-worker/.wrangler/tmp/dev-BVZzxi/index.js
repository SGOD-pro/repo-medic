var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// .wrangler/tmp/bundle-mG681I/checked-fetch.js
var urls = /* @__PURE__ */ new Set();
function checkURL(request, init) {
  const url = request instanceof URL ? request : new URL(
    (typeof request === "string" ? new Request(request, init) : request).url
  );
  if (url.port && url.port !== "443" && url.protocol === "https:") {
    if (!urls.has(url.toString())) {
      urls.add(url.toString());
      console.warn(
        `WARNING: known issue with \`fetch()\` requests to custom HTTPS ports in published Workers:
 - ${url.toString()} - the custom port will be ignored when the Worker is published using the \`wrangler deploy\` command.
`
      );
    }
  }
}
__name(checkURL, "checkURL");
globalThis.fetch = new Proxy(globalThis.fetch, {
  apply(target, thisArg, argArray) {
    const [request, init] = argArray;
    checkURL(request, init);
    return Reflect.apply(target, thisArg, argArray);
  }
});

// .wrangler/tmp/bundle-mG681I/strip-cf-connecting-ip-header.js
function stripCfConnectingIPHeader(input, init) {
  const request = new Request(input, init);
  request.headers.delete("CF-Connecting-IP");
  return request;
}
__name(stripCfConnectingIPHeader, "stripCfConnectingIPHeader");
globalThis.fetch = new Proxy(globalThis.fetch, {
  apply(target, thisArg, argArray) {
    return Reflect.apply(target, thisArg, [
      stripCfConnectingIPHeader.apply(null, argArray)
    ]);
  }
});

// src/index.ts
function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}
__name(jsonResponse, "jsonResponse");
var DEFAULT_BRIDGE_TOKEN = "local-bridge-token";
function errorResponse(code, message, status = 400) {
  return jsonResponse({ error: { code, message } }, status);
}
__name(errorResponse, "errorResponse");
function checkAuth(request, env) {
  const expectedToken = env.DB_BRIDGE_TOKEN || DEFAULT_BRIDGE_TOKEN;
  const authHeader = request.headers.get("Authorization");
  if (!authHeader || authHeader !== `Bearer ${expectedToken}`) {
    return errorResponse("unauthorized", "Missing or invalid authorization token", 401);
  }
  return null;
}
__name(checkAuth, "checkAuth");
async function updateOperationProviderRef(db, operationId, providerRef, updatedAt) {
  return db.prepare(
    "UPDATE operations SET provider_ref = ?, updated_at = ? WHERE operation_id = ?"
  ).bind(providerRef, updatedAt, operationId).run();
}
__name(updateOperationProviderRef, "updateOperationProviderRef");
var src_default = {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();
    const pathname = url.pathname.replace(/\/+$/, "") || "/";
    if (method === "GET" && pathname === "/health") {
      return jsonResponse({ ok: true, status: "healthy" });
    }
    const authError = checkAuth(request, env);
    if (authError) {
      return authError;
    }
    try {
      if (method === "GET" && pathname === "/api/tasks") {
        const tasksResult = await env.DB.prepare(
          "SELECT task_id, title, repository_url, commit_sha, dependency, from_version, to_version, recipe_json FROM tasks ORDER BY created_at ASC"
        ).all();
        return jsonResponse({ tasks: tasksResult.results || [] }, 200);
      }
      if (method === "POST" && pathname === "/api/tasks") {
        const body = await request.json();
        if (!body.task_id || !body.title || !body.repository_url || !body.commit_sha || !body.dependency || !body.from_version || !body.to_version) {
          return errorResponse("invalid_request", "Missing required task fields", 400);
        }
        const recipeJsonStr = typeof body.recipe_json === "string" ? body.recipe_json : body.recipe_json ? JSON.stringify(body.recipe_json) : null;
        const now = (/* @__PURE__ */ new Date()).toISOString();
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
      const getTaskMatch = pathname.match(/^\/api\/tasks\/([^/]+)$/);
      if (method === "GET" && getTaskMatch) {
        const taskId = decodeURIComponent(getTaskMatch[1]);
        const task = await env.DB.prepare(
          "SELECT task_id, title, repository_url, commit_sha, dependency, from_version, to_version, recipe_json FROM tasks WHERE task_id = ?"
        ).bind(taskId).first();
        if (!task) {
          return errorResponse("not_found", "Task not found", 404);
        }
        return jsonResponse(task, 200);
      }
      if (method === "GET" && pathname === "/api/runs") {
        const limitParam = parseInt(url.searchParams.get("limit") || "50", 10);
        const limit = Math.min(Math.max(isNaN(limitParam) ? 50 : limitParam, 1), 100);
        const taskId = url.searchParams.get("task_id") || null;
        let query = "SELECT run_id, task_id, mode, search_mode, state, reason, usage_json, created_at FROM runs";
        const params = [];
        if (taskId) {
          query += " WHERE task_id = ?";
          params.push(taskId);
        }
        query += " ORDER BY created_at DESC LIMIT ?";
        params.push(limit);
        const runsResult = await env.DB.prepare(query).bind(...params).all();
        const runsList = runsResult.results || [];
        const runsWithArtifacts = await Promise.all(
          runsList.map(async (run) => {
            const artifactsResult = await env.DB.prepare(
              "SELECT artifact_id, kind, filename FROM artifacts WHERE run_id = ? ORDER BY created_at ASC"
            ).bind(run.run_id).all();
            let usage = { model_calls: 0, input_tokens: 0, output_tokens: 0, estimated_usd: 0 };
            try {
              usage = JSON.parse(run.usage_json);
            } catch {
            }
            return {
              run_id: run.run_id,
              task_id: run.task_id,
              mode: run.mode,
              search_mode: run.search_mode,
              state: run.state,
              reason: run.reason,
              usage,
              artifacts: artifactsResult.results || []
            };
          })
        );
        return jsonResponse({ runs: runsWithArtifacts }, 200);
      }
      if (method === "POST" && pathname === "/api/runs") {
        const body = await request.json();
        if (!body.run_id || !body.task_id || !body.mode || !body.search_mode) {
          return errorResponse("invalid_request", "Missing required run fields", 400);
        }
        const maxMicroUsd = typeof body.max_run_micro_usd === "number" ? body.max_run_micro_usd : 0;
        if (maxMicroUsd < 0) {
          return errorResponse("invalid_request", "max_run_micro_usd must be non-negative", 400);
        }
        const state = body.state || "queued";
        const now = (/* @__PURE__ */ new Date()).toISOString();
        const initialUsage = JSON.stringify({
          model_calls: 0,
          input_tokens: 0,
          output_tokens: 0,
          estimated_usd: 0
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
      const getRunMatch = pathname.match(/^\/api\/runs\/([^/]+)$/);
      if (method === "GET" && getRunMatch) {
        const runId = decodeURIComponent(getRunMatch[1]);
        const run = await env.DB.prepare(
          "SELECT run_id, task_id, mode, search_mode, state, reason, usage_json FROM runs WHERE run_id = ?"
        ).bind(runId).first();
        if (!run) {
          return errorResponse("not_found", "Run not found", 404);
        }
        const artifactsResult = await env.DB.prepare(
          "SELECT artifact_id, kind, filename FROM artifacts WHERE run_id = ? ORDER BY created_at ASC"
        ).bind(runId).all();
        let usage = { model_calls: 0, input_tokens: 0, output_tokens: 0, estimated_usd: 0 };
        try {
          usage = JSON.parse(run.usage_json);
        } catch {
        }
        return jsonResponse({
          run_id: run.run_id,
          task_id: run.task_id,
          mode: run.mode,
          search_mode: run.search_mode,
          state: run.state,
          reason: run.reason,
          usage,
          artifacts: artifactsResult.results || []
        }, 200);
      }
      if (method === "PATCH" && getRunMatch) {
        const runId = decodeURIComponent(getRunMatch[1]);
        const body = await request.json();
        if (!body.state) {
          return errorResponse("invalid_request", "State is required", 400);
        }
        const allowedStates = ["queued", "running", "succeeded", "failed", "cancelled"];
        if (!allowedStates.includes(body.state)) {
          return errorResponse("invalid_state", `Invalid state '${body.state}'`, 400);
        }
        const run = await env.DB.prepare("SELECT state FROM runs WHERE run_id = ?").bind(runId).first();
        if (!run) {
          return errorResponse("not_found", "Run not found", 404);
        }
        const terminalStates = ["succeeded", "failed", "cancelled"];
        if (terminalStates.includes(run.state)) {
          return errorResponse("terminal_state_immutable", `Cannot transition run from terminal state '${run.state}'`, 409);
        }
        const now = (/* @__PURE__ */ new Date()).toISOString();
        const reason = body.reason !== void 0 ? body.reason : null;
        await env.DB.prepare(
          "UPDATE runs SET state = ?, reason = ?, updated_at = ? WHERE run_id = ?"
        ).bind(body.state, reason, now, runId).run();
        return jsonResponse({ ok: true }, 200);
      }
      const eventsMatch = pathname.match(/^\/api\/runs\/([^/]+)\/events$/);
      if (method === "POST" && eventsMatch) {
        const runId = decodeURIComponent(eventsMatch[1]);
        const body = await request.json();
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
        const now = (/* @__PURE__ */ new Date()).toISOString();
        const payloadJson = JSON.stringify(body.payload);
        const res = await env.DB.prepare(
          `INSERT INTO events (run_id, seq, ts, type, payload_json)
           VALUES (?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE run_id = ?), ?, ?, ?)
           RETURNING seq, ts`
        ).bind(runId, runId, now, body.type, payloadJson).first();
        if (!res) {
          return errorResponse("internal_error", "Failed to insert event", 500);
        }
        return jsonResponse({ ok: true, seq: res.seq, ts: res.ts }, 201);
      }
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
        ).bind(runId, after).all();
        const events = (result.results || []).map((row) => {
          let payload = {};
          try {
            payload = JSON.parse(row.payload_json);
          } catch {
            payload = row.payload_json;
          }
          return {
            seq: row.seq,
            type: row.type,
            payload,
            ts: row.ts
          };
        });
        return jsonResponse({ events }, 200);
      }
      const artifactsMatch = pathname.match(/^\/api\/runs\/([^/]+)\/artifacts$/);
      if (method === "POST" && artifactsMatch) {
        const runId = decodeURIComponent(artifactsMatch[1]);
        const body = await request.json();
        if (!body.artifact_id || !body.kind || !body.filename || !body.sha256 || typeof body.size_bytes !== "number" || !body.content_base64) {
          return errorResponse("invalid_request", "Missing required artifact fields", 400);
        }
        if (body.size_bytes > 1048576) {
          return errorResponse("artifact_size_limit_exceeded", "Individual artifact exceeds limit of 1048576 bytes", 413);
        }
        const run = await env.DB.prepare("SELECT 1 FROM runs WHERE run_id = ?").bind(runId).first();
        if (!run) {
          return errorResponse("not_found", "Run not found", 404);
        }
        const now = (/* @__PURE__ */ new Date()).toISOString();
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
      const artifactDetailMatch = pathname.match(/^\/api\/runs\/([^/]+)\/artifacts\/([^/]+)$/);
      if (method === "GET" && artifactDetailMatch) {
        const runId = decodeURIComponent(artifactDetailMatch[1]);
        const artifactId = decodeURIComponent(artifactDetailMatch[2]);
        const artifact = await env.DB.prepare(
          "SELECT artifact_id, kind, filename, sha256, size_bytes, content_base64 FROM artifacts WHERE run_id = ? AND artifact_id = ?"
        ).bind(runId, artifactId).first();
        if (!artifact) {
          return errorResponse("not_found", "Artifact not found", 404);
        }
        return jsonResponse(artifact, 200);
      }
      const opsMatch = pathname.match(/^\/api\/runs\/([^/]+)\/operations$/);
      if (method === "POST" && opsMatch) {
        const runId = decodeURIComponent(opsMatch[1]);
        const body = await request.json();
        if (!body.operation_id || !body.kind || typeof body.reserved_micro_usd !== "number") {
          return errorResponse("invalid_request", "Missing required operation fields", 400);
        }
        if (body.reserved_micro_usd < 0) {
          return errorResponse("invalid_request", "reserved_micro_usd must be non-negative", 400);
        }
        const run = await env.DB.prepare(
          "SELECT max_run_micro_usd FROM runs WHERE run_id = ?"
        ).bind(runId).first();
        if (!run) {
          return errorResponse("not_found", "Run not found", 404);
        }
        const now = (/* @__PURE__ */ new Date()).toISOString();
        const insertResult = await env.DB.prepare(
          `INSERT INTO operations (operation_id, run_id, kind, status, reserved_micro_usd, settled_micro_usd, provider_ref, created_at, updated_at)
           SELECT ?, ?, ?, 'reserved', ?, NULL, NULL, ?, ?
           WHERE (
             SELECT COALESCE(SUM(CASE WHEN status = 'settled' THEN settled_micro_usd ELSE reserved_micro_usd END), 0)
             FROM operations
             WHERE run_id = ? AND status IN ('reserved', 'settled', 'uncertain')
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
          run.max_run_micro_usd
        ).run();
        if (!insertResult.meta || insertResult.meta.changes === 0) {
          return errorResponse("budget_limit_exceeded", "Requested reservation exceeds available run budget cap", 409);
        }
        return jsonResponse({ ok: true }, 201);
      }
      const opDetailMatch = pathname.match(/^\/api\/operations\/([^/]+)$/);
      if (method === "PATCH" && opDetailMatch) {
        const operationId = decodeURIComponent(opDetailMatch[1]);
        const body = await request.json();
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
        ).bind(operationId).first();
        if (!op) {
          return errorResponse("not_found", "Operation not found", 404);
        }
        const now = (/* @__PURE__ */ new Date()).toISOString();
        if (settled !== null) {
          if (op.status === "settled") {
            if (op.settled_micro_usd !== settled) {
              return errorResponse("operation_already_settled", "Operation is already settled with a different amount", 409);
            }
            return jsonResponse({ ok: true }, 200);
          }
          if (op.status !== "reserved" && op.status !== "uncertain") {
            return errorResponse("invalid_state", `Cannot settle operation in '${op.status}' state`, 409);
          }
          await env.DB.prepare(
            `UPDATE operations
             SET settled_micro_usd = ?, status = 'settled', updated_at = ?, provider_ref = COALESCE(?, provider_ref)
             WHERE operation_id = ?`
          ).bind(settled, now, providerRef, operationId).run();
        } else if (providerRef !== null) {
          if (op.status !== "reserved" && op.status !== "uncertain") {
            return errorResponse("invalid_state", `Cannot update provider_ref for operation in '${op.status}' state`, 409);
          }
          await updateOperationProviderRef(env.DB, operationId, providerRef, now);
        }
        return jsonResponse({ ok: true }, 200);
      }
      const opProviderRefMatch = pathname.match(/^\/api\/operations\/([^/]+)\/provider_ref$/);
      if (method === "PATCH" && opProviderRefMatch) {
        const operationId = decodeURIComponent(opProviderRefMatch[1]);
        const body = await request.json();
        if (!body.provider_ref || typeof body.provider_ref !== "string") {
          return errorResponse("invalid_request", "provider_ref must be a string", 400);
        }
        const op = await env.DB.prepare("SELECT operation_id, status FROM operations WHERE operation_id = ?").bind(operationId).first();
        if (!op) {
          return errorResponse("not_found", "Operation not found", 404);
        }
        if (op.status !== "reserved" && op.status !== "uncertain") {
          return errorResponse("invalid_state", `Cannot update provider_ref for operation in '${op.status}' state`, 409);
        }
        const now = (/* @__PURE__ */ new Date()).toISOString();
        await updateOperationProviderRef(env.DB, operationId, body.provider_ref, now);
        return jsonResponse({ ok: true }, 200);
      }
      return errorResponse("not_found", `Route '${method} ${pathname}' not found`, 404);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Internal database worker error";
      return errorResponse("internal_error", message, 500);
    }
  }
};

// node_modules/wrangler/templates/middleware/middleware-ensure-req-body-drained.ts
var drainBody = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } finally {
    try {
      if (request.body !== null && !request.bodyUsed) {
        const reader = request.body.getReader();
        while (!(await reader.read()).done) {
        }
      }
    } catch (e) {
      console.error("Failed to drain the unused request body.", e);
    }
  }
}, "drainBody");
var middleware_ensure_req_body_drained_default = drainBody;

// node_modules/wrangler/templates/middleware/middleware-miniflare3-json-error.ts
function reduceError(e) {
  return {
    name: e?.name,
    message: e?.message ?? String(e),
    stack: e?.stack,
    cause: e?.cause === void 0 ? void 0 : reduceError(e.cause)
  };
}
__name(reduceError, "reduceError");
var jsonError = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } catch (e) {
    const error = reduceError(e);
    return Response.json(error, {
      status: 500,
      headers: { "MF-Experimental-Error-Stack": "true" }
    });
  }
}, "jsonError");
var middleware_miniflare3_json_error_default = jsonError;

// .wrangler/tmp/bundle-mG681I/middleware-insertion-facade.js
var __INTERNAL_WRANGLER_MIDDLEWARE__ = [
  middleware_ensure_req_body_drained_default,
  middleware_miniflare3_json_error_default
];
var middleware_insertion_facade_default = src_default;

// node_modules/wrangler/templates/middleware/common.ts
var __facade_middleware__ = [];
function __facade_register__(...args) {
  __facade_middleware__.push(...args.flat());
}
__name(__facade_register__, "__facade_register__");
function __facade_invokeChain__(request, env, ctx, dispatch, middlewareChain) {
  const [head, ...tail] = middlewareChain;
  const middlewareCtx = {
    dispatch,
    next(newRequest, newEnv) {
      return __facade_invokeChain__(newRequest, newEnv, ctx, dispatch, tail);
    }
  };
  return head(request, env, ctx, middlewareCtx);
}
__name(__facade_invokeChain__, "__facade_invokeChain__");
function __facade_invoke__(request, env, ctx, dispatch, finalMiddleware) {
  return __facade_invokeChain__(request, env, ctx, dispatch, [
    ...__facade_middleware__,
    finalMiddleware
  ]);
}
__name(__facade_invoke__, "__facade_invoke__");

// .wrangler/tmp/bundle-mG681I/middleware-loader.entry.ts
var __Facade_ScheduledController__ = class {
  constructor(scheduledTime, cron, noRetry) {
    this.scheduledTime = scheduledTime;
    this.cron = cron;
    this.#noRetry = noRetry;
  }
  #noRetry;
  noRetry() {
    if (!(this instanceof __Facade_ScheduledController__)) {
      throw new TypeError("Illegal invocation");
    }
    this.#noRetry();
  }
};
__name(__Facade_ScheduledController__, "__Facade_ScheduledController__");
function wrapExportedHandler(worker) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return worker;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  const fetchDispatcher = /* @__PURE__ */ __name(function(request, env, ctx) {
    if (worker.fetch === void 0) {
      throw new Error("Handler does not export a fetch() function.");
    }
    return worker.fetch(request, env, ctx);
  }, "fetchDispatcher");
  return {
    ...worker,
    fetch(request, env, ctx) {
      const dispatcher = /* @__PURE__ */ __name(function(type, init) {
        if (type === "scheduled" && worker.scheduled !== void 0) {
          const controller = new __Facade_ScheduledController__(
            Date.now(),
            init.cron ?? "",
            () => {
            }
          );
          return worker.scheduled(controller, env, ctx);
        }
      }, "dispatcher");
      return __facade_invoke__(request, env, ctx, dispatcher, fetchDispatcher);
    }
  };
}
__name(wrapExportedHandler, "wrapExportedHandler");
function wrapWorkerEntrypoint(klass) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return klass;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  return class extends klass {
    #fetchDispatcher = (request, env, ctx) => {
      this.env = env;
      this.ctx = ctx;
      if (super.fetch === void 0) {
        throw new Error("Entrypoint class does not define a fetch() function.");
      }
      return super.fetch(request);
    };
    #dispatcher = (type, init) => {
      if (type === "scheduled" && super.scheduled !== void 0) {
        const controller = new __Facade_ScheduledController__(
          Date.now(),
          init.cron ?? "",
          () => {
          }
        );
        return super.scheduled(controller);
      }
    };
    fetch(request) {
      return __facade_invoke__(
        request,
        this.env,
        this.ctx,
        this.#dispatcher,
        this.#fetchDispatcher
      );
    }
  };
}
__name(wrapWorkerEntrypoint, "wrapWorkerEntrypoint");
var WRAPPED_ENTRY;
if (typeof middleware_insertion_facade_default === "object") {
  WRAPPED_ENTRY = wrapExportedHandler(middleware_insertion_facade_default);
} else if (typeof middleware_insertion_facade_default === "function") {
  WRAPPED_ENTRY = wrapWorkerEntrypoint(middleware_insertion_facade_default);
}
var middleware_loader_entry_default = WRAPPED_ENTRY;
export {
  __INTERNAL_WRANGLER_MIDDLEWARE__,
  middleware_loader_entry_default as default
};
//# sourceMappingURL=index.js.map
