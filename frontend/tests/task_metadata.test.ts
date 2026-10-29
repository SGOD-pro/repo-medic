import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { TaskSummary } from "../src/lib/contracts";
import { MockTransport } from "../src/lib/api";

// Pure mapping test matching tasks-view.tsx mapSummaryToTaskItem logic
function mapSummaryToTaskItem(s: TaskSummary) {
  const repoName = s.repository_url
    ? s.repository_url.replace(/^https?:\/\/github\.com\//, "").replace(/\.git$/, "")
    : "Unavailable";
  const expectedFailure =
    typeof s.expected_failure === "string" && s.expected_failure.trim()
      ? s.expected_failure.trim()
      : "Unavailable";
  const allowlist =
    Array.isArray(s.allowed_source_paths) && s.allowed_source_paths.length > 0
      ? s.allowed_source_paths.join(", ")
      : "Unavailable";
  const testsCount =
    typeof s.tests_count === "number" && !isNaN(s.tests_count)
      ? s.tests_count
      : null;
  const baselineTime =
    typeof s.baseline_time === "string" && s.baseline_time.trim()
      ? s.baseline_time.trim()
      : "Unavailable";

  return {
    id: s.task_id,
    repo: repoName,
    title: s.title,
    commitSha: s.commit_sha || "Unavailable",
    dependency: s.dependency,
    targetVersion: s.to_version,
    testsCount,
    expectedFailure,
    baselineTime,
    allowlist,
  };
}

describe("demo tasks metadata: mapping & API serialization", () => {
  test("maps full declared metadata cleanly without modification", () => {
    const summary: TaskSummary = {
      task_id: "TASK-DEMO-JWT",
      title: "Upgrade pyjwt 1.7.1 to 2.8.0 in repomedic-demo-auth",
      repository_url: "https://github.com/SGOD-pro/repo-medic.git",
      commit_sha: "8b635e7ff84556962f6ec4fee43523778461c938",
      dependency: "pyjwt",
      from_version: "1.7.1",
      to_version: "2.8.0",
      expected_failure: "AttributeError: 'str' object has no attribute 'decode'",
      test_command: ["pytest", "tests/"],
      allowed_source_paths: ["src/auth/tokens.py"],
      tests_count: 3,
      baseline_time: "0.15s (Python 3.12)",
    };

    const item = mapSummaryToTaskItem(summary);
    assert.equal(item.id, "TASK-DEMO-JWT");
    assert.equal(item.expectedFailure, "AttributeError: 'str' object has no attribute 'decode'");
    assert.equal(item.testsCount, 3);
    assert.equal(item.baselineTime, "0.15s (Python 3.12)");
    assert.equal(item.allowlist, "src/auth/tokens.py");
  });

  test("handles missing metadata by showing Unavailable and null count", () => {
    const summary: TaskSummary = {
      task_id: "TASK-CUSTOM-EMPTY",
      title: "Custom Empty Task",
      repository_url: "https://github.com/SGOD-pro/repo-medic.git",
      commit_sha: "abcdef1234567890abcdef1234567890abcdef12",
      dependency: "empty_pkg",
      from_version: "1.0.0",
      to_version: "2.0.0",
      expected_failure: null,
      test_command: null,
      allowed_source_paths: null,
      tests_count: null,
      baseline_time: null,
    };

    const item = mapSummaryToTaskItem(summary);
    assert.equal(item.expectedFailure, "Unavailable");
    assert.equal(item.testsCount, null);
    assert.equal(item.baselineTime, "Unavailable");
    assert.equal(item.allowlist, "Unavailable");
  });

  test("handles whitespace, empty arrays, and NaN gracefully", () => {
    const summary: TaskSummary = {
      task_id: "TASK-MALFORMED",
      title: "Malformed Task",
      repository_url: "",
      commit_sha: "",
      dependency: "pkg",
      from_version: "1.0",
      to_version: "2.0",
      expected_failure: "   ",
      test_command: [],
      allowed_source_paths: [],
      tests_count: NaN,
      baseline_time: "  ",
    };

    const item = mapSummaryToTaskItem(summary);
    assert.equal(item.repo, "Unavailable");
    assert.equal(item.commitSha, "Unavailable");
    assert.equal(item.expectedFailure, "Unavailable");
    assert.equal(item.testsCount, null);
    assert.equal(item.baselineTime, "Unavailable");
    assert.equal(item.allowlist, "Unavailable");
  });

  test("MockTransport returns declared task metadata for all demo tasks", async () => {
    const client = new MockTransport();
    const tasks = await client.getTasks("supported_demo");
    assert.ok(tasks.length >= 4, "Expected at least 4 demo tasks in MockTransport");

    const demoMap = new Map(tasks.map((t) => [t.task_id, t]));

    const shop = demoMap.get("TASK-DEMO-SHOP");
    assert.ok(shop, "TASK-DEMO-SHOP must exist");
    assert.equal(shop.expected_failure, "AttributeError: 'Engine' object has no attribute 'execute'");
    assert.equal(shop.tests_count, 1);
    assert.equal(shop.baseline_time, "0.16s (Python 3.12)");

    const jwt = demoMap.get("TASK-DEMO-JWT");
    assert.ok(jwt, "TASK-DEMO-JWT must exist");
    assert.equal(jwt.expected_failure, "AttributeError: 'str' object has no attribute 'decode'");
    assert.equal(jwt.tests_count, 3);
    assert.equal(jwt.baseline_time, "0.15s (Python 3.12)");
  });
});
