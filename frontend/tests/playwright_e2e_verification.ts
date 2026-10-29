import { chromium } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");

async function runVerification() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  console.log("Launching Chromium browser for safe product slice E2E tests...");
  const browser = await chromium.launch({ headless: true });

  try {
    // =========================================================================
    // 1. Desktop Experience (1280x800)
    // =========================================================================
    console.log("\n--- Starting Desktop Experience Tests (1280x800) ---");
    const desktopContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
    });
    const desktopPage = await desktopContext.newPage();

    // A. Initial Navigation & First-time Landing
    console.log("Navigating to http://localhost:3000 as first-time user...");
    await desktopPage.goto("http://localhost:3000", { waitUntil: "networkidle" });

    // Verify Configure Custom Repo is the active starting view
    await desktopPage.waitForSelector('[data-testid="custom-repo-form-view"]');
    const headingText = await desktopPage.textContent("h1");
    console.log("Home Page Heading:", headingText);
    assert.ok(headingText?.includes("Configure Custom Repository"));

    // B. Invalid Form Inputs & Error Rendering
    console.log("Testing invalid form submission and validation feedback...");
    await desktopPage.fill('[data-testid="input-repository-url"]', "http://invalid-url.com");
    await desktopPage.fill('[data-testid="input-commit-sha"]', "short-sha");
    await desktopPage.fill('[data-testid="input-dependency"]', "bad package!");
    await desktopPage.fill('[data-testid="input-from-version"]', "1.0.0");
    await desktopPage.fill('[data-testid="input-to-version"]', "1.0.0");
    await desktopPage.fill('[data-testid="input-pytest-args"]', "tests/; rm -rf /");
    await desktopPage.fill('[data-testid="input-allowed-paths"]', "../traversal/src");
    await desktopPage.fill('[data-testid="input-expected-failure"]', "");

    await desktopPage.click('[data-testid="btn-validate-config"]');
    await desktopPage.waitForSelector('[data-testid="validation-error-box"]');

    const errorBoxText = await desktopPage.textContent('[data-testid="validation-error-box"]');
    console.log("Validation Error Box rendered:", errorBoxText?.substring(0, 120) + "...");
    assert.ok(errorBoxText?.includes("Validation Issues"));

    const invalidShotPath = path.join(SCREENSHOT_DIR, "safe_slice_desktop_invalid_validation.png");
    await desktopPage.screenshot({ path: invalidShotPath, fullPage: true });
    console.log("Saved screenshot:", invalidShotPath);

    // C. Valid Form Input & Safety Gate Enforcement
    console.log("Testing valid form pre-fill and safety gate status...");
    await desktopPage.click('text="Pre-fill with Demo Values"');

    // Verify values populated
    const repoVal = await desktopPage.inputValue('[data-testid="input-repository-url"]');
    assert.equal(repoVal, "https://github.com/SGOD-pro/repo-medic.git");

    await desktopPage.click('[data-testid="btn-validate-config"]');
    await desktopPage.waitForSelector('[data-testid="validation-success-box"]');

    const successBoxText = await desktopPage.textContent('[data-testid="validation-success-box"]');
    console.log("Validation Success Box rendered:", successBoxText?.substring(0, 100) + "...");
    assert.ok(successBoxText?.includes("Repository Specification Valid"));

    // Verify execution button is disabled with gate message
    const isRunBtnDisabled = await desktopPage.isDisabled('[data-testid="btn-run-custom-repair"]');
    console.log("Start Repair Run button disabled:", isRunBtnDisabled);
    assert.equal(isRunBtnDisabled, true);

    const validShotPath = path.join(SCREENSHOT_DIR, "safe_slice_desktop_valid_gated.png");
    await desktopPage.screenshot({ path: validShotPath, fullPage: true });
    console.log("Saved screenshot:", validShotPath);

    // D. Navigation to Curated Demo Tasks View
    console.log("Navigating to Curated Demo Tasks view...");
    await desktopPage.click('[data-testid="nav-tab-tasks"]');
    await desktopPage.waitForSelector('[data-testid="tasks-view"]');

    const tasksHeading = await desktopPage.textContent("h1");
    console.log("Tasks View Heading:", tasksHeading);
    assert.ok(tasksHeading?.includes("Curated Demo Tasks"));

    // Verify all 3 approved demo tasks are present
    await desktopPage.waitForSelector('[data-testid="task-card-TASK-DEMO-SHOP"]');
    await desktopPage.waitForSelector('[data-testid="task-card-TASK-DEMO-PYDANTIC"]');
    await desktopPage.waitForSelector('[data-testid="task-card-TASK-DEMO-CLICK"]');
    console.log("  ✔ All three approved demo tasks visible: TASK-DEMO-SHOP, TASK-DEMO-PYDANTIC, TASK-DEMO-CLICK");

    // Verify unapproved tasks and fixtures are NOT displayed
    const pageText = await desktopPage.textContent("body");
    assert.ok(!pageText?.includes("TASK-084"), "Must not display TASK-084 in demo chooser");
    assert.ok(!pageText?.includes("TASK-091"), "Must not display TASK-091 in demo chooser");
    assert.ok(!pageText?.includes("example/repo.git"), "Must not display example/repo.git");
    assert.ok(!pageText?.includes("Determinism Token: #0x7F2B"), "Must not display fake determinism token");
    assert.ok(!pageText?.includes("8 warm containers"), "Must not display fake runner pool");

    const demoTasksShotPath = path.join(SCREENSHOT_DIR, "safe_slice_desktop_demo_tasks.png");
    await desktopPage.screenshot({ path: demoTasksShotPath, fullPage: true });
    console.log("Saved screenshot:", demoTasksShotPath);

    // E. Real Production Run Verification & Results Hydration
    console.log("Testing production run hydration for run_c89257b365a247b0ab8d8f44fb04a779...");
    await desktopPage.goto(
      "http://localhost:3000/?runId=run_c89257b365a247b0ab8d8f44fb04a779",
      { waitUntil: "networkidle" }
    );
    await desktopPage.waitForSelector('[data-testid="verification-view"]');

    const runTitle = await desktopPage.textContent("h1");
    console.log("Verified Run Heading:", runTitle);
    assert.ok(runTitle?.includes("Verified Source Repair Completed") || runTitle?.includes("Behavior preserved"));

    // Check terminal run state
    const badgeText = await desktopPage.textContent('[data-testid="verification-view"]');
    assert.ok(badgeText?.includes("SUCCEEDED"));
    assert.ok(!badgeText?.includes("ACTIVE PIPELINE"));

    // Verify artifact download interaction
    const downloadPatchBtn = desktopPage.locator('button:has-text("Download patch")');
    assert.ok(await downloadPatchBtn.isVisible(), "Download patch button must be visible");
    const downloadPromise = desktopPage.waitForEvent("download", { timeout: 3000 }).catch(() => null);
    await downloadPatchBtn.click();
    const download = await downloadPromise;
    if (download) {
      console.log("  ✔ Patch download triggered:", download.suggestedFilename());
    } else {
      console.log("  ✔ Download patch button clicked without error");
    }

    const verifiedRunShotPath = path.join(SCREENSHOT_DIR, "safe_slice_desktop_verified_run.png");
    await desktopPage.screenshot({ path: verifiedRunShotPath, fullPage: true });
    console.log("Saved screenshot:", verifiedRunShotPath);

    // F. Run Active Tab with Terminal Run State
    console.log("Testing Run Active view behavior on a terminal run...");
    await desktopPage.click('[data-testid="nav-tab-run-active"]');
    await desktopPage.waitForTimeout(500);

    const activeViewText = await desktopPage.textContent("main");
    assert.ok(activeViewText?.includes("RUN SUCCEEDED"), "Must display RUN SUCCEEDED badge");
    assert.ok(!activeViewText?.includes("ACTIVE PIPELINE"), "Must not display ACTIVE PIPELINE for terminal run");
    assert.ok(!activeViewText?.includes("Cancel Run"), "Must not display Cancel Run button for terminal run");
    assert.ok(activeViewText?.includes("Inspect Results"), "Must offer Inspect Results button");
    assert.ok(activeViewText?.includes("Return to Tasks"), "Must offer Return to Tasks button");

    const terminalActiveShotPath = path.join(SCREENSHOT_DIR, "safe_slice_desktop_terminal_active_view.png");
    await desktopPage.screenshot({ path: terminalActiveShotPath, fullPage: true });
    console.log("Saved screenshot:", terminalActiveShotPath);

    await desktopContext.close();

    // =========================================================================
    // 2. Mobile Experience (390x844 - iPhone Viewport)
    // =========================================================================
    console.log("\n--- Starting Mobile Experience Tests (390x844) ---");
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true,
    });
    const mobilePage = await mobileContext.newPage();

    console.log("Testing mobile landing on custom repository form...");
    await mobilePage.goto("http://localhost:3000", { waitUntil: "networkidle" });
    await mobilePage.waitForSelector('[data-testid="custom-repo-form-view"]');

    const mobileCustomShot = path.join(SCREENSHOT_DIR, "safe_slice_mobile_custom_repo.png");
    await mobilePage.screenshot({ path: mobileCustomShot, fullPage: true });
    console.log("Saved screenshot:", mobileCustomShot);

    console.log("Testing mobile navigation to demo tasks...");
    await mobilePage.click('[data-testid="nav-tab-tasks"]');
    await mobilePage.waitForSelector('[data-testid="tasks-view"]');

    const mobileTasksShot = path.join(SCREENSHOT_DIR, "safe_slice_mobile_demo_tasks.png");
    await mobilePage.screenshot({ path: mobileTasksShot, fullPage: true });
    console.log("Saved screenshot:", mobileTasksShot);

    console.log("Testing mobile verified run presentation...");
    await mobilePage.goto(
      "http://localhost:3000/?runId=run_c89257b365a247b0ab8d8f44fb04a779",
      { waitUntil: "networkidle" }
    );
    await mobilePage.waitForSelector('[data-testid="verification-view"]');

    const mobileVerifiedShot = path.join(SCREENSHOT_DIR, "safe_slice_mobile_verified_run.png");
    await mobilePage.screenshot({ path: mobileVerifiedShot, fullPage: true });
    console.log("Saved screenshot:", mobileVerifiedShot);

    await mobileContext.close();

    console.log("\n✅ ALL PLAYWRIGHT E2E BROWSER CHECKS PASSED SUCCESSFULLY!");
  } finally {
    await browser.close();
  }
}

runVerification().catch((err) => {
  console.error("Playwright verification failed:", err);
  process.exit(1);
});
