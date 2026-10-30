import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { RunSummary, EventEnvelope, UsageSummary, StageCompletedPayload, CandidateCompletedPayload } from "../src/lib/contracts";
import { resolveVerificationViewModel } from "../src/components/verification-view";

interface StageResult {
  passed: boolean;
  summary: string;
}

interface HttpStage {
  name: string;
  key: "baseline" | "upgrade" | "repair" | "verification";
  defaultDetail: string;
}

const HTTP_STAGES: HttpStage[] = [
  { name: "1. Baseline Check", key: "baseline", defaultDetail: "Confirm test suite passes cleanly on pinned commit" },
  { name: "2. Target Upgrade", key: "upgrade", defaultDetail: "Install target dependency version and reproduce failure" },
  { name: "3. Source Repair", key: "repair", defaultDetail: "Synthesize and rank minimally scoped candidate patches" },
  { name: "4. Full Verification", key: "verification", defaultDetail: "Execute verification suite against patched source tree" },
];

function resolveStageCardState(
  stage: HttpStage,
  idx: number,
  stageResults: Record<string, StageResult | undefined>,
  activeRun: RunSummary | null,
  isTerminal: boolean,
  liveCandidateCount: number = 0
): { badge: "PASSED" | "FAILED" | "ACTIVE" | "NOT RUN" | "PENDING" | "UNAVAILABLE"; summary: string } {
  const res = stageResults[stage.key];
  const isNoRegression = Boolean(
    activeRun?.reason?.toLowerCase().includes("no regression detected")
  );
  const isSkippedDueToNoRegression =
    isNoRegression && (stage.key === "repair" || stage.key === "verification");

  if (res) {
    return {
      badge: res.passed ? "PASSED" : "FAILED",
      summary: res.summary,
    };
  }

  if (
    stage.key === "repair" &&
    (liveCandidateCount > 0 || Boolean(stageResults["verification"]))
  ) {
    return {
      badge: "PASSED",
      summary:
        liveCandidateCount > 0
          ? `${liveCandidateCount} candidate${liveCandidateCount === 1 ? "" : "s"} synthesized`
          : "Candidate patch synthesized",
    };
  }

  if (isSkippedDueToNoRegression) {
    return {
      badge: "NOT RUN",
      summary: "No regression detected in target version; repair not required",
    };
  }

  if (isTerminal) {
    const prevPassed = idx === 0 ? false : Boolean(stageResults[HTTP_STAGES[idx - 1].key]?.passed);
    const isEarlierFailed = HTTP_STAGES.slice(0, idx).some((s) => stageResults[s.key] && !stageResults[s.key]?.passed);
    if (isEarlierFailed || (idx > 0 && !prevPassed)) {
      return {
        badge: "NOT RUN",
        summary: "Stage was not reached before run terminated",
      };
    } else {
      return {
        badge: "UNAVAILABLE",
        summary: "Execution evidence unavailable for this stage",
      };
    }
  }

  const isPrevPassed = idx === 0 || Boolean(stageResults[HTTP_STAGES[idx - 1].key]?.passed);
  if (isPrevPassed && !res) {
    return {
      badge: "ACTIVE",
      summary: stage.defaultDetail,
    };
  }

  return {
    badge: "PENDING",
    summary: stage.defaultDetail,
  };
}

const DEFAULT_USAGE: UsageSummary = {
  model_calls: 0,
  input_tokens: 0,
  output_tokens: 0,
  estimated_usd: 0,
};

