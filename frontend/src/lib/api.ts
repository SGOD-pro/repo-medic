import {
  TaskSummary,
  RunSummary,
  SearchMode,
  Mode,
  APIErrorEnvelope,
  EventEnvelope,
  ArtifactKind,
  CustomRepositoryConfig,
  CustomConfigValidationResponse,
  SUPPORTED_DEMO_TASK_IDS,
} from "./contracts";
import { validateCustomRepositoryConfig } from "./validation";

export interface RepoMedicApiClient {
  getTasks(policy?: string): Promise<TaskSummary[]>;
  validateCustomConfig(config: CustomRepositoryConfig): Promise<CustomConfigValidationResponse>;
  startRun(taskId: string, searchMode: SearchMode, mode?: Mode, idempotencyKey?: string): Promise<RunSummary>;
  getRun(runId: string): Promise<RunSummary>;
  cancelRun(runId: string): Promise<RunSummary>;
  getRunEvents(runId: string, lastEventId?: string | null): Promise<EventEnvelope[]>;
  getArtifact(runId: string, artifactIdOrKind: ArtifactKind | string): Promise<string>;
}

export const SUPPORTED_DEMO_TASKS: TaskSummary[] = [
  {
    task_id: "TASK-DEMO-SHOP",
    title: "Upgrade sqlalchemy 1.4.48 to 2.0.19 in repomedic-demo-shop",
    repository_url: "https://github.com/SGOD-pro/repo-medic.git",
    commit_sha: "8c400721558392a23b3af71766f673da02f80040",
    dependency: "sqlalchemy",
    from_version: "1.4.48",
    to_version: "2.0.19",
  },
  {
    task_id: "TASK-091",
    title: "Upgrade sqlalchemy from 1.4.48 to 2.0.19 in backend-core",
    repository_url: "https://github.com/SGOD-pro/repo-medic.git",
    commit_sha: "453a0b6c6b125177504cdd941902b8d48266ed1c",
    dependency: "sqlalchemy",
    from_version: "1.4.48",
    to_version: "2.0.19",
  },
];

export const CURATED_TASKS: TaskSummary[] = [
  {
    task_id: "TASK-084",
    title: "pydantic v1.10.8 → v2.0.0 migration in fastapi-service",
    repository_url: "https://github.com/tiangolo/fastapi-service",
    commit_sha: "8a4f21d",
    dependency: "pydantic",
    from_version: "1.10.8",
    to_version: "2.0.0",
  },
  {
    task_id: "TASK-091",
    title: "sqlalchemy v1.4.48 → v2.0.19 in backend-core",
    repository_url: "https://github.com/pallets/backend-core",
    commit_sha: "c39b104",
    dependency: "sqlalchemy",
    from_version: "1.4.48",
    to_version: "2.0.19",
  },
  {
    task_id: "TASK-097",
    title: "httpx v0.23.3 → v0.24.1 in scraper-bot",
    repository_url: "https://github.com/encode/scraper-bot",
    commit_sha: "f72a110",
    dependency: "httpx",
    from_version: "0.23.3",
    to_version: "0.24.1",
  },
];

export const MOCK_PATCH = `--- a/src/app/schemas.py
+++ b/src/app/schemas.py
@@ -3,9 +3,8 @@
-from pydantic import BaseModel, Field
+from pydantic import BaseModel, Field, ConfigDict
 
 class AccountPayload(BaseModel):
     account_id: str
-    tenant_slug: str = Field(..., regex="^[a-zA-Z0-9]+$")
+    tenant_slug: str = Field(..., pattern="^[a-zA-Z0-9]+$")
     is_active: bool = True
-    class Config:
-        orm_mode = True
+    model_config = ConfigDict(from_attributes=True)
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -20,2 +20,3 @@
-    "pydantic>=1.10.8,<2.0.0",
+    "pydantic>=2.0.2,<3.0.0",
+    "pydantic-settings>=2.0.0",
`;

export const MOCK_EVIDENCE = {
  task_id: "TASK-084",
  status: "PASSED",
  ast_hash: "sha256:d8a261f9c09b8841a12e5661c478",
  tests_passed: 42,
  tests_failed: 0,
  execution_time: "24.2s",
  sandbox_id: "nb-sand-9941a",
  kernel: "Linux 6.2-cgroup2",
  contract_assertions: 2,
  model: "Nemotron-70B",
  cost_usd: 0.04,
};

