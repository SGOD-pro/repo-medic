import {
  TaskRecipe,
  RunSummary,
  ReconnectResult,
  RunHistoryItem,
  EventEnvelope,
  RunState,
  Mode,
  SearchMode,
  EventType,
  CustomRepositoryConfig,
  CustomConfigValidationResponse,
} from './contracts';

const VALID_MODES: Set<Mode> = new Set(["offline", "replay", "live"]);
const VALID_SEARCH_MODES: Set<SearchMode> = new Set(["sequential", "branch_refine"]);
const VALID_RUN_STATES: Set<RunState> = new Set([
  "queued",
  "running",
  "succeeded",
  "failed",
  "cancelled",
]);
const VALID_EVENT_TYPES: Set<EventType> = new Set([
  "run.started",
  "stage.completed",
  "candidate.completed",
  "usage.updated",
  "run.finished",
]);

type Dict = Record<string, unknown>;

function isObject(val: unknown): val is Dict {
  return typeof val === 'object' && val !== null && !Array.isArray(val);
}

export function validateTaskRecipe(input: unknown): TaskRecipe {
  if (!isObject(input)) throw new Error("TaskRecipe must be an object");
  const data = input;
  if (typeof data.task_id !== 'string' || !data.task_id) throw new Error("task_id must be a non-empty string");
  if (typeof data.title !== 'string') throw new Error("title must be a string");
  if (typeof data.repository_url !== 'string') throw new Error("repository_url must be a string");
  if (typeof data.commit_sha !== 'string') throw new Error("commit_sha must be a string");
  if (typeof data.dependency !== 'string') throw new Error("dependency must be a string");
  if (typeof data.from_version !== 'string') throw new Error("from_version must be a string");
  if (typeof data.to_version !== 'string') throw new Error("to_version must be a string");

  if (!Array.isArray(data.test_command) || data.test_command.length === 0) {
    throw new Error("test_command must be a non-empty string array");
  }
  if (!Array.isArray(data.allowed_source_paths)) {
    throw new Error("allowed_source_paths must be an array");
  }
  if (typeof data.expected_failure !== 'string') {
    throw new Error("expected_failure must be a string");
  }
  if (typeof data.timeout_seconds !== 'number' || data.timeout_seconds <= 0) {
    throw new Error("timeout_seconds must be a positive number");
  }
  if (typeof data.max_candidates !== 'number' || data.max_candidates <= 0) {
    throw new Error("max_candidates must be a positive number");
  }
  if (typeof data.max_refinements !== 'number' || data.max_refinements < 0) {
    throw new Error("max_refinements must be a non-negative number");
  }

  return input as unknown as TaskRecipe;
}

export function validateRunSummary(input: unknown): RunSummary {
  if (!isObject(input)) throw new Error("RunSummary must be an object");
  const data = input;
  if (typeof data.run_id !== 'string' || !data.run_id) throw new Error("run_id must be a non-empty string");
  if (typeof data.task_id !== 'string' || !data.task_id) throw new Error("task_id must be a non-empty string");
  if (!VALID_MODES.has(data.mode as Mode)) throw new Error(`Invalid mode: ${String(data.mode)}`);
  if (!VALID_SEARCH_MODES.has(data.search_mode as SearchMode)) throw new Error(`Invalid search_mode: ${String(data.search_mode)}`);
  if (!VALID_RUN_STATES.has(data.state as RunState)) throw new Error(`Invalid state: ${String(data.state)}`);

  if (data.reason !== null && typeof data.reason !== 'string' && data.reason !== undefined) {
    throw new Error("reason must be null or string");
  }

  if (!isObject(data.usage)) throw new Error("usage must be an object");
  const usage = data.usage;
  if (typeof usage.model_calls !== 'number' || usage.model_calls < 0) {
    throw new Error("usage.model_calls must be a non-negative number");
  }
  if (typeof usage.input_tokens !== 'number' || usage.input_tokens < 0) {
    throw new Error("usage.input_tokens must be a non-negative number");
  }
  if (typeof usage.output_tokens !== 'number' || usage.output_tokens < 0) {
    throw new Error("usage.output_tokens must be a non-negative number");
  }
  if (typeof usage.estimated_usd !== 'number' || usage.estimated_usd < 0) {
    throw new Error("usage.estimated_usd must be a non-negative number");
  }

  if (!Array.isArray(data.artifacts)) {
    throw new Error("artifacts must be an array");
  }
  for (const art of data.artifacts) {
    if (!isObject(art)) throw new Error("artifact must be an object");
    if (typeof art.artifact_id !== 'string' || !art.artifact_id) throw new Error("artifact_id must be a non-empty string");
    if (typeof art.kind !== 'string' || !["patch", "evidence", "log"].includes(art.kind)) {
      throw new Error(`Invalid artifact kind: ${String(art.kind)}`);
    }
    if (typeof art.filename !== 'string' || !art.filename) throw new Error("filename must be a non-empty string");
  }

  return input as unknown as RunSummary;
}

