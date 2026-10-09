export type Mode = "offline" | "replay" | "live";
export type SearchMode = "sequential" | "branch_refine";
export type RunState = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type TerminalRunState = "succeeded" | "failed" | "cancelled";
export type ArtifactKind = "patch" | "evidence" | "log";
export type StageName = "baseline" | "upgrade" | "repair" | "verification";

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
  | "run.finished";

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

export interface APIErrorDetail {
  code: string;
  message: string;
}

export interface APIErrorEnvelope {
  error: APIErrorDetail;
}
