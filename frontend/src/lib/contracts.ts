export type Mode = "offline" | "replay" | "live";
export type SearchMode = "sequential" | "branch_refine";
export type RunState = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type TerminalRunState = "succeeded" | "failed" | "cancelled";
export type ArtifactKind = "patch" | "evidence" | "log";
export type StageName = "baseline" | "upgrade" | "repair" | "verification";

export const SUPPORTED_DEMO_TASK_IDS: readonly string[] = [
  "TASK-DEMO-SHOP",
  "TASK-091",
  "TASK-DEMO-PYDANTIC",
  "TASK-DEMO-CLICK",
  "TASK-DEMO-JWT",
];

export const APPROVED_DEMO_TASK_IDS: readonly string[] = [
  "TASK-DEMO-SHOP",
  "TASK-DEMO-PYDANTIC",
  "TASK-DEMO-CLICK",
  "TASK-DEMO-JWT",
];

export interface CustomRepositoryConfig {
  repository_url: string;
  commit_sha: string;
  dependency: string;
  from_version: string;
  to_version: string;
  pytest_args: string[];
  allowed_source_paths: string[];
  expected_failure: string;
}

export interface CustomConfigValidationResponse {
  valid: boolean;
  errors: string[];
  field_errors: Record<string, string[]>;
  custom_execution_supported: boolean;
  gate_status: string;
  gate_message: string;
}

export interface TaskSummary {
  task_id: string;
  title: string;
  repository_url: string;
  commit_sha: string;
  dependency: string;
  from_version: string;
  to_version: string;
}

export interface TaskRecipe extends TaskSummary {
  test_command: string[];
  allowed_source_paths: string[];
  expected_failure: string;
  timeout_seconds: number;
  max_candidates: number;
  max_refinements: number;
}

export interface ArtifactSummary {
  artifact_id: string;
  kind: ArtifactKind;
  filename: string;
}

export interface UsageSummary {
  model_calls: number;
  input_tokens: number;
  output_tokens: number;
  estimated_usd: number;
}

export interface RunSummary {
  run_id: string;
  task_id: string;
  mode: Mode;
  search_mode: SearchMode;
  state: RunState;
  reason: string | null;
  usage: UsageSummary;
  artifacts: ArtifactSummary[];
  error?: ErrorDetail | null;
  connection_status?: ConnectionStatus;
}

export type RunDetail = RunSummary;

export interface RunHistoryItem {
  run_id: string;
  state: RunState;
}

export interface RepairRequest {
  run_id: string;
  task_id: string;
  mode: Mode;
  search_mode: SearchMode;
  max_run_usd: number;
}

export interface RepairResult {
  state: TerminalRunState;
  reason: string | null;
}

export type EventType =
  | "run.started"
  | "stage.completed"
  | "candidate.completed"
  | "usage.updated"
  | "run.finished"
  | "run.error"
  | "run.cancelled";

export interface RunStartedPayload {
  mode: Mode;
  search_mode: SearchMode;
  max_run_usd: number;
}

export interface StageCompletedPayload {
  stage: StageName;
  passed: boolean;
  summary: string;
}

export interface CandidateCompletedPayload {
  candidate_id: string;
  passed: boolean;
  summary: string;
}

export type UsageUpdatedPayload = UsageSummary;

export interface RunFinishedPayload {
  state: TerminalRunState;
  reason: string | null;
}

export interface RunErrorPayload {
  code: string;
  message: string;
  traceback?: string | null;
  recoverable?: boolean;
}

export interface RunCancelledPayload {
  reason: string | null;
}

export interface EventEnvelope {
  run_id: string;
  seq: number;
  ts: string;
  type: EventType;
  payload: Record<string, unknown>;
}

export type Event = EventEnvelope;

export interface ReconnectResult {
  run_id: string;
  events: EventEnvelope[];
}

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

export interface ErrorDetail {
  code: string;
  message: string;
  traceback?: string | null;
  timestamp: string;
  recoverable?: boolean;
}

export interface StreamManagerConfig {
  max_retries: number;
  backoff_intervals: number[];
  last_event_id: string | null;
}

export interface APIErrorDetail {
  code: string;
  message: string;
  traceback?: string | null;
}

export interface APIErrorEnvelope {
  error: APIErrorDetail;
}

