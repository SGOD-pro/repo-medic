import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

describe("evidence accuracy and schema regression checks", () => {
  const evidencePath = path.resolve(__dirname, "../../artifacts/live_evidence.json");
  const rawEvidence = fs.readFileSync(evidencePath, "utf-8");
  const liveEvidence = JSON.parse(rawEvidence);

  it("loads committed live evidence accurately", () => {
    assert.equal(liveEvidence.task_id, "TASK-091");
    assert.equal(liveEvidence.execution_mode, "live");
    assert.equal(liveEvidence.dependency, "sqlalchemy");
    assert.equal(liveEvidence.verified_version, "2.0.19");
  });

  it("parses actual test_summary schema and displays 1/1 tests passing, never 42/42", () => {
    const summary = liveEvidence.test_summary;
    assert.ok(summary, "test_summary must be defined in evidence");
    assert.equal(summary.passed_count, 1);
    assert.equal(summary.collected_count, 1);
    assert.equal(summary.failed_count, 0);

    // Replicate frontend verification-view parser logic
    const testsPassed = typeof summary?.passed_count === "number"
      ? summary.passed_count
      : (typeof liveEvidence.tests_passed === "number" ? liveEvidence.tests_passed : 0);
    const testsFailed = typeof summary?.failed_count === "number"
      ? summary.failed_count
      : (typeof liveEvidence.tests_failed === "number" ? liveEvidence.tests_failed : 0);
    const totalCollected = typeof summary?.collected_count === "number"
      ? summary.collected_count
      : (testsPassed + testsFailed > 0 ? testsPassed + testsFailed : 1);

    const ratioDisplay = `${testsPassed} / ${totalCollected}`;
    const headerDisplay = `Behavior preserved (${testsPassed}/${totalCollected} tests passing)`;

    assert.equal(testsPassed, 1);
    assert.equal(totalCollected, 1);
    assert.equal(ratioDisplay, "1 / 1");
    assert.notEqual(ratioDisplay, "42 / 42");
    assert.equal(headerDisplay, "Behavior preserved (1/1 tests passing)");
    assert.notEqual(headerDisplay, "Behavior preserved (42/42 tests passing)");
  });

  it("formats actual execution time from duration_seconds without 24.2s fallback", () => {
    assert.equal(typeof liveEvidence.duration_seconds, "number");
    assert.ok(liveEvidence.duration_seconds > 0);

    const formattedDuration = typeof liveEvidence.duration_seconds === "number"
      ? `${liveEvidence.duration_seconds.toFixed(1)}s`
      : typeof liveEvidence.execution_time === "string"
      ? liveEvidence.execution_time
      : "0.0s";

    assert.equal(formattedDuration, "10.3s");
    assert.notEqual(formattedDuration, "24.2s");
  });

  it("does not fall back to fabricated 0.04 USD cost", () => {
    const activeRunUsage = undefined;
    const costUsd = activeRunUsage ?? (typeof liveEvidence.cost_usd === "number" ? liveEvidence.cost_usd : 0.0);
    assert.equal(costUsd, 0.0);
    assert.notEqual(costUsd, 0.04);
  });

  it("only displays verification claims supported by actual evidence", () => {
    assert.equal(liveEvidence.signature, undefined);
    assert.equal(liveEvidence.checks.tests_passed, true);

    // If signature is missing, no ed25519 signature is claimed
    const signatureBadge = liveEvidence.signature
      ? `Signature: ${String(liveEvidence.signature)}`
      : liveEvidence.checks?.tests_passed
      ? "Verification Checks Passed"
      : null;

    assert.equal(signatureBadge, "Verification Checks Passed");
    assert.notEqual(signatureBadge, "Patch Sig: ed25519 verified");
  });

  it("resolves execution mode accurately from live evidence and run metadata", () => {
    const mode = liveEvidence.execution_mode;
    assert.equal(mode, "live");

    let modeLabel = "OFFLINE MODE (TURSO)";
    if (mode === "live") modeLabel = "LIVE SANDBOX (NEBIUS)";
    else if (mode === "replay") modeLabel = "REPLAY MODE";

    assert.equal(modeLabel, "LIVE SANDBOX (NEBIUS)");
  });
});