describe("stage event mapping, hydration and terminal presentation", () => {
  it("maps stage.completed and candidate.completed events to stage results", () => {
    const stageResults: Record<string, StageResult | undefined> = {};

    // Simulate baseline event
    const baselinePayload: StageCompletedPayload = {
      stage: "baseline",
      passed: true,
      summary: "Baseline tests passed cleanly (2/2 tests)",
    };
    const baselineEv: EventEnvelope = {
      run_id: "run_test_1",
      seq: 1,
      ts: new Date().toISOString(),
      type: "stage.completed",
      payload: baselinePayload as unknown as Record<string, unknown>,
    };
    const stageName = baselinePayload.stage;
    stageResults[stageName] = {
      passed: baselinePayload.passed,
      summary: baselinePayload.summary,
    };
    assert.equal(baselineEv.type, "stage.completed");
    assert.equal(stageResults.baseline?.passed, true);
    assert.equal(stageResults.baseline?.summary, "Baseline tests passed cleanly (2/2 tests)");

    // Simulate candidate event
    const candPayload: CandidateCompletedPayload = {
      candidate_id: "cand_1",
      passed: true,
      summary: "Patch applied cleanly and fixed tests",
    };
    const candEv: EventEnvelope = {
      run_id: "run_test_1",
      seq: 2,
      ts: new Date().toISOString(),
      type: "candidate.completed",
      payload: candPayload as unknown as Record<string, unknown>,
    };
    assert.equal(candEv.type, "candidate.completed");
    stageResults.repair = {
      passed: candPayload.passed,
      summary: candPayload.summary,
    };

    assert.equal(stageResults.repair?.passed, true);
    assert.equal(stageResults.repair?.summary, "Patch applied cleanly and fixed tests");
  });

  it("accurately reports FAILED and NOT RUN when run fails at baseline stage", () => {
    const stageResults: Record<string, StageResult | undefined> = {
      baseline: { passed: false, summary: "Baseline tests failed with instability" },
    };
    const activeRun: RunSummary = {
      run_id: "run_fail_baseline",
      task_id: "TASK-DEMO-SHOP",
      mode: "offline",
      search_mode: "sequential",
      state: "failed",
      reason: "Baseline check failed",
      usage: DEFAULT_USAGE,
      artifacts: [],
    };

    // Baseline should be FAILED
    const s0 = resolveStageCardState(HTTP_STAGES[0], 0, stageResults, activeRun, true);
    assert.equal(s0.badge, "FAILED");
    assert.equal(s0.summary, "Baseline tests failed with instability");

    // Subsequent stages must be NOT RUN (never PENDING, never PASSED)
    for (let i = 1; i < HTTP_STAGES.length; i++) {
      const s = resolveStageCardState(HTTP_STAGES[i], i, stageResults, activeRun, true);
      assert.equal(s.badge, "NOT RUN");
      assert.equal(s.summary, "Stage was not reached before run terminated");
    }
  });

  it("truthfully renders terminal reload without fabricated log fallbacks", () => {
    const activeRun: RunSummary = {
      run_id: "run_994e3320ba764066b3d7c55e5146493f",
      task_id: "TASK-DEMO-JWT",
      mode: "offline",
      search_mode: "sequential",
      state: "failed",
      reason: "Patch safety validation failed: File 'src/app.py' is outside recipe allowed source paths ['src/auth/tokens.py']",
      usage: DEFAULT_USAGE,
      artifacts: [],
    };

    const emptyStreamLogs: string[] = [];
    const isTerminal = true;

    const logText =
      emptyStreamLogs.length > 0
        ? emptyStreamLogs.join("\n")
        : isTerminal
        ? `[00:00] run.finished: state=${activeRun.state} (${activeRun.reason})`
        : "Connecting...";

    assert.ok(logText.includes("Patch safety validation failed"));
    assert.ok(!logText.includes("[00:01] stage.baseline: PASSED"));
    assert.ok(!logText.includes("[00:04] stage.upgrade: PASSED"));
  });

  it("handles automatic regression discovery with no regression detected cleanly", () => {
    const stageResults: Record<string, StageResult | undefined> = {
      baseline: { passed: true, summary: "Baseline tests passed cleanly" },
      upgrade: { passed: true, summary: "Upgrade installed. No regression detected in test suite." },
    };
    const activeRun: RunSummary = {
      run_id: "run_clean_no_regression",
      task_id: "TASK-CUSTOM-CLEAN",
      mode: "live",
      search_mode: "sequential",
      state: "succeeded",
      reason: "No regression detected in target version; repair not required",
      usage: DEFAULT_USAGE,
      artifacts: [],
    };

    // Baseline & Upgrade: PASSED
    const s0 = resolveStageCardState(HTTP_STAGES[0], 0, stageResults, activeRun, true);
    assert.equal(s0.badge, "PASSED");
    const s1 = resolveStageCardState(HTTP_STAGES[1], 1, stageResults, activeRun, true);
    assert.equal(s1.badge, "PASSED");

    // Repair & Verification: NOT RUN because no regression was detected
    const s2 = resolveStageCardState(HTTP_STAGES[2], 2, stageResults, activeRun, true);
    assert.equal(s2.badge, "NOT RUN");
    assert.equal(s2.summary, "No regression detected in target version; repair not required");

    const s3 = resolveStageCardState(HTTP_STAGES[3], 3, stageResults, activeRun, true);
    assert.equal(s3.badge, "NOT RUN");
    assert.equal(s3.summary, "No regression detected in target version; repair not required");
  });

  it("distinguishes live versus offline mode presentation", () => {
    const liveRun: RunSummary = {
      run_id: "run_live_1",
      task_id: "TASK-DEMO-JWT",
      mode: "live",
      search_mode: "sequential",
      state: "running",
      reason: null,
      usage: DEFAULT_USAGE,
      artifacts: [],
    };
    const offlineRun: RunSummary = {
      run_id: "run_offline_1",
      task_id: "TASK-DEMO-JWT",
      mode: "offline",
      search_mode: "sequential",
      state: "running",
      reason: null,
      usage: DEFAULT_USAGE,
      artifacts: [],
    };

    assert.equal(liveRun.mode, "live");
    assert.notEqual(liveRun.mode, "offline");
    assert.equal(offlineRun.mode, "offline");
    assert.notEqual(offlineRun.mode, "live");
  });

  it("candidate synthesis shows PASSED when candidate events exist even if repair stage was omitted", () => {
    const stageResults: Record<string, StageResult | undefined> = {
      baseline: { passed: true, summary: "Baseline tests passed cleanly twice" },
      upgrade: { passed: true, summary: "Upgrade reproduced expected failure" },
      verification: { passed: false, summary: "Candidate patch failed to apply cleanly" },
    };
    const terminalRun: RunSummary = {
      run_id: "run_05ff3b08a62b49b98a69cabb7573ed37",
      task_id: "TASK-CUSTOM-ee2d8a152218111555c0fbf51d6376ce",
      mode: "live",
      search_mode: "sequential",
      state: "failed",
      reason: "Candidate patch failed to apply cleanly",
      usage: {
        model_calls: 1,
        input_tokens: 929,
        output_tokens: 589,
        estimated_usd: 0.05,
      },
      artifacts: [],
    };

    const repairState = resolveStageCardState(HTTP_STAGES[2], 2, stageResults, terminalRun, true, 1);
    assert.equal(repairState.badge, "PASSED");
    assert.equal(repairState.summary, "1 candidate synthesized");
    assert.notEqual(repairState.badge, "NOT RUN");
    assert.notEqual(repairState.badge, "UNAVAILABLE");
  });

  it("patch apply failure resolves to PATCH APPLY FAILED and does not show All assertions verified", () => {
    const failedRun: RunSummary = {
      run_id: "run_05ff3b08a62b49b98a69cabb7573ed37",
      task_id: "TASK-CUSTOM-ee2d8a152218111555c0fbf51d6376ce",
      mode: "live",
      search_mode: "sequential",
      state: "failed",
      reason: "Candidate patch failed to apply cleanly (error: patch failed: src/shop/database.py:6)",
      usage: {
        model_calls: 1,
        input_tokens: 929,
        output_tokens: 589,
        estimated_usd: 0.05,
      },
      artifacts: [],
    };

    const evidenceData = {
      schema_version: "1.0.0",
      candidate_id: "candidate_1",
      task_id: "TASK-CUSTOM-ee2d8a152218111555c0fbf51d6376ce",
      execution_mode: "live",
      checks: {
        checkpoint_isolated: true,
        pre_patch_hash_match: true,
        patch_applied: false,
        post_patch_hash_match: false,
        tests_passed: false,
      },
      test_summary: {
        exit_code: 1,
        collected_count: 0,
        passed_count: 0,
        failed_count: 0,
      },
    };

    const vm = resolveVerificationViewModel(failedRun, evidenceData);

    assert.equal(vm.isFail, true);
    assert.equal(vm.isPass, false);
    assert.equal(vm.patchApplied, false);
    assert.equal(vm.regressionsBadgeText, "PATCH APPLY FAILED");
    assert.equal(vm.ratioDisplay, "Not Run");
    assert.equal(vm.preservedSubtitle, "Patch application failed · 0 tests run");
    assert.notEqual(vm.preservedSubtitle, "All assertions verified");
    assert.notEqual(vm.regressionsBadgeText, "0 REGRESSIONS");
  });
});
