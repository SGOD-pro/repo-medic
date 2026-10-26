import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { resolveVerificationViewModel } from "../src/components/verification-view";
import { RunSummary } from "../src/lib/contracts";

describe("evidence accuracy and real component behavior", () => {
  const evidencePath = path.resolve(__dirname, "../../artifacts/live_evidence.json");
  const rawEvidence = fs.readFileSync(evidencePath, "utf-8");
  const liveEvidence = JSON.parse(rawEvidence);

  const mockLiveRun: RunSummary = {
    run_id: "run_466bde7e846a494b8414e6f973df97d1",
    task_id: "TASK-091",
    mode: "live",
    search_mode: "sequential",
    state: "succeeded",
    reason: "Candidate verified cleanly and resolved upgrade regression",
    usage: {
      model_calls: 1,
      input_tokens: 613,
      output_tokens: 1803,
      estimated_usd: 0.35,
    },
    artifacts: [
      { artifact_id: "art_60fd3df2e637", kind: "patch", filename: "patch.diff" },
      { artifact_id: "art_6b0049716a3f", kind: "log", filename: "verify.log" },
      { artifact_id: "art_5def40de8347", kind: "evidence", filename: "evidence.json" },
    ],
  };

  it("extracts real model from committed live evidence without fabricated 42/42 fallback", () => {
    const vm = resolveVerificationViewModel(mockLiveRun, liveEvidence);

    assert.equal(vm.testsPassed, 1);
    assert.equal(vm.totalCollected, 1);
    assert.equal(vm.testsFailed, 0);
    assert.equal(vm.ratioDisplay, "1 / 1");
    assert.notEqual(vm.ratioDisplay, "42 / 42");
    assert.equal(vm.headerTitle, "Behavior preserved (1/1 tests passing)");
    assert.notEqual(vm.headerTitle, "Behavior preserved (42/42 tests passing)");
    assert.equal(vm.regressionsBadgeText, "0 REGRESSIONS");
  });

  it("formats verification time from duration_seconds without 24.2s fallback", () => {
    const vm = resolveVerificationViewModel(mockLiveRun, liveEvidence);

    assert.equal(vm.verificationTimeText, "10.3s");
    assert.notEqual(vm.verificationTimeText, "24.2s");
    assert.notEqual(vm.verificationTimeText, "0.0s");
  });

  it("formats actual usage cost from run data without 0.04 USD fallback", () => {
    const vm = resolveVerificationViewModel(mockLiveRun, liveEvidence);

    assert.equal(vm.costText, "$0.35");
    assert.notEqual(vm.costText, "$0.04");
  });

  it("binds AST verified badge and proof detail to actual verified checks", () => {
    const vm = resolveVerificationViewModel(mockLiveRun, liveEvidence);

    assert.equal(vm.astBadgeVisible, true);
    assert.equal(vm.testFilesUnchangedVisible, true);
    assert.equal(vm.hashCheckBadgeText, "Test files unchanged");
    assert.equal(vm.astProofSupported, true);
    assert.equal(vm.astProofText, "AST Proof: 0 test files modified · exact dependency verified");
    assert.equal(vm.signatureBadgeText, "Verification Checks Passed");
    assert.notEqual(vm.signatureBadgeText, "Patch Sig: ed25519 verified");
  });

  it("renders Unavailable for all missing evidence metrics instead of fabricating numbers", () => {
    const emptyEvidenceRun: RunSummary = {
      run_id: "run_empty_test",
      task_id: "TASK-091",
      mode: "live",
      search_mode: "sequential",
      state: "succeeded",
      reason: null,
      usage: undefined as unknown as RunSummary["usage"],
      artifacts: [],
    };

    const vm = resolveVerificationViewModel(emptyEvidenceRun, null);

    // Tests ratio must show Unavailable rather than 42/42, 1/1, or 0/0
    assert.equal(vm.ratioDisplay, "Unavailable");
    assert.equal(vm.testsPassed, null);
    assert.equal(vm.totalCollected, null);

    // Header must describe generic completed repair without inventing test numbers
    assert.equal(vm.headerTitle, "Verified Source Repair Completed");

    // Verification time must show Unavailable rather than 0.0s or 24.2s
    assert.equal(vm.verificationTimeText, "Unavailable");

    // Cost must show Unavailable rather than 0.04
    assert.equal(vm.costText, "Unavailable");

    // Characterization tests must show Unavailable rather than 0
    assert.equal(vm.characterizationTestsText, "Unavailable");

    // Proof detail must show Unavailable
    assert.equal(vm.astProofSupported, false);
    assert.equal(vm.astProofText, "Evidence proof unavailable");

    // Unconditional AST badge must NOT be visible
    assert.equal(vm.astBadgeVisible, false);
    assert.equal(vm.regressionsBadgeText, null);
    assert.equal(vm.signatureBadgeText, null);
  });

  it("does not display AST proof badge when checks indicate post patch hash mismatch", () => {
    const tamperedEvidence = {
      ...liveEvidence,
      checks: {
        ...liveEvidence.checks,
        post_patch_hash_match: false,
      },
    };

    const vm = resolveVerificationViewModel(mockLiveRun, tamperedEvidence);

    assert.equal(vm.astBadgeVisible, false);
    assert.equal(vm.astProofSupported, false);
    assert.equal(vm.astProofText, "Verification checks evaluated without AST proof");
  });
});
