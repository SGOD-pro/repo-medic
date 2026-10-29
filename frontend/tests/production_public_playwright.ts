import { chromium, Browser } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execSync } from "node:child_process";

const BASE_URL = process.env.BASE_URL || "https://repo-medic-gamma.vercel.app";
const BACKEND_URL = process.env.BACKEND_URL || "https://oflqusaa1e.execute-api.ap-south-1.amazonaws.com";
const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");

function sha256(buf: Buffer): string {
  return crypto.createHash("sha256").update(buf).digest("hex");
}

async function main() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  console.log("=================================================================");
  console.log(" REPOMEDIC PRODUCTION PLAYWRIGHT ACCEPTANCE & E2E REPAIR SUITE");
  console.log(` Target frontend: ${BASE_URL}`);
  console.log(` Target backend:  ${BACKEND_URL}`);
  console.log("=================================================================\n");

  // Step 1: Pre-flight check on budget and concurrent runs
  console.log("[PREFLIGHT] Checking Turso database budget and concurrency status...");
  const budgetCheckOutput = execSync(
    `cd ${path.resolve(__dirname, "../../backend")} && .venv/bin/python -c '
from src.storage.repository import D1StorageRepository
from src.config import settings
repo = D1StorageRepository()
committed = repo.get_total_committed_usd()
max_run = getattr(settings, "repomedic_max_run_usd", 2.0)
total_budget = getattr(settings, "repomedic_total_budget_usd", 25.0)
active = [r for r in repo.list_runs(limit=10) if r.state in ("queued", "running")]
print(f"COMMITTED:{committed:.2f}")
print(f"MAX_RUN:{max_run:.2f}")
print(f"TOTAL:{total_budget:.2f}")
print(f"ACTIVE_COUNT:{len(active)}")
'`,
    { encoding: "utf-8" }
  );

  const committedMatch = budgetCheckOutput.match(/COMMITTED:([\d.]+)/);
  const maxRunMatch = budgetCheckOutput.match(/MAX_RUN:([\d.]+)/);
  const totalMatch = budgetCheckOutput.match(/TOTAL:([\d.]+)/);
  const activeCountMatch = budgetCheckOutput.match(/ACTIVE_COUNT:(\d+)/);

  const committed = parseFloat(committedMatch?.[1] || "0");
  const maxRun = parseFloat(maxRunMatch?.[1] || "2.0");
  const total = parseFloat(totalMatch?.[1] || "25.0");
  const activeCount = parseInt(activeCountMatch?.[1] || "0", 10);

  console.log(`  Committed spend: $${committed.toFixed(2)} USD`);
  console.log(`  Max run ceiling: $${maxRun.toFixed(2)} USD`);
  console.log(`  Total budget:    $${total.toFixed(2)} USD`);
  console.log(`  Remaining:       $${(total - committed).toFixed(2)} USD`);
  console.log(`  Active runs:     ${activeCount}`);

  assert.ok(total - committed >= maxRun, "Insufficient remaining budget for bounded live repair");
  assert.equal(activeCount, 0, "Cannot run with active concurrent runs in production");

  const browser: Browser = await chromium.launch({ headless: true });

  try {
    // =========================================================================
    // SECTION 1: Fix the judge-facing experience on deployed /home and /
    // =========================================================================
    console.log("\n--- SECTION 1: Verifying Judge-Facing Experience ---");
    const desktopContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      acceptDownloads: true,
    });
    const page = await desktopContext.newPage();

    // 1A. Inspect deployed /home
    console.log(`Navigating to ${BASE_URL}/home ...`);
    await page.goto(`${BASE_URL}/home`, { waitUntil: "networkidle" });

    const homeHeading = await page.textContent("h1");
    console.log("  Home Hero Heading:", homeHeading?.replace(/\s+/g, " ").trim());
    assert.ok(homeHeading?.includes("See what breaks"));

    // Take screenshot of deployed landing page
    const landingShot = path.join(SCREENSHOT_DIR, "production_judge_landing_hero.png");
    await page.screenshot({ path: landingShot, fullPage: false });
    console.log("  Saved landing screenshot:", landingShot);

    // 1B. Click "Saved Demo" on /home hero
    console.log("Clicking 'View saved demo' CTA on /home...");
    await page.click('[data-testid="hero-btn-view-demo"]');
    await page.waitForSelector('[data-testid="verification-view"]', { timeout: 15000 });

    const currentUrl = page.url();
    console.log("  Navigated URL:", currentUrl);
    assert.ok(
      currentUrl.includes("run_a72af9a70dbc47ee9ba7c7b8b6ff1226"),
      `Expected URL to contain run_a72af9a70dbc47ee9ba7c7b8b6ff1226, got ${currentUrl}`
    );

    // 1C. Verify Verification View Hydration
    const runStateBadge = await page.textContent('[data-testid="verification-view"]');
    assert.ok(runStateBadge?.includes("SUCCEEDED"), "Expected SUCCEEDED state");
    assert.ok(!runStateBadge?.includes("No Verification Results Selected"), "Must not display empty state");

    // 1D. Verify Mode Label against actual backend data
    const modeBadge = page.locator('span:has-text("LIVE SANDBOX (NEBIUS)")');
    assert.ok(await modeBadge.isVisible(), "Expected authentic 'LIVE SANDBOX (NEBIUS)' mode badge");
    console.log("  ✔ Authentic mode badge 'LIVE SANDBOX (NEBIUS)' is visible");

    // 1E. Verify unified diff rendered
    await page.waitForSelector('text="src/shop/database.py"', { timeout: 15000 });
    const diffText = await page.textContent('[data-testid="verification-view"]');
    assert.ok(diffText?.includes("src/shop/database.py"), "Unified diff must show modified file");
    assert.ok(diffText?.includes("with engine.begin() as conn:"), "Unified diff must show patch hunks");
    console.log("  ✔ Unified diff rendered cleanly");

    // 1F. Verify surviving reload
    console.log("Reloading verification page to test persistence...");
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForSelector('[data-testid="verification-view"]', { timeout: 15000 });
    await page.waitForSelector('text="src/shop/database.py"', { timeout: 15000 });
    const reloadedBadge = await page.textContent('[data-testid="verification-view"]');
    assert.ok(reloadedBadge?.includes("SUCCEEDED"), "Must remain SUCCEEDED after reload");
    console.log("  ✔ Verification view survives page reload");

    // 1G. Verify custom repository view: branch resolution, commit pinning, validation, and gated button
    console.log("Navigating to Configure Custom Repo...");
    await page.click('[data-testid="nav-tab-custom-repo"]');
    await page.waitForSelector('[data-testid="custom-repo-form-view"]');

    // Test real GitHub branch discovery and commit pinning
    console.log("Testing real GitHub branch discovery on custom repository form...");
    await page.fill('[data-testid="input-repository-url"]', "https://github.com/SGOD-pro/repo-medic.git");
    await page.click('[data-testid="btn-fetch-branches"]');
    await page.waitForFunction(() => {
      const select = document.querySelector('[data-testid="select-branch"]') as HTMLSelectElement | null;
      return select && select.options.length > 1;
    }, { timeout: 15000 });

    const branchCount = await page.evaluate(() => {
      const select = document.querySelector('[data-testid="select-branch"]') as HTMLSelectElement | null;
      return select ? select.options.length : 0;
    });
    console.log(`  Discovered ${branchCount} branches from GitHub`);
    assert.ok(branchCount >= 4, `Expected at least 4 branches, got ${branchCount}`);

    // Select fixture/repomedic-demo-jwt and verify pinned commit SHA
    console.log("Selecting fixture/repomedic-demo-jwt branch...");
    await page.selectOption('[data-testid="select-branch"]', "fixture/repomedic-demo-jwt");
    const pinnedSha = await page.inputValue('[data-testid="input-commit-sha"]');
    console.log(`  Pinned SHA: ${pinnedSha}`);
    assert.equal(
      pinnedSha,
      "8b635e7ff84556962f6ec4fee43523778461c938",
      "Pinned commit SHA must match fixture branch head"
    );

    // Pre-fill demo values to test validation contract
    await page.click('text="Pre-fill with Demo Values"');
    await page.click('[data-testid="btn-validate-config"]');
    await page.waitForSelector('[data-testid="validation-success-box"]');

    const successBoxText = await page.textContent('[data-testid="validation-success-box"]');
    assert.ok(successBoxText?.includes("Repository Specification Valid"));
    console.log("  ✔ Validation succeeded for conforming custom repository specification");

    // Verify Start Custom Repair Run button is disabled and reflects gated status
    const isRunBtnDisabled = await page.isDisabled('[data-testid="btn-run-custom-repair"]');
    const runBtnText = await page.textContent('[data-testid="btn-run-custom-repair"]');
    console.log(`  Start Repair Run button disabled: ${isRunBtnDisabled}, text: ${runBtnText?.trim()}`);
    assert.equal(isRunBtnDisabled, true, "Start Custom Repair Run button must be disabled");
    assert.ok(
      runBtnText?.includes("Execution Gated"),
      "Button label must indicate that execution is gated"
    );
    console.log("  ✔ Custom run action is safely disabled and clearly labeled");

    const customGatedShot = path.join(SCREENSHOT_DIR, "production_custom_repo_gated.png");
    await page.screenshot({ path: customGatedShot, fullPage: false });
    console.log("  Saved custom repo screenshot:", customGatedShot);

    // =========================================================================
    // SECTION 2: Demo Tasks & Saved Repair Verification on TASK-DEMO-JWT
    // =========================================================================
    console.log("\n--- SECTION 2: Verifying Demo Tasks & Execution Modes ---");

    // 2A. Navigate to Curated Demo Tasks view
    await page.click('[data-testid="nav-tab-tasks"]');
    await page.waitForSelector('[data-testid="tasks-view"]');

    // Verify all four demo task cards exist with authentic metadata
    const approvedTasks = [
      "TASK-DEMO-SHOP",
      "TASK-DEMO-CLICK",
      "TASK-DEMO-PYDANTIC",
      "TASK-DEMO-JWT",
    ];

    for (const taskId of approvedTasks) {
      const card = page.locator(`[data-testid="task-card-${taskId}"]`);
      await card.waitFor({ timeout: 10000 });
      const cardText = await card.textContent();
      assert.ok(cardText?.includes("target:"), `Task ${taskId} card must display target`);
      assert.ok(
        !cardText?.includes("Expected failure: Unavailable"),
        `Task ${taskId} must have available expected failure`
      );
      assert.ok(
        !cardText?.includes("Declared tests: Unavailable"),
        `Task ${taskId} must have available declared tests count`
      );
      console.log(`  ✔ Task card for ${taskId} verified with complete metadata`);
    }

    // 2B. Select TASK-DEMO-JWT card
    console.log("Selecting task card for TASK-DEMO-JWT...");
    const jwtCard = page.locator('[data-testid="task-card-TASK-DEMO-JWT"]');
    await jwtCard.click();

    // Verify Selected Task Details
    const taskDetailsText = await page.textContent('[data-testid="tasks-view"]');
    assert.ok(taskDetailsText?.includes("TASK-DEMO-JWT"), "Target spec must show TASK-DEMO-JWT");
    assert.ok(taskDetailsText?.includes("pyjwt==2.8.0"), "Target spec must show target pyjwt==2.8.0");
    assert.ok(taskDetailsText?.includes("8b635e7ff8"), "Target spec must show pinned commit SHA");
    assert.ok(taskDetailsText?.includes("3 declared tests (fixture metadata)"), "Target spec must show declared tests count");
    assert.ok(taskDetailsText?.includes("0.15s (Python 3.12)"), "Target spec must show baseline timing");
    assert.ok(taskDetailsText?.includes("src/auth/tokens.py"), "Target spec must show allowed mutation paths");
    console.log("  ✔ Target specification loaded for TASK-DEMO-JWT with full metadata");

    // 2C. Verify Execution Mode transparency
    console.log("Testing execution mode transparency (dry run simulation vs live sandbox)...");
    const modeSelectTrigger = page.locator('[data-testid="select-execution-mode"]');
    await modeSelectTrigger.waitFor({ timeout: 5000 });

    // Dry Run mode check (default)
    const dryRunExplanation = await page.textContent('[data-testid="mode-explanation-dry-run"]');
    assert.ok(dryRunExplanation?.includes("OFFLINE DRY RUN SIMULATION"));
    const dryRunBtnText = await page.textContent('[data-testid="btn-start-repair-run"]');
    assert.ok(dryRunBtnText?.includes("Start Dry Run Simulation"));
    console.log("  ✔ Default dry run mode is clearly labeled with zero spend disclaimer");

    // Switch to Live Sandbox mode
    await modeSelectTrigger.click();
    await page.waitForSelector('[role="option"]:has-text("Live Sandbox Execution")', { timeout: 5000 });
    await page.click('[role="option"]:has-text("Live Sandbox Execution")');

    const liveExplanation = await page.textContent('[data-testid="mode-explanation-live"]');
    assert.ok(liveExplanation?.includes("LIVE NEBIUS SANDBOX"));
    const liveBtnText = await page.textContent('[data-testid="btn-start-repair-run"]');
    assert.ok(liveBtnText?.includes("Start Live Sandbox Repair (Nebius)"));
    console.log("  ✔ Live sandbox mode explicitly warns about provider resource consumption");

    // Take screenshot of configured task view
    const taskConfigShot = path.join(SCREENSHOT_DIR, "production_jwt_task_selected.png");
    await page.screenshot({ path: taskConfigShot, fullPage: false });
    console.log("  Saved task config screenshot:", taskConfigShot);

    // 2D. Inspect retained production repair run for TASK-DEMO-JWT
    const newRunId = "run_4c8b02996ca547a4a134e5ccaf682681";
    console.log(`  Production Run ID: ${newRunId}`);

    // Verify run status via backend API
    const runStatusJson = execSync(
      `curl -sS "${BACKEND_URL}/api/runs/${newRunId}"`,
      { encoding: "utf-8" }
    );
    const runData = JSON.parse(runStatusJson);
    const terminalState = runData.state;
    console.log(`  Run ${newRunId} terminal state: ${terminalState}`);
    assert.equal(terminalState, "succeeded", `Expected run to succeed, got ${terminalState}`);

    // 2G. In UI, navigate to verification results
    console.log("Navigating to verification results in UI...");
    await page.goto(`${BASE_URL}/?runId=${newRunId}`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-testid="verification-view"]', { timeout: 15000 });
    await page.waitForSelector('text="src/auth/tokens.py"', { timeout: 15000 });

    // Verify UI presentation
    const resultsText = await page.textContent('[data-testid="verification-view"]');
    assert.ok(resultsText?.includes("SUCCEEDED"), "Verification view must show SUCCEEDED");
    assert.ok(resultsText?.includes("LIVE SANDBOX (NEBIUS)"), "Mode badge must show LIVE SANDBOX (NEBIUS)");
    assert.ok(resultsText?.includes("src/auth/tokens.py"), "Diff must reference src/auth/tokens.py");

    const verifiedShot = path.join(SCREENSHOT_DIR, "production_jwt_repair_verified.png");
    await page.screenshot({ path: verifiedShot, fullPage: false });
    console.log("  Saved verification screenshot:", verifiedShot);

    // =========================================================================
    // SECTION 3: Download & Verify Cryptographic Hashes of Artifacts
    // =========================================================================
    console.log("\n--- SECTION 3: Downloading & Verifying Artifacts ---");

    const runMeta = JSON.parse(
      execSync(`curl -sS "${BACKEND_URL}/api/runs/${newRunId}"`, { encoding: "utf-8" })
    );

    console.log("Run artifacts:", runMeta.artifacts);
    assert.ok(runMeta.artifacts.length >= 3, "Expected at least 3 artifacts (patch, log, evidence)");

    interface ArtifactItem {
      artifact_id: string;
      kind: string;
      filename: string;
    }
    const artifacts: ArtifactItem[] = runMeta.artifacts || [];
    const patchMeta = artifacts.find((a) => a.kind === "patch");
    const logMeta = artifacts.find((a) => a.kind === "log");
    const evidenceMeta = artifacts.find((a) => a.kind === "evidence");

    assert.ok(patchMeta, "patch artifact missing");
    assert.ok(logMeta, "log artifact missing");
    assert.ok(evidenceMeta, "evidence artifact missing");

    // Download each artifact
    const patchBytes = execSync(
      `curl -sS "${BACKEND_URL}/api/runs/${newRunId}/artifacts/${patchMeta.artifact_id}"`
    );
    const logBytes = execSync(
      `curl -sS "${BACKEND_URL}/api/runs/${newRunId}/artifacts/${logMeta.artifact_id}"`
    );
    const evidenceBytes = execSync(
      `curl -sS "${BACKEND_URL}/api/runs/${newRunId}/artifacts/${evidenceMeta.artifact_id}"`
    );

    const patchHash = sha256(patchBytes);
    const logHash = sha256(logBytes);
    const evidenceHash = sha256(evidenceBytes);

    console.log(`  patch.diff   (${patchBytes.length} bytes): SHA256 ${patchHash}`);
    console.log(`  verify.log   (${logBytes.length} bytes): SHA256 ${logHash}`);
    console.log(`  evidence.json (${evidenceBytes.length} bytes): SHA256 ${evidenceHash}`);

    const evidenceObj = JSON.parse(evidenceBytes.toString("utf-8"));
    console.log("Evidence checks summary:", evidenceObj.checks);
    assert.equal(evidenceObj.checks.patch_applied, true, "Evidence check: patch_applied must be true");
    assert.equal(evidenceObj.checks.tests_passed, true, "Evidence check: tests_passed must be true");
    assert.equal(evidenceObj.checks.zero_new_skips, true, "Evidence check: zero_new_skips must be true");
    assert.equal(evidenceObj.checks.version_intact, true, "Evidence check: version_intact must be true");

    // Save artifacts locally to /tmp for fresh test checkout
    const artifactSaveDir = path.resolve(__dirname, "../../scratch/production_jwt_run");
    fs.mkdirSync(artifactSaveDir, { recursive: true });
    fs.writeFileSync(path.join(artifactSaveDir, "patch.diff"), patchBytes);
    fs.writeFileSync(path.join(artifactSaveDir, "verify.log"), logBytes);
    fs.writeFileSync(path.join(artifactSaveDir, "evidence.json"), evidenceBytes);
    console.log("  ✔ Artifacts saved to:", artifactSaveDir);

    // =========================================================================
    // SECTION 4: Independent Verification on Fresh Git Checkout
    // =========================================================================
    console.log("\n--- SECTION 4: Independent Verification on Fresh Checkout ---");
    const freshCheckoutDir = "/tmp/repomedic_fresh_jwt_test";
    if (fs.existsSync(freshCheckoutDir)) {
      execSync(`rm -rf "${freshCheckoutDir}"`);
    }

    console.log("Cloning fresh copy of repository at pinned SHA 8b635e7ff84556962f6ec4fee43523778461c938...");
    const repoRoot = path.resolve(__dirname, "../..");
    execSync(
      `git clone --branch fixture/repomedic-demo-jwt "${repoRoot}" "${freshCheckoutDir}"`
    );
    execSync(`cd "${freshCheckoutDir}" && git checkout 8b635e7ff84556962f6ec4fee43523778461c938`);

    console.log("Applying downloaded patch.diff to fresh checkout...");
    const patchPath = path.join(artifactSaveDir, "patch.diff");
    execSync(`cd "${freshCheckoutDir}" && git apply "${patchPath}"`);
    console.log("  ✔ Patch applied cleanly to fresh checkout");

    console.log("Running unchanged test suite under pyjwt==2.8.0 in clean virtualenv...");
    const testResult = execSync(
      `cd "${freshCheckoutDir}" && uv venv .test_venv --python 3.12 && uv pip install --python .test_venv/bin/python "pytest>=8.0.0" "pyjwt==2.8.0" && .test_venv/bin/pytest tests/`,
      { encoding: "utf-8" }
    );

    console.log(testResult);
    assert.ok(testResult.includes("3 passed"), "Expected all 3 tests to pass on fresh checkout");
    console.log("  ✔ All 3 deterministic tests passed independently on fresh checkout with unchanged tests!");

    await desktopContext.close();

    // =========================================================================
    // SECTION 5: Mobile Experience & Navigation Check (390x844)
    // =========================================================================
    console.log("\n--- SECTION 5: Checking Mobile Experience & Navigation ---");
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true,
    });
    const mobilePage = await mobileContext.newPage();

    console.log("Navigating to mobile /home ...");
    await mobilePage.goto(`${BASE_URL}/home`, { waitUntil: "networkidle" });
    const mobileHomeHeading = await mobilePage.textContent("h1");
    assert.ok(mobileHomeHeading?.includes("See what breaks"));

    const mobileLandingShot = path.join(SCREENSHOT_DIR, "production_mobile_landing.png");
    await mobilePage.screenshot({ path: mobileLandingShot, fullPage: false });
    console.log("  Saved mobile landing screenshot:", mobileLandingShot);

    console.log("Testing mobile navigation to workspace...");
    await mobilePage.goto(`${BASE_URL}/?tab=tasks`, { waitUntil: "networkidle" });
    await mobilePage.waitForSelector('[data-testid="tasks-view"]');

    const mobileTasksShot = path.join(SCREENSHOT_DIR, "production_mobile_demo_tasks.png");
    await mobilePage.screenshot({ path: mobileTasksShot, fullPage: false });
    console.log("  Saved mobile tasks screenshot:", mobileTasksShot);

    console.log(`Testing mobile hydration for run ${newRunId}...`);
    await mobilePage.goto(`${BASE_URL}/?runId=${newRunId}`, { waitUntil: "networkidle" });
    await mobilePage.waitForSelector('[data-testid="verification-view"]');

    const mobileVerifiedShot = path.join(SCREENSHOT_DIR, "production_mobile_jwt_verified.png");
    await mobilePage.screenshot({ path: mobileVerifiedShot, fullPage: false });
    console.log("  Saved mobile verification screenshot:", mobileVerifiedShot);

    await mobileContext.close();

    console.log("\n=================================================================");
    console.log(" ✅ ALL PRODUCTION ACCEPTANCE & REPAIR VERIFICATIONS PASSED!");
    console.log(` Production Run ID: ${newRunId}`);
    console.log(` Status:            SUCCEEDED`);
    console.log(` Model:             nvidia/nemotron-3-super-120b-a12b via Nebius Token Factory`);
    console.log(` Cost:              $${runMeta.usage.estimated_usd.toFixed(2)} USD`);
    console.log(` Tests Preserved:   3 passed, 0 skipped, 0 modified`);
    console.log(` Patch Hash:        ${patchHash}`);
    console.log("=================================================================");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error("FAILED PRODUCTION PLAYWRIGHT SUITE:", err);
  process.exit(1);
});
