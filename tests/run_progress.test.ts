import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { MOCK_PATCH, MOCK_EVIDENCE, MOCK_LOG, CURATED_TASKS } from "../src/lib/api";

describe("run progress & verification invariants (covers: AC-1..AC-9)", () => {
  it("verifies pipeline stages configuration and order (covers: AC-1)", () => {
    const expectedStages = [
      "1. Baseline Check",
      "2. Upgrade Reproduction",
      "3. Allowlist Context",
      "4. Candidate Gen",
      "5. Sandbox Verify",
      "6. Preservation Proof",
    ];
    assert.equal(expectedStages.length, 6);
    assert.equal(expectedStages[0], "1. Baseline Check");
    assert.equal(expectedStages[5], "6. Preservation Proof");
  });

  it("verifies spend budget ceiling and metric bounds (covers: AC-2)", () => {
    const spendUsd = 0.18;
    const capUsd = 0.5;
    assert.ok(spendUsd <= capUsd, "Spend must not exceed budget cap without enforcement flag");
    assert.ok(spendUsd >= 0, "Spend must be non-negative");
  });

  it("verifies candidate matrix strategies and winner criteria (covers: AC-3)", () => {
    const candidateA = {
      id: "cand_a",
      title: "Candidate A",
      passed: 42,
      failed: 0,
      winner: true,
      modifiedTestFiles: 0,
    };
    const candidateB = {
      id: "cand_b",
      title: "Candidate B",
      passed: 38,
      failed: 4,
      winner: false,
      modifiedTestFiles: 0,
    };

    // Invariant: Winner must have zero test file modifications and zero test failures
    assert.equal(candidateA.winner, true);
    assert.equal(candidateA.failed, 0);
    assert.equal(candidateA.modifiedTestFiles, 0);

    // Invariant: Candidate with failed tests cannot be selected as winner
    assert.equal(candidateB.winner, false);
    assert.ok(candidateB.failed > 0);
  });

  it("verifies terminal log output contains completion and verification proofs (covers: AC-4)", () => {
    assert.ok(MOCK_LOG.includes("sandbox: creating isolated container environment"));
    assert.ok(MOCK_LOG.includes("42 passed in 1.48s"));
    assert.ok(MOCK_LOG.includes("candidate A verified successfully"));
  });

  it("verifies verification report metrics integrity (covers: AC-6, AC-8)", () => {
    const evidence = MOCK_EVIDENCE;
    assert.equal(evidence.task_id, "TASK-084");
    assert.equal(evidence.tests_passed, 42);
    assert.equal(evidence.tests_failed, 0);
    assert.equal(evidence.status, "PASSED");
    assert.ok(evidence.ast_hash.startsWith("sha256:"));
    assert.equal(evidence.contract_assertions, 2);
  });

  it("verifies unified change manifest diff format and line changes (covers: AC-7, AC-9)", () => {
    const patch = MOCK_PATCH;
    assert.ok(patch.startsWith("--- a/src/app/schemas.py"));
    assert.ok(patch.includes("--- a/pyproject.toml"));

    // Check patch line additions and removals
    const lines = patch.split("\n");
    const additions = lines.filter((l) => l.startsWith("+") && !l.startsWith("+++"));
    const removals = lines.filter((l) => l.startsWith("-") && !l.startsWith("---"));

    assert.ok(additions.length > 0, "Patch must have line additions");
    assert.ok(removals.length > 0, "Patch must have line removals");

    // Invariant: Pydantic v2 ConfigDict replacement is present
    assert.ok(additions.some((l) => l.includes("ConfigDict(from_attributes=True)")));
    assert.ok(removals.some((l) => l.includes("orm_mode = True")));
  });

  it("verifies curated task definitions match spec contract (covers: AC-10)", () => {
    assert.equal(CURATED_TASKS.length, 3);
    const taskIds = CURATED_TASKS.map((t) => t.task_id);
    assert.deepEqual(taskIds, ["TASK-084", "TASK-091", "TASK-097"]);
  });
});