export function validateEventEnvelope(input: unknown): EventEnvelope {
  if (!isObject(input)) throw new Error("Event must be an object");
  const data = input;
  if (typeof data.run_id !== 'string' || !data.run_id) throw new Error("run_id must be a non-empty string");
  if (typeof data.seq !== 'number' || data.seq < 1) throw new Error("seq must be an integer >= 1");
  if (typeof data.ts !== 'string' || !data.ts) throw new Error("ts must be a timestamp string");
  if (!VALID_EVENT_TYPES.has(data.type as EventType)) throw new Error(`Invalid event type: ${String(data.type)}`);
  if (!isObject(data.payload) || Object.keys(data.payload).length === 0) {
    throw new Error(`payload for event type ${String(data.type)} must be a non-empty object`);
  }

  const p = data.payload;
  switch (data.type) {
    case "run.started":
      if (!VALID_MODES.has(p.mode as Mode)) throw new Error("run.started payload requires valid mode");
      if (!VALID_SEARCH_MODES.has(p.search_mode as SearchMode)) throw new Error("run.started payload requires valid search_mode");
      if (typeof p.max_run_usd !== 'number' || p.max_run_usd < 0) throw new Error("run.started payload requires non-negative max_run_usd");
      break;
    case "stage.completed":
      if (!["baseline", "upgrade", "repair", "verification"].includes(p.stage as string)) {
        throw new Error("stage.completed payload requires valid stage name");
      }
      if (typeof p.passed !== 'boolean') throw new Error("stage.completed payload requires boolean passed");
      if (typeof p.summary !== 'string') throw new Error("stage.completed payload requires string summary");
      break;
    case "candidate.completed":
      if (typeof p.candidate_id !== 'string' || !p.candidate_id) {
        throw new Error("candidate.completed payload requires candidate_id string");
      }
      if (typeof p.passed !== 'boolean') throw new Error("candidate.completed payload requires boolean passed");
      if (typeof p.summary !== 'string') throw new Error("candidate.completed payload requires string summary");
      break;
    case "usage.updated":
      if (typeof p.model_calls !== 'number' || p.model_calls < 0) throw new Error("usage.updated payload requires non-negative model_calls");
      if (typeof p.input_tokens !== 'number' || p.input_tokens < 0) throw new Error("usage.updated payload requires non-negative input_tokens");
      if (typeof p.output_tokens !== 'number' || p.output_tokens < 0) throw new Error("usage.updated payload requires non-negative output_tokens");
      if (typeof p.estimated_usd !== 'number' || p.estimated_usd < 0) throw new Error("usage.updated payload requires non-negative estimated_usd");
      break;
    case "run.finished":
      if (!["succeeded", "failed", "cancelled"].includes(p.state as string)) {
        throw new Error("run.finished payload requires terminal state");
      }
      if (p.reason !== null && typeof p.reason !== 'string' && p.reason !== undefined) {
        throw new Error("run.finished payload reason must be string or null");
      }
      break;
  }

  return input as unknown as EventEnvelope;
}

export function validateReconnectResult(input: unknown): ReconnectResult {
  if (!isObject(input)) throw new Error("ReconnectResult must be an object");
  const data = input;
  if (typeof data.run_id !== 'string' || !data.run_id) throw new Error("run_id must be a non-empty string");
  if (!Array.isArray(data.events)) throw new Error("events must be an array");
  for (const ev of data.events) {
    validateEventEnvelope(ev);
  }
  return input as unknown as ReconnectResult;
}

export function validateRunHistory(input: unknown): RunHistoryItem[] {
  if (!Array.isArray(input)) throw new Error("History must be an array");
  for (const item of input) {
    if (!isObject(item)) throw new Error("History item must be an object");
    if (typeof item.run_id !== 'string' || !item.run_id) throw new Error("run_id must be string");
    if (!VALID_RUN_STATES.has(item.state as RunState)) throw new Error(`Invalid state: ${String(item.state)}`);
  }
  return input as unknown as RunHistoryItem[];
}

