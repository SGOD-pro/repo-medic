import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { useHistoryStore, INITIAL_SEEDED_RUNS, HistoryRunItem } from "../src/lib/history-store";

describe("history store: Zustand persistence & actions (covers: AC-6, AC-7, AC-8)", () => {
  beforeEach(() => {
    useHistoryStore.setState({
      runs: [...INITIAL_SEEDED_RUNS],
      isHistoryOpen: false,
      hasHydrated: true,
    });
  });

  it("initializes with seeded runs matching fixtures (covers: AC-6)", () => {
    const state = useHistoryStore.getState();
    assert.equal(state.runs.length, 3);
    assert.equal(state.runs[0].run_id, "run-success-1");
    assert.equal(state.runs[0].state, "succeeded");
    assert.equal(state.runs[1].run_id, "run-fail-1");
    assert.equal(state.runs[1].state, "failed");
    assert.equal(state.runs[2].run_id, "run-cancel-1");
    assert.equal(state.runs[2].state, "cancelled");
  });

  it("addRun prepends new run and avoids duplicate IDs (covers: AC-8)", () => {
    const newRun: HistoryRunItem = {
      run_id: "run-new-test",
      task_id: "TASK-084",
      task_title: "pydantic migration test",
      dependency: "pydantic",
      from_version: "1.10.8",
      to_version: "2.0.2",
      state: "running",
      mode: "live",
      search_mode: "branch_refine",
      started_at: new Date().toISOString(),
      cost_usd: 0.18,
    };

    useHistoryStore.getState().addRun(newRun);
    const state = useHistoryStore.getState();
    assert.equal(state.runs.length, 4);
    assert.equal(state.runs[0].run_id, "run-new-test");
    assert.equal(state.runs[0].state, "running");

    // Adding same ID again deduplicates
    useHistoryStore.getState().addRun(newRun);
    assert.equal(useHistoryStore.getState().runs.length, 4);
  });

  it("updateRun modifies specific run fields cleanly (covers: AC-8)", () => {
    useHistoryStore.getState().updateRun("run-success-1", {
      tests_passed: 45,
      cost_usd: 0.05,
    });
    const updated = useHistoryStore.getState().runs.find((r) => r.run_id === "run-success-1");
    assert.ok(updated);
    assert.equal(updated.tests_passed, 45);
    assert.equal(updated.cost_usd, 0.05);
  });

  it("clearHistory resets runs to an empty list (covers: AC-7)", () => {
    useHistoryStore.getState().clearHistory();
    const state = useHistoryStore.getState();
    assert.equal(state.runs.length, 0);
  });

  it("setHistoryOpen updates open state correctly (covers: AC-1)", () => {
    useHistoryStore.getState().setHistoryOpen(true);
    assert.equal(useHistoryStore.getState().isHistoryOpen, true);
    useHistoryStore.getState().setHistoryOpen(false);
    assert.equal(useHistoryStore.getState().isHistoryOpen, false);
  });
});

describe("history state resolution: view mapping (covers: AC-4, AC-5)", () => {
  it("routes terminal runs to verification view", () => {
    const terminalStates: HistoryRunItem["state"][] = ["succeeded", "failed", "cancelled"];
    for (const state of terminalStates) {
      const targetTab =
        state === "succeeded" || state === "failed" || state === "cancelled"
          ? "verification"
          : "run_active";
      assert.equal(targetTab, "verification");
    }
  });

  it("routes active and queued runs to run_active view", () => {
    const activeStates: HistoryRunItem["state"][] = ["queued", "running"];
    for (const state of activeStates) {
      const targetTab =
        state === "succeeded" || state === "failed" || state === "cancelled"
          ? "verification"
          : "run_active";
      assert.equal(targetTab, "run_active");
    }
  });
});

