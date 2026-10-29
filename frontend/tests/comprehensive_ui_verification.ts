import { chromium } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const SCREENSHOT_DIR = path.resolve(__dirname, "../../artifacts/refactor_verification");

async function runRefactorVerification() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  console.log("=== COMPREHENSIVE REFACTOR UI / UX VERIFICATION ===");
  const browser = await chromium.launch({ headless: true });

  try {
    // -------------------------------------------------------------
    // 1. DESKTOP WORKSPACE (1280x800)
    // -------------------------------------------------------------
    console.log("\n[CHECK 1] Desktop (1280x800) - Home intro & Configure Form");
    const desktopContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
    });
    const page = await desktopContext.newPage();

    await page.goto("http://localhost:3000", { waitUntil: "networkidle" });

    // Verify Home Section Sequence
    const workflowTitle = await page.textContent('text="Automated Python Dependency Regression Repair"');
    assert.ok(workflowTitle, "Workflow headline must be visible");

    // Verify 4-step sequence
    const baselineStep = await page.locator('text="Baseline Check"').isVisible();
    const upgradeStep = await page.locator('text="Upgrade Failure"').isVisible();
    const candidateStep = await page.locator('text="Candidate Patch"').isVisible();
    const verificationStep = await page.locator('text="Verification"').isVisible();
    assert.ok(baselineStep && upgradeStep && candidateStep && verificationStep, "All 4 workflow steps must be visible");

    // Verify Configure form immediately follows
    const formHeading = await page.textContent('h1');
    assert.ok(formHeading?.includes("Configure Custom Repository"), "Configure heading must be present");

    // Take screenshot of desktop home & configure
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "01_desktop_home_configure.png"), fullPage: true });
    console.log("  ✔ Saved 01_desktop_home_configure.png");

    // Test Validation feedback immediately follows form
    await page.fill('[data-testid="input-repository-url"]', "invalid-url");
    await page.click('[data-testid="btn-validate-config"]');
    await page.waitForSelector('[data-testid="validation-error-box"]');
    console.log("  ✔ Validation error box displayed immediately after actions");

    // Test that editing field clears validation box
    await page.fill('[data-testid="input-repository-url"]', "https://github.com/owner/repo");
    const errorBoxCount = await page.locator('[data-testid="validation-error-box"]').count();
    assert.equal(errorBoxCount, 0, "Validation error box must clear when input changes");
    console.log("  ✔ Validation box cleared upon field modification");

    // Test Pre-fill Demo
    await page.click('text="Pre-fill with Demo Values"');
    await page.click('[data-testid="btn-validate-config"]');
    await page.waitForSelector('[data-testid="validation-success-box"]');
    console.log("  ✔ Pre-fill validated successfully");

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "02_desktop_validation_success.png") });
    console.log("  ✔ Saved 02_desktop_validation_success.png");

    // -------------------------------------------------------------
    // 2. DEMO TASKS VIEW (1280x800)
    // -------------------------------------------------------------
    console.log("\n[CHECK 2] Desktop Demo Tasks - Selection and Sticky Action");
    await page.click('[data-testid="nav-tab-tasks"]');
    await page.waitForSelector('[data-testid="tasks-view"]');

    // Verify task cards
    const demoShopCard = page.locator('[data-testid="task-card-TASK-DEMO-SHOP"]');
    await demoShopCard.waitFor({ state: "visible" });
    assert.equal(await demoShopCard.getAttribute("role"), "radio", "Task card must have role=radio");

    // Verify saved runs banner
    const savedBanner = await page.locator('text="Past Verified Production Runs (Instant Results)"').isVisible();
    assert.ok(savedBanner, "Saved verification banner must be distinct");

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "03_desktop_demo_tasks.png"), fullPage: true });
    console.log("  ✔ Saved 03_desktop_demo_tasks.png");

    // -------------------------------------------------------------
    // 3. HISTORY DRAWER SLIDE-OVER
    // -------------------------------------------------------------
    console.log("\n[CHECK 3] History Drawer Open / Close / Select");
    const historyBtn = page.locator('button:has-text("History")');
    await historyBtn.click();
    await page.waitForSelector('text="Run History"');

    // Verify history runs rendered
    const historyItems = page.locator('[role="dialog"] [role="button"]');
    const count = await historyItems.count();
    console.log(`  History items visible in drawer: ${count}`);
    assert.ok(count >= 3, "At least 3 seeded history runs must be present");

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "04_desktop_history_drawer.png") });
    console.log("  ✔ Saved 04_desktop_history_drawer.png");

    // Select the first history run (run-success-1)
    await historyItems.first().click();
    await page.waitForTimeout(600);

    // Verify routing to verification view
    const verifView = page.locator('[data-testid="verification-view"]');
    await verifView.waitFor({ state: "visible" });
    console.log("  ✔ History item selected and hydrated verification view");

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "05_desktop_hydrated_verification.png"), fullPage: true });
    console.log("  ✔ Saved 05_desktop_hydrated_verification.png");

    await desktopContext.close();

    // -------------------------------------------------------------
    // 4. SHORT VIEWPORT (800x480) - Test reachability of actions
    // -------------------------------------------------------------
    console.log("\n[CHECK 4] Short Viewport (800x480) - Mobile / Laptop short screen");
    const shortContext = await browser.newContext({
      viewport: { width: 800, height: 480 },
    });
    const shortPage = await shortContext.newPage();
    await shortPage.goto("http://localhost:3000", { waitUntil: "networkidle" });

    // Switch to tasks
    await shortPage.click('[data-testid="nav-tab-tasks"]');
    await shortPage.waitForSelector('[data-testid="tasks-view"]');

    // Check Start button visibility
    const startBtn = shortPage.locator('button:has-text("Start repair run")');
    await startBtn.scrollIntoViewIfNeeded();
    assert.ok(await startBtn.isVisible(), "Start repair run button must be reachable on short viewport");

    await shortPage.screenshot({ path: path.join(SCREENSHOT_DIR, "06_short_viewport_tasks.png") });
    console.log("  ✔ Saved 06_short_viewport_tasks.png");

    await shortContext.close();

    // -------------------------------------------------------------
    // 5. NARROW MOBILE (320x568 - iPhone SE / narrowest target)
    // -------------------------------------------------------------
    console.log("\n[CHECK 5] Narrow Mobile (320x568) - Responsive Containment");
    const narrowContext = await browser.newContext({
      viewport: { width: 320, height: 568 },
      isMobile: true,
      hasTouch: true,
    });
    const narrowPage = await narrowContext.newPage();
    await narrowPage.goto("http://localhost:3000", { waitUntil: "networkidle" });

    // Verify no horizontal overflow on body
    const bodyScrollWidth = await narrowPage.evaluate(() => document.body.scrollWidth);
    const windowInnerWidth = await narrowPage.evaluate(() => window.innerWidth);
    console.log(`  Narrow mobile width: inner=${windowInnerWidth}, scroll=${bodyScrollWidth}`);
    assert.ok(bodyScrollWidth <= windowInnerWidth + 1, "Page must not have horizontal overflow on 320px screen");

    await narrowPage.screenshot({ path: path.join(SCREENSHOT_DIR, "07_narrow_mobile_configure.png"), fullPage: true });
    console.log("  ✔ Saved 07_narrow_mobile_configure.png");

    // Test Navigation on narrow mobile
    await narrowPage.click('[data-testid="nav-tab-tasks"]');
    await narrowPage.waitForSelector('[data-testid="tasks-view"]');
    await narrowPage.screenshot({ path: path.join(SCREENSHOT_DIR, "08_narrow_mobile_tasks.png"), fullPage: true });
    console.log("  ✔ Saved 08_narrow_mobile_tasks.png");

    // Test Verified Run on narrow mobile
    await narrowPage.goto("http://localhost:3000/?runId=run_c89257b365a247b0ab8d8f44fb04a779", { waitUntil: "networkidle" });
    await narrowPage.waitForSelector('[data-testid="verification-view"]');
    await narrowPage.screenshot({ path: path.join(SCREENSHOT_DIR, "09_narrow_mobile_verification.png"), fullPage: true });
    console.log("  ✔ Saved 09_narrow_mobile_verification.png");

    await narrowContext.close();

    // -------------------------------------------------------------
    // 6. TABLET (768x1024 - iPad Viewport)
    // -------------------------------------------------------------
    console.log("\n[CHECK 6] Tablet (768x1024) - Intermediate Layout");
    const tabletContext = await browser.newContext({
      viewport: { width: 768, height: 1024 },
    });
    const tabletPage = await tabletContext.newPage();
    await tabletPage.goto("http://localhost:3000", { waitUntil: "networkidle" });

    await tabletPage.screenshot({ path: path.join(SCREENSHOT_DIR, "10_tablet_configure.png"), fullPage: true });
    console.log("  ✔ Saved 10_tablet_configure.png");

    await tabletPage.click('[data-testid="nav-tab-tasks"]');
    await tabletPage.waitForSelector('[data-testid="tasks-view"]');
    await tabletPage.screenshot({ path: path.join(SCREENSHOT_DIR, "11_tablet_tasks.png"), fullPage: true });
    console.log("  ✔ Saved 11_tablet_tasks.png");

    await tabletContext.close();

    console.log("\n============================================================");
    console.log("ALL 6 COMPREHENSIVE REFACTOR UI / UX CHECKS PASSED!");
    console.log("============================================================\n");
  } finally {
    await browser.close();
  }
}

runRefactorVerification().catch((err) => {
  console.error("Refactor verification failed:", err);
  process.exit(1);
});

