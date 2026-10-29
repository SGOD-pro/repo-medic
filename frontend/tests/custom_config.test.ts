import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { validateCustomRepositoryConfig } from "../src/lib/validation";
import { MockTransport } from "../src/lib/api";
import { CustomRepositoryConfig } from "../src/lib/contracts";

const VALID_CONFIG: CustomRepositoryConfig = {
  repository_url: "https://github.com/SGOD-pro/repo-medic.git",
  commit_sha: "8c400721558392a23b3af71766f673da02f80040",
  dependency: "sqlalchemy",
  from_version: "1.4.48",
  to_version: "2.0.19",
  pytest_args: ["tests/"],
  allowed_source_paths: ["src/shop/"],
  expected_failure: "AttributeError: 'Engine' object has no attribute 'execute'",
};

describe("custom repository configuration: validation & safety gate (Spec 0009)", () => {
  it("validates a conforming repository configuration cleanly", () => {
    const result = validateCustomRepositoryConfig(VALID_CONFIG);
    assert.equal(result.valid, true);
    assert.equal(result.errors.length, 0);
    assert.equal(result.custom_execution_supported, false);
    assert.equal(result.gate_status, "disabled");
    assert.ok(result.gate_message.includes("Custom repository execution is disabled"));
  });

  it("rejects non-GitHub or non-HTTPS repository URLs", () => {
    const result1 = validateCustomRepositoryConfig({
      ...VALID_CONFIG,
      repository_url: "http://github.com/owner/repo",
    });
    assert.equal(result1.valid, false);
    assert.ok(result1.field_errors.repository_url?.length > 0);

    const result2 = validateCustomRepositoryConfig({
      ...VALID_CONFIG,
      repository_url: "https://gitlab.com/owner/repo",
    });
    assert.equal(result2.valid, false);
    assert.ok(result2.field_errors.repository_url?.length > 0);
  });

  it("rejects non-40-character or non-hexadecimal commit SHAs", () => {
    const result = validateCustomRepositoryConfig({
      ...VALID_CONFIG,
      commit_sha: "8c40072", // short SHA
    });
    assert.equal(result.valid, false);
    assert.ok(result.field_errors.commit_sha?.some((e) => e.includes("40 character")));
  });

  it("rejects identical baseline and target dependency versions", () => {
    const result = validateCustomRepositoryConfig({
      ...VALID_CONFIG,
      from_version: "2.0.0",
      to_version: "2.0.0",
    });
    assert.equal(result.valid, false);
    assert.ok(result.field_errors.to_version?.some((e) => e.includes("differ")));
  });

  it("rejects shell metacharacters and dangerous commands in pytest arguments", () => {
    const result = validateCustomRepositoryConfig({
      ...VALID_CONFIG,
      pytest_args: ["tests/", "; rm -rf /"],
    });
    assert.equal(result.valid, false);
    assert.ok(result.field_errors.pytest_args?.some((e) => e.includes("shell operators")));
  });

  it("rejects directory traversal and absolute paths in allowed source paths", () => {
    const result1 = validateCustomRepositoryConfig({
      ...VALID_CONFIG,
      allowed_source_paths: ["../etc/passwd"],
    });
    assert.equal(result1.valid, false);
    assert.ok(result1.field_errors.allowed_source_paths?.some((e) => e.includes("traversal")));

    const result2 = validateCustomRepositoryConfig({
      ...VALID_CONFIG,
      allowed_source_paths: ["/root/src"],
    });
    assert.equal(result2.valid, false);
    assert.ok(result2.field_errors.allowed_source_paths?.some((e) => e.includes("traversal")));
  });

  it("allows optional expected failure substring for automatic regression discovery", () => {
    const result = validateCustomRepositoryConfig({
      ...VALID_CONFIG,
      expected_failure: "   ",
    });
    assert.equal(result.valid, true);
    assert.equal(result.field_errors.expected_failure, undefined);
  });

  it("MockTransport validates custom configs with same contract", async () => {
    const transport = new MockTransport();
    const result = await transport.validateCustomConfig(VALID_CONFIG);
    assert.equal(result.valid, true);
    assert.equal(result.gate_status, "disabled");
  });

  it("MockTransport filters supported demo tasks when requested", async () => {
    const transport = new MockTransport();
    const demoTasks = await transport.getTasks("supported_demo");
    assert.equal(demoTasks.length, 5);
    assert.equal(demoTasks[0].task_id, "TASK-DEMO-SHOP");
    assert.equal(demoTasks[1].task_id, "TASK-DEMO-PYDANTIC");
    assert.equal(demoTasks[2].task_id, "TASK-DEMO-CLICK");
    assert.equal(demoTasks[3].task_id, "TASK-DEMO-JWT");
    assert.equal(demoTasks[4].task_id, "TASK-091");
  });

  it("MockTransport resolves branches with default branch first", async () => {
    const transport = new MockTransport();
    const res = await transport.resolveBranches("https://github.com/SGOD-pro/repo-medic.git");
    assert.equal(res.default_branch, "main");
    assert.ok(res.branches.length >= 2);
    assert.equal(res.branches[0].name, "main");
    assert.equal(res.branches[0].commit_sha.length, 40);
  });

  it("MockTransport starts custom run and returns summary", async () => {
    const transport = new MockTransport();
    const run = await transport.startCustomRun({
      config: VALID_CONFIG,
      branch: "main",
      search_mode: "sequential",
    });
    assert.ok(run.run_id);
    assert.equal(run.state, "running");
  });
});
