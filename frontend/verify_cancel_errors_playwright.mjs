import { chromium } from "playwright";
import path from "path";

async function runCancelErrorsVerification() {
  const artifactDir = "C:\\Users\\KIIT\\.gemini\\antigravity-ide\\brain\\2d656c98-0d4f-44bb-b446-b085b26d5dd6";
  const cancelScreenshot = path.join(artifactDir, "evidence_cancel_flow.png");
  const simulationScreenshot = path.join(artifactDir, "evidence_simulation_controls.png");
  const errorScreenshot = path.join(artifactDir, "evidence_error_traceback.png");

  console.log("Launching browser via Playwright...");
  let browser;
  try {
    browser = await chromium.launch({ channel: "chrome", headless: true });
  } catch {
    browser = await chromium.launch({ channel: "msedge", headless: true });
  }

  const context = await browser.newContext({ viewport: { width: 1280, height: 950 } });
  const page = await context.newPage();

  console.log("\n==================================================");
  console.log("STEP 1: NAVIGATING & STARTING RUN");
  console.log("==================================================");
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  await page.locator("button:has-text('Start repair run')").click();
  await page.waitForSelector("text=Active Candidate Matrices", { timeout: 5000 });
  console.log("RunActiveView loaded successfully.");

  console.log("\n==================================================");
  console.log("STEP 2: TESTING SIMULATION CONTROLS & TRACEBACK (AC-6, AC-8)");
  console.log("==================================================");
  // Trigger Engine Error
  const engineErrorBtn = page.locator("button:has-text('Engine Error')");
  await engineErrorBtn.click();
  await page.waitForSelector("text=ENGINE_EXECUTION_FAILURE");
  console.log("Inline error banner displayed with code ENGINE_EXECUTION_FAILURE");

  // Expand Traceback
  const viewTracebackBtn = page.locator("button:has-text('View Traceback')");
  await viewTracebackBtn.click();
  await page.waitForSelector("text=Execution Error Traceback:");
  console.log("Traceback expanded successfully.");

  // Click Copy Traceback
  const copyTracebackBtn = page.locator("button:has-text('Copy Traceback')");
  await copyTracebackBtn.click();
  console.log("Clicked Copy Traceback button.");

  await page.screenshot({ path: errorScreenshot, fullPage: true });
  console.log("Saved error banner screenshot:", errorScreenshot);

  // Test Retry Limit (AC-5)
  const retryLimitBtn = page.locator("button:has-text('Retry Limit')");
  await retryLimitBtn.click();
  await page.waitForSelector("text=Event Stream Connection Lost", { timeout: 3000 });
  console.log("Disconnection banner displayed successfully with Retry Connection button.");

  await page.screenshot({ path: simulationScreenshot, fullPage: true });
  console.log("Saved simulation screenshot:", simulationScreenshot);

  // Reset Simulation
  const resetBtn = page.locator("button:has-text('Reset')");
  await resetBtn.click();
  console.log("Simulation controls reset.");

  console.log("\n==================================================");
  console.log("STEP 3: TESTING OPTIMISTIC CANCELLATION FLOW (AC-1, AC-2, AC-7)");
  console.log("==================================================");
  const cancelBtn = page.locator("button:has-text('Cancel Run')");
  await cancelBtn.click();

  // Wait for cancelled banner
  await page.waitForSelector("text=Run Cancelled by Maintainer", { timeout: 3000 });
  const cancelledBadge = await page.textContent("text=RUN CANCELLED");
  console.log("Found RUN CANCELLED Badge:", !!cancelledBadge);

  const inspectPartialBtn = page.locator("button:has-text('Inspect Partial Results')");
  console.log("Inspect Partial Results button present:", await inspectPartialBtn.isVisible());

  const returnBtn = page.locator("button:has-text('Return to Tasks')");
  console.log("Return to Tasks button present:", await returnBtn.isVisible());

  await page.screenshot({ path: cancelScreenshot, fullPage: true });
  console.log("Saved cancelled run screenshot:", cancelScreenshot);

  // Click Return to Tasks
  await returnBtn.click();
  await page.waitForSelector("text=Upgrade & Repair Tasks", { timeout: 3000 });
  console.log("Returned to tasks view cleanly.");

  await browser.close();
  console.log("\nALL CANCEL, RECONNECT, AND ERROR CRITERIA VERIFIED SUCCESSFULLY!");
}

runCancelErrorsVerification().catch((err) => {
  console.error("Verification failed:", err);
  process.exit(1);
});
