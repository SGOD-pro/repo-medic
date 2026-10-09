export type Mode = "offline" | "replay" | "live";
export type State = "succeeded" | "failed" | "cancelled";

export interface TaskSummary {
  task_id: string;
  repository: string;
  commit: string;
}

export interface TaskRecipe extends TaskSummary {
  test_command: string[];
  allowed_source_paths: string[];
  expected_failure: string;
  timeout_seconds: number;
  max_candidates: number;
  max_refinements: number;
}

export interface RepairRequest {
  run_id: string;
  task_id: string;
  mode: Mode;
  search_mode: string;
  max_run_usd: number;
}

export interface RepairResult {
  state: State;
  reason?: string;
}

export interface RunDetail extends RepairRequest, RepairResult {}

export interface RunHistoryItem {
  run_id: string;
  state: State;
}

export interface EventPayload {
  message: string;
}

export interface Event {
  seq: number;
  type: string;
  payload: EventPayload;
}

export interface ReconnectResult {
  run_id: string;
  events: Event[];
}