const GITHUB_HTTPS_REGEX = /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+(?:\.git)?\/?$/;
const HEX_40_REGEX = /^[0-9a-fA-F]{40}$/;
const PYTHON_PACKAGE_REGEX = /^[a-zA-Z0-9_.-]+$/;
const DANGEROUS_COMMAND_REGEX = /(?:^|[;&|\s])(?:sh|bash|zsh|curl|wget|rm|sudo|chmod|eval|exec|python\s+-c)(?:$|[;&|\s])|[;&|><`$]/;

export function validateCustomRepositoryConfig(
  config: Partial<CustomRepositoryConfig>
): CustomConfigValidationResponse {
  const errors: string[] = [];
  const fieldErrors: Record<string, string[]> = {};

  const addError = (field: string, msg: string) => {
    errors.push(msg);
    if (!fieldErrors[field]) {
      fieldErrors[field] = [];
    }
    fieldErrors[field].push(msg);
  };

  // Repository URL validation
  const repoUrl = (config.repository_url || "").trim();
  if (!repoUrl) {
    addError("repository_url", "Repository URL is required");
  } else if (!GITHUB_HTTPS_REGEX.test(repoUrl)) {
    addError(
      "repository_url",
      "Repository URL must be a public GitHub HTTPS URL (e.g. https://github.com/owner/repo)"
    );
  }

  // Commit SHA validation
  const commitSha = (config.commit_sha || "").trim();
  if (!commitSha) {
    addError("commit_sha", "Commit SHA is required");
  } else if (!HEX_40_REGEX.test(commitSha)) {
    addError(
      "commit_sha",
      "Commit SHA must be a full 40 character hexadecimal string"
    );
  }

  // Dependency name validation
  const dependency = (config.dependency || "").trim();
  if (!dependency) {
    addError("dependency", "Dependency name is required");
  } else if (!PYTHON_PACKAGE_REGEX.test(dependency)) {
    addError(
      "dependency",
      "Dependency name must be a valid Python package name"
    );
  }

  // Baseline version validation
  const fromVersion = (config.from_version || "").trim();
  if (!fromVersion) {
    addError("from_version", "Baseline version is required");
  }

  // Target version validation
  const toVersion = (config.to_version || "").trim();
  if (!toVersion) {
    addError("to_version", "Target version is required");
  } else if (fromVersion && toVersion === fromVersion) {
    addError("to_version", "Target version must differ from baseline version");
  }

  // Pytest args validation
  if (!config.pytest_args || !Array.isArray(config.pytest_args)) {
    addError("pytest_args", "Pytest arguments list cannot be empty");
  } else {
    let hasNonEmpty = false;
    let hasUnsafe = false;
    for (const arg of config.pytest_args) {
      if (typeof arg !== "string") {
        hasUnsafe = true;
        continue;
      }
      const trimmed = arg.trim();
      if (trimmed) {
        hasNonEmpty = true;
        if (DANGEROUS_COMMAND_REGEX.test(trimmed)) {
          hasUnsafe = true;
        }
      }
    }
    if (!hasNonEmpty) {
      addError("pytest_args", "Pytest arguments list cannot be empty");
    } else if (hasUnsafe) {
      addError(
        "pytest_args",
        "Pytest arguments must not contain shell operators or command escapes"
      );
    }
  }

  // Allowed relative source paths validation
  if (!config.allowed_source_paths || !Array.isArray(config.allowed_source_paths)) {
    addError("allowed_source_paths", "Allowed source paths list cannot be empty");
  } else {
    let hasNonEmptyPath = false;
    let hasPathTraversal = false;
    for (const p of config.allowed_source_paths) {
      if (typeof p !== "string") {
        hasPathTraversal = true;
        continue;
      }
      const trimmed = p.trim();
      if (trimmed) {
        hasNonEmptyPath = true;
        if (trimmed.startsWith("/") || trimmed.startsWith("\\") || trimmed.includes(":")) {
          hasPathTraversal = true;
        }
        const parts = trimmed.replace(/\\/g, "/").split("/");
        if (parts.includes("..") || parts.includes(".")) {
          hasPathTraversal = true;
        }
      }
    }
    if (!hasNonEmptyPath) {
      addError("allowed_source_paths", "Allowed source paths list cannot be empty");
    } else if (hasPathTraversal) {
      addError(
        "allowed_source_paths",
        "Allowed source paths must be relative paths within repository root and cannot contain parent directory traversal (..)"
      );
    }
  }

  // Expected failure substring validation
  const expectedFailure = (config.expected_failure || "").trim();
  if (!expectedFailure) {
    addError("expected_failure", "Expected failure substring is required");
  }

  return {
    valid: errors.length === 0,
    errors,
    field_errors: fieldErrors,
    custom_execution_supported: false,
    gate_status: "disabled",
    gate_message:
      "Custom repository execution is disabled in this safe product slice. Arbitrary remote execution, background worker enqueueing, provider calls, and task execution are strictly gated off.",
  };
}