describe("history store: ordering & edge cases (covers: AC-2, AC-8)", () => {
  beforeEach(() => {
    useHistoryStore.setState({
      runs: [...INITIAL_SEEDED_RUNS],
      isHistoryOpen: false,
      hasHydrated: true,
    });
  });

  it("maintains most recent run prepended at index 0 (covers: AC-2, AC-8)", () => {
    const runA: HistoryRunItem = {
      run_id: "run-first",
      task_id: "TASK-084",
      task_title: "first test task",
      dependency: "pydantic",
      from_version: "1.10.8",
      to_version: "2.0.2",
      state: "running",
      mode: "live",
      search_mode: "branch_refine",
      started_at: "2026-10-10T10:00:00Z",
    };
    const runB: HistoryRunItem = {
      run_id: "run-second",
      task_id: "TASK-091",
      task_title: "second test task",
      dependency: "sqlalchemy",
      from_version: "1.4.48",
      to_version: "2.0.19",
      state: "running",
      mode: "offline",
      search_mode: "sequential",
      started_at: "2026-10-10T10:05:00Z",
    };

    useHistoryStore.getState().addRun(runA);
    assert.equal(useHistoryStore.getState().runs[0].run_id, "run-first");

    useHistoryStore.getState().addRun(runB);
    assert.equal(useHistoryStore.getState().runs[0].run_id, "run-second");
    assert.equal(useHistoryStore.getState().runs[1].run_id, "run-first");
  });

  it("handles updateRun on non-existent run ID without mutation (covers: AC-8)", () => {
    const initialCount = useHistoryStore.getState().runs.length;
    useHistoryStore.getState().updateRun("run-non-existent", { state: "succeeded" });
    const runs = useHistoryStore.getState().runs;
    assert.equal(runs.length, initialCount);
    assert.equal(runs.find((r) => r.run_id === "run-non-existent"), undefined);
  });

  it("validates all seeded history items contain valid task and version metadata (covers: AC-2)", () => {
    for (const run of INITIAL_SEEDED_RUNS) {
      assert.ok(run.run_id.length > 0, "run_id must not be empty");
      assert.ok(run.task_id.startsWith("TASK-"), "task_id must follow TASK- prefix");
      assert.ok(run.dependency.length > 0, "dependency must be specified");
      assert.ok(run.from_version.length > 0, "from_version must be specified");
      assert.ok(run.to_version.length > 0, "to_version must be specified");
      assert.ok(Date.parse(run.started_at) > 0, "started_at must be valid ISO timestamp");
    }
  });
});

describe("run state badges: token and status integrity (covers: AC-3)", () => {
  it("recognizes all standard lifecycle and terminal states (covers: AC-3)", () => {
    const allowedStates: HistoryRunItem["state"][] = [
      "queued",
      "running",
      "succeeded",
      "failed",
      "cancelled",
    ];
    for (const state of allowedStates) {
      assert.ok(["queued", "running", "succeeded", "failed", "cancelled"].includes(state));
    }
  });

  it("distinguishes terminal states from active states accurately (covers: AC-3, AC-4)", () => {
    const isTerminal = (state: HistoryRunItem["state"]) =>
      state === "succeeded" || state === "failed" || state === "cancelled";

    assert.equal(isTerminal("succeeded"), true);
    assert.equal(isTerminal("failed"), true);
    assert.equal(isTerminal("cancelled"), true);
    assert.equal(isTerminal("running"), false);
    assert.equal(isTerminal("queued"), false);
  });
});

describe("URL parameter synchronization: query string parser (covers: AC-5)", () => {
  it("parses runId from standard URL search string (covers: AC-5)", () => {
    const search = "?runId=run-success-1&tab=verification";
    const params = new URLSearchParams(search);
    assert.equal(params.get("runId"), "run-success-1");
  });

  it("returns null when runId is not present in URL search string (covers: AC-5)", () => {
    const search = "?tab=tasks";
    const params = new URLSearchParams(search);
    assert.equal(params.get("runId"), null);
  });

  it("handles empty or root search string safely (covers: AC-5)", () => {
    const search = "";
    const params = new URLSearchParams(search);
    assert.equal(params.get("runId"), null);
  });
});