export const MOCK_LOG = `[00:01.12] sandbox: creating isolated container environment (python 3.11, pydantic 2.0.2)
[00:03.45] agent: generating patch for src/app/schemas.py
[00:08.20] verifier: applying untrusted patch to clean repo
[00:09.11] verifier: ast check passed (0 test files modified, source allowlist respected)
[00:14.30] pytest: running full test suite (42 tests)...
[00:22.04] pytest: test_users_schema.py::test_validation PASSED
[00:23.95] pytest: ================= 42 passed in 1.48s =================
[00:24.20] verifier: candidate A verified successfully`;

export class MockTransport implements RepoMedicApiClient {
  private activeRuns: Map<string, RunSummary> = new Map();

  async getTasks(policy?: string): Promise<TaskSummary[]> {
    if (policy === "supported_demo") {
      return Promise.resolve(SUPPORTED_DEMO_TASKS);
    }
    return Promise.resolve(CURATED_TASKS);
  }

  async validateCustomConfig(
    config: CustomRepositoryConfig
  ): Promise<CustomConfigValidationResponse> {
    return Promise.resolve(validateCustomRepositoryConfig(config));
  }

  async startRun(
    taskId: string,
    searchMode: SearchMode,
    mode?: Mode,
    _idempotencyKey?: string
  ): Promise<RunSummary> {
    const task = CURATED_TASKS.find((t) => t.task_id === taskId) || CURATED_TASKS[0];
    const runId = `run_${task.task_id.toLowerCase().replace("-", "_")}_${Date.now()}`;
    const run: RunSummary = {
      run_id: runId,
      task_id: task.task_id,
      mode: (mode || "live") as Mode,
      search_mode: searchMode,
      state: "running",
      reason: null,
      usage: {
        model_calls: 3,
        input_tokens: 14200,
        output_tokens: 2840,
        estimated_usd: 0.18,
      },
      artifacts: [
        {
          artifact_id: "art_patch_01",
          kind: "patch",
          filename: "repomedic-fix.patch",
        },
        {
          artifact_id: "art_evidence_01",
          kind: "evidence",
          filename: "verification-evidence.json",
        },
        {
          artifact_id: "art_log_01",
          kind: "log",
          filename: "container-eval-candidate-a.log",
        },
      ],
    };
    this.activeRuns.set(runId, run);
    return Promise.resolve(run);
  }

  async getRun(runId: string): Promise<RunSummary> {
    const run = this.activeRuns.get(runId);
    if (!run) {
      if (runId === "run-success-1") {
        return Promise.resolve({
          run_id: "run-success-1",
          task_id: "TASK-084",
          mode: "live" as Mode,
          search_mode: "branch_refine",
          state: "succeeded",
          reason: null,
          usage: {
            model_calls: 3,
            input_tokens: 14200,
            output_tokens: 2840,
            estimated_usd: 0.18,
          },
          artifacts: [
            {
              artifact_id: "art_patch_01",
              kind: "patch",
              filename: "repomedic-fix.patch",
            },
            {
              artifact_id: "art_evidence_01",
              kind: "evidence",
              filename: "verification-evidence.json",
            },
            {
              artifact_id: "art_log_01",
              kind: "log",
              filename: "container-eval-candidate-a.log",
            },
          ],
        });
      }
      if (runId === "run-fail-1") {
        return Promise.resolve({
          run_id: "run-fail-1",
          task_id: "TASK-091",
          mode: "offline" as Mode,
          search_mode: "sequential",
          state: "failed",
          reason: "Verification tests failed on candidate matrix",
          usage: {
            model_calls: 2,
            input_tokens: 9500,
            output_tokens: 1900,
            estimated_usd: 0.12,
          },
          artifacts: [],
        });
      }
      if (runId === "run-cancel-1") {
        return Promise.resolve({
          run_id: "run-cancel-1",
          task_id: "TASK-097",
          mode: "live" as Mode,
          search_mode: "branch_refine",
          state: "cancelled",
          reason: "User initiated cancellation",
          usage: {
            model_calls: 1,
            input_tokens: 2100,
            output_tokens: 350,
            estimated_usd: 0.02,
          },
          artifacts: [],
        });
      }
      return this.startRun("TASK-084", "branch_refine");
    }
    return Promise.resolve(run);
  }

  async cancelRun(runId: string): Promise<RunSummary> {
    const run = await this.getRun(runId);
    run.state = "cancelled";
    run.reason = "User initiated cancellation";
    this.activeRuns.set(runId, run);
    return Promise.resolve(run);
  }

