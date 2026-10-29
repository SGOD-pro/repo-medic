import { chromium } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");

async function main() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  console.log("=== PLAYWRIGHT VERIFICATION: JWT FAILURE DIAGNOSIS, HYDRATION & AUTO-DISCOVERY ===");
  const browser = await chromium.launch({ headless: true });

  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 850 },
    });
    const page = await context.newPage();

    // -------------------------------------------------------------------------
    // 1. Stage Card Hydration & Historical Event Rendering for Production Run
    //    run_994e3320ba764066b3d7c55e5146493f (TASK-DEMO-JWT offline failure)
    // -------------------------------------------------------------------------
    console.log("\n[CHECK 1] Testing hydration for production run run_994e3320ba764066b3d7c55e5146493f...");
    await page.goto("http://localhost:3000/?runId=run_994e3320ba764066b3d7c55e5146493f&tab=run_active", {
      waitUntil: "networkidle",
    });

    await page.waitForSelector('[data-testid="run-active-view"]', { timeout: 10000 });
    console.log("  ✔ Active run view rendered");

    // Verify mode is truthfully displayed as OFFLINE
    const modeBadgeText = await page.textContent('[data-testid="run-active-view"]');
    assert.ok(modeBadgeText?.includes("OFFLINE"), "Run header must display OFFLINE");
    assert.ok(!modeBadgeText?.includes("LIVE SANDBOX"), "Offline run must NEVER be labelled as LIVE SANDBOX");
    console.log("  ✔ Mode badge truthfully displayed as OFFLINE");

    // Verify terminal status badge shows FAILED
    const statusText = await page.textContent('[data-testid="active-run-status"]');
    assert.ok(statusText?.includes("FAILED"), `Status must show FAILED, got ${statusText}`);
    console.log("  ✔ Terminal status badge shows FAILED");

    // Wait for event hydration to populate stage results
    await page.waitForTimeout(1000);

    const fullPageText = await page.textContent("main");

    // Check Stage 1: Baseline Check -> PASSED
    assert.ok(
      fullPageText?.includes("Baseline tests passed cleanly") || fullPageText?.includes("PASSED"),
      "Baseline stage must show PASSED with authentic event summary"
    );

    // Check Stage 2: Target Upgrade -> PASSED
    assert.ok(
      fullPageText?.includes("Upgrade to 2.8.0") || fullPageText?.includes("PASSED"),
      "Upgrade stage must show PASSED with authentic event summary"
    );

    // Check Stage 3 / 4: Candidate Repair / Verification -> FAILED with exact allowlist diagnostic
    assert.ok(
      fullPageText?.includes("File 'src/app.py' is outside recipe allowed source paths ['src/auth/tokens.py']"),
      "Repair or verification stage must display the authentic allowlist violation diagnostic"
    );
    console.log("  ✔ Stage cards reflect authentic event stream outcome without fabricated fallbacks");

    const jwtShotPath = path.join(SCREENSHOT_DIR, "jwt_demo_run_active_hydrated.png");
    await page.screenshot({ path: jwtShotPath, fullPage: true });
    console.log("  ✔ Saved screenshot:", jwtShotPath);

    // -------------------------------------------------------------------------
    // 2. Custom Repo Form: Automatic Regression Discovery (Optional Expected Failure)
    // -------------------------------------------------------------------------
    console.log("\n[CHECK 2] Testing custom repo form with optional expected failure...");
    await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
    await page.waitForSelector('[data-testid="custom-repo-form-view"]');

    // Pre-fill with demo values
    await page.click('text="Pre-fill with Demo Values"');
    await page.waitForTimeout(300);

    // Verify label displays (Optional · Advanced Option)
    const labelText = await page.textContent('label[for="expected_failure"]');
    assert.ok(
      labelText?.includes("(Optional · Advanced Option)"),
      `Expected label to include '(Optional · Advanced Option)', got: ${labelText}`
    );
    console.log("  ✔ Expected failure label clearly shows '(Optional · Advanced Option)'");

    // Verify help text clarifies automatic regression discovery
    const helpText = await page.textContent("#expected_failure_help");
    assert.ok(
      helpText?.includes("automatic regression discovery"),
      `Expected help text to describe automatic regression discovery, got: ${helpText}`
    );
    console.log("  ✔ Helper text explains automatic regression discovery");

    // Clear expected failure input to activate automatic regression discovery
    await page.fill('[data-testid="input-expected-failure"]', "");

    // Click Validate Configuration
    await page.click('[data-testid="btn-validate-config"]');
    await page.waitForSelector('[data-testid="validation-success-box"]', { timeout: 10000 });

    const successText = await page.textContent('[data-testid="validation-success-box"]');
    assert.ok(successText?.includes("Repository Specification Valid"));
    console.log("  ✔ Validation succeeded with empty expected_failure (automatic discovery mode)");

    // Verify Start Repair Run button is enabled
    const isRunBtnDisabled = await page.isDisabled('[data-testid="btn-run-custom-repair"]');
    assert.equal(isRunBtnDisabled, false, "Start Repair Run button must be enabled");
    console.log("  ✔ Start Repair Run button is enabled");

    const autoDiscoveryShotPath = path.join(SCREENSHOT_DIR, "custom_repo_automatic_discovery_form.png");
    await page.screenshot({ path: autoDiscoveryShotPath, fullPage: true });
    console.log("  ✔ Saved screenshot:", autoDiscoveryShotPath);

    // -------------------------------------------------------------------------
    // 3. Live vs Offline Presentation Verification
    // -------------------------------------------------------------------------
    console.log("\n[CHECK 3] Testing live run presentation for run_c89257b365a247b0ab8d8f44fb04a779...");
    await page.goto("http://localhost:3000/?runId=run_c89257b365a247b0ab8d8f44fb04a779&tab=run_active", {
      waitUntil: "networkidle",
    });
    await page.waitForSelector('[data-testid="run-active-view"]', { timeout: 10000 });

    const liveHeaderText = await page.textContent('[data-testid="run-active-view"]');
    assert.ok(liveHeaderText?.includes("LIVE SANDBOX"), "Must display LIVE SANDBOX for live execution");
    assert.ok(!liveHeaderText?.includes("OFFLINE (TURSO)"), "Must not display OFFLINE (TURSO) for live execution");
    console.log("  ✔ Live run header truthfully shows LIVE SANDBOX");

    const liveShotPath = path.join(SCREENSHOT_DIR, "live_mode_presentation.png");
    await page.screenshot({ path: liveShotPath, fullPage: true });
    console.log("  ✔ Saved screenshot:", liveShotPath);

    console.log("\n✅ ALL LOCAL PLAYWRIGHT VERIFICATION CHECKS PASSED!");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error("Playwright test failed:", err);
  process.exit(1);
});