  async getRunEvents(runId: string, lastEventId?: string | null): Promise<EventEnvelope[]> {
    const now = new Date().toISOString();
    const allEvents: EventEnvelope[] = [
      {
        run_id: runId,
        seq: 1,
        ts: now,
        type: "run.started",
        payload: { mode: "live", search_mode: "branch_refine", max_run_usd: 0.5 },
      },
      {
        run_id: runId,
        seq: 2,
        ts: now,
        type: "stage.completed",
        payload: { stage: "baseline", passed: true, summary: "42/42 tests pass on pinned commit" },
      },
      {
        run_id: runId,
        seq: 3,
        ts: now,
        type: "stage.completed",
        payload: { stage: "upgrade", passed: true, summary: "Expected upgrade failure confirmed" },
      },
      {
        run_id: runId,
        seq: 4,
        ts: now,
        type: "stage.completed",
        payload: { stage: "repair", passed: true, summary: "Bounded context extracted" },
      },
      {
        run_id: runId,
        seq: 5,
        ts: now,
        type: "candidate.completed",
        payload: { candidate_id: "cand_a", passed: true, summary: "Candidate A verified successfully" },
      },
      {
        run_id: runId,
        seq: 6,
        ts: now,
        type: "usage.updated",
        payload: { model_calls: 3, input_tokens: 14200, output_tokens: 2840, estimated_usd: 0.18 },
      },
    ];

    if (!lastEventId) {
      return Promise.resolve(allEvents);
    }
    const lastSeq = Number(lastEventId);
    return Promise.resolve(
      isNaN(lastSeq) ? allEvents : allEvents.filter((e) => e.seq > lastSeq)
    );
  }

  async getArtifact(_runId: string, artifactIdOrKind: ArtifactKind | string): Promise<string> {
    if (
      artifactIdOrKind === "patch" ||
      artifactIdOrKind.includes("patch") ||
      artifactIdOrKind.endsWith(".diff") ||
      artifactIdOrKind.endsWith(".patch") ||
      artifactIdOrKind === "art_patch_01"
    ) {
      return Promise.resolve(MOCK_PATCH);
    }
    if (
      artifactIdOrKind === "evidence" ||
      artifactIdOrKind.includes("evidence") ||
      artifactIdOrKind.endsWith(".json") ||
      artifactIdOrKind === "art_evidence_01"
    ) {
      return Promise.resolve(JSON.stringify(MOCK_EVIDENCE, null, 2));
    }
    return Promise.resolve(MOCK_LOG);
  }
}

export class HttpTransport implements RepoMedicApiClient {
  private baseUrl: string;

  constructor(baseUrl = "/api") {
    this.baseUrl = baseUrl;
  }

  async getTasks(policy = "supported_demo"): Promise<TaskSummary[]> {
    const url = policy
      ? `${this.baseUrl}/tasks?policy=${encodeURIComponent(policy)}`
      : `${this.baseUrl}/tasks`;
    const res = await fetch(url);
    if (!res.ok) {
      const err: APIErrorEnvelope = await res.json().catch(() => ({
        error: { code: "unavailable", message: "Failed to fetch tasks" },
      }));
      throw new Error(err.error.message);
    }
    const data = await res.json();
    let tasks: TaskSummary[] = data.tasks || [];
    if (policy === "supported_demo") {
      tasks = tasks.filter(
        (t) =>
          SUPPORTED_DEMO_TASK_IDS.includes(t.task_id) &&
          !t.repository_url?.toLowerCase().includes("example")
      );
      if (tasks.length === 0) {
        tasks = SUPPORTED_DEMO_TASKS;
      }
    }
    return tasks;
  }

  async validateCustomConfig(
    config: CustomRepositoryConfig
  ): Promise<CustomConfigValidationResponse> {
    const res = await fetch(`${this.baseUrl}/custom/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({
        error: { code: "validation_failed", message: "Validation endpoint error" },
      }));
      throw new Error(err?.error?.message || err?.detail || "Validation failed");
    }
    return res.json();
  }

  async startRun(
    taskId: string,
    searchMode: SearchMode,
    mode?: Mode,
    idempotencyKey?: string
  ): Promise<RunSummary> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }
    const res = await fetch(`${this.baseUrl}/runs`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        task_id: taskId,
        search_mode: searchMode,
        ...(mode ? { mode } : {}),
        ...(idempotencyKey ? { idempotency_key: idempotencyKey } : {}),
      }),
    });
    if (!res.ok) {
      const err: APIErrorEnvelope = await res.json().catch(() => ({
        error: { code: "unavailable", message: "Failed to start run" },
      }));
      throw new Error(err.error.message);
    }
    return res.json();
  }

  async getRun(runId: string): Promise<RunSummary> {
    const res = await fetch(`${this.baseUrl}/runs/${runId}`);
    if (!res.ok) {
      const err: APIErrorEnvelope = await res.json().catch(() => ({
        error: { code: "not_found", message: "Run not found" },
      }));
      throw new Error(err.error.message);
    }
    return res.json();
  }

  async cancelRun(runId: string): Promise<RunSummary> {
    const res = await fetch(`${this.baseUrl}/runs/${runId}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      const err: APIErrorEnvelope = await res.json().catch(() => ({
        error: { code: "unavailable", message: "Failed to cancel run" },
      }));
      throw new Error(err.error.message);
    }
    return res.json();
  }

  async getRunEvents(runId: string, lastEventId?: string | null): Promise<EventEnvelope[]> {
    const headers: Record<string, string> = {};
    if (lastEventId) {
      headers["Last-Event-ID"] = lastEventId;
    }
    const res = await fetch(`${this.baseUrl}/runs/${runId}/events`, { headers });
    if (!res.ok) {
      throw new Error("Failed to fetch run events");
    }
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("text/event-stream")) {
      const text = await res.text();
      const events: EventEnvelope[] = [];
      const parts = text.split("\n\n");
      for (const part of parts) {
        if (!part.trim() || part.startsWith(":")) continue;
        for (const line of part.split("\n")) {
          if (line.startsWith("data: ")) {
            try {
              events.push(JSON.parse(line.slice(6)));
            } catch {
              // ignore
            }
          } else if (line.startsWith("data:")) {
            try {
              events.push(JSON.parse(line.slice(5)));
            } catch {
              // ignore
            }
          }
        }
      }
      return events;
    }
    const data = await res.json();
    return data.events || [];
  }

  async getArtifact(runId: string, artifactIdOrKind: ArtifactKind | string): Promise<string> {
    const res = await fetch(`${this.baseUrl}/runs/${runId}/artifacts/${artifactIdOrKind}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch ${artifactIdOrKind} artifact`);
    }
    return res.text();
  }
}

export function createEventStreamFetcher(
  apiClient: RepoMedicApiClient,
  runId: string,
  baseUrl = process.env.NEXT_PUBLIC_API_URL || "/api"
): (lastEventId: string | null) => AsyncIterable<EventEnvelope> {
  return async function* (lastEventId: string | null): AsyncIterable<EventEnvelope> {
    if (typeof window !== "undefined" && typeof fetch === "function") {
      const transportType = process.env.NEXT_PUBLIC_API_TRANSPORT || "mock";
      if (transportType === "http") {
        const headers: Record<string, string> = {
          Accept: "text/event-stream",
        };
        if (lastEventId) {
          headers["Last-Event-ID"] = lastEventId;
        }
        const res = await fetch(`${baseUrl}/runs/${runId}/events`, { headers });
        if (!res.ok) {
          throw new Error(`Event stream request failed with status ${res.status}`);
        }
        if (res.body && typeof res.body.getReader === "function") {
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              buffer += decoder.decode(value, { stream: true });
              const blocks = buffer.split("\n\n");
              buffer = blocks.pop() ?? "";
              for (const block of blocks) {
                if (!block.trim() || block.startsWith(":")) continue;
                for (const line of block.split("\n")) {
                  if (line.startsWith("data: ")) {
                    try {
                      yield JSON.parse(line.slice(6));
                    } catch {
                      // skip
                    }
                  } else if (line.startsWith("data:")) {
                    try {
                      yield JSON.parse(line.slice(5));
                    } catch {
                      // skip
                    }
                  }
                }
              }
            }
          } finally {
            reader.releaseLock();
          }
          return;
        }
      }
    }
    const events = await apiClient.getRunEvents(runId, lastEventId);
    for (const ev of events) {
      yield ev;
    }
  };
}

export function createApiClient(): RepoMedicApiClient {
  const defaultTransport = process.env.NODE_ENV === "production" ? "http" : "mock";
  const transportType = process.env.NEXT_PUBLIC_API_TRANSPORT || defaultTransport;
  if (transportType === "http") {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "/api";
    return new HttpTransport(apiUrl);
  }
  return new MockTransport();
}
