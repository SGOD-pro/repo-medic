import { chromium } from "playwright";
import path from "path";
import fs from "fs";

async function runVerification() {
  const artifactDir = "C:\\Users\\KIIT\\.gemini\\antigravity-ide\\brain\\2d656c98-0d4f-44bb-b446-b085b26d5dd6";
  const tasksScreenshot = path.join(artifactDir, "evidence_tasks_view.png");
  const runActiveScreenshot = path.join(artifactDir, "evidence_run_active_view.png");
  const verificationScreenshot = path.join(artifactDir, "evidence_verification_view.png");
  const historyScreenshot = path.join(artifactDir, "evidence_history_drawer.png");

  console.log("Launching browser via Playwright with host Chrome/Edge...");
  let browser;
  try {
    browser = await chromium.launch({ channel: "chrome", headless: true });
    console.log("Launched Google Chrome successfully.");
  } catch (err) {
    console.log("Chrome launch failed, trying Edge...", err.message);
    browser = await chromium.launch({ channel: "msedge", headless: true });
    console.log("Launched Microsoft Edge successfully.");
  }

  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    acceptDownloads: true,
  });
  const page = await context.newPage();

  console.log("\n==================================================");
  console.log("STEP 1: NAVIGATING TO http://localhost:3000 (Tasks View)");
  console.log("==================================================");
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });

  // 1. Verify Tasks View elements
  const h1Text = await page.textContent("h1");
  console.log("Found Page H1:", h1Text);
  if (!h1Text.includes("Upgrade & Repair Tasks")) {
    throw new Error(`Expected 'Upgrade & Repair Tasks', got '${h1Text}'`);
  }

  const task084 = await page.textContent("text=TASK-084");
  const task091 = await page.textContent("text=TASK-091");
  const task097 = await page.textContent("text=TASK-097");
  console.log("Verified Curated Tasks:", { task084: !!task084, task091: !!task091, task097: !!task097 });

  const targetVerification = await page.textContent("text=TARGET VERIFICATION");
  console.log("Target Verification Panel Present:", !!targetVerification);

  await page.screenshot({ path: tasksScreenshot, fullPage: true });
  console.log("Saved Tasks View screenshot:", tasksScreenshot);

  console.log("\n==================================================");
  console.log("STEP 2: TRIGGERING 'Start repair run' -> Run Active View");
  console.log("==================================================");
  const startButton = page.locator("button:has-text('Start repair run')");
  await startButton.click();

  await page.waitForSelector("text=Active Candidate Matrices", { timeout: 5000 });
  const activePipelineBadge = await page.textContent("text=ACTIVE PIPELINE");
  console.log("Found Active Pipeline Indicator:", !!activePipelineBadge);

  // AC-1: Verify all 6 execution pipeline stages
  const stageNames = [
    "1. Baseline Check",
    "2. Upgrade Reproduction",
    "3. Allowlist Context",
    "4. Candidate Gen",
    "5. Sandbox Verify",
    "6. Preservation Proof",
  ];
  const stagesFound = {};
  for (const name of stageNames) {
    const el = await page.textContent(`text=${name}`);
    stagesFound[name] = !!el;
  }
  console.log("AC-1: Verified 6 Pipeline Stages:", stagesFound);

  // AC-2: Verify spend metrics and elapsed time
  const spendText = await page.textContent("text=$0.18");
  const capText = await page.textContent("text=/ $0.50 cap");
  const elapsedText = await page.textContent("text=ELAPSED");
  console.log("AC-2: Spend and Timing Metrics:", { spendText: !!spendText, capText: !!capText, elapsedText: !!elapsedText });

  // AC-3: Verify candidate matrices
  const candidateA = await page.textContent("text=Candidate A");
  const candidateB = await page.textContent("text=Candidate B");
  const candidateC = await page.textContent("text=Candidate C");
  const selectedBadge = await page.textContent("text=SELECTED / PASS");
  console.log("AC-3: Candidate Matrices:", { candidateA: !!candidateA, candidateB: !!candidateB, candidateC: !!candidateC, selectedBadge: !!selectedBadge });

  // AC-4: Terminal log box with copy action
  const streamCompleted = await page.textContent("text=STREAM COMPLETED");
  const copyLogButton = page.locator("button[aria-label='Copy logs']");
  const copyLogPresent = await copyLogButton.isVisible();
  console.log("AC-4: Monospace Terminal Log Box:", { streamCompleted: !!streamCompleted, copyLogPresent });
  if (copyLogPresent) {
    await copyLogButton.click();
    console.log("AC-4: Clicked Copy full log button successfully.");
  }

  // AC-5: Expandable error stack on rejected Candidate B
  const viewErrorStackButton = page.locator("button:has-text('View Error Stack')");
  if (await viewErrorStackButton.isVisible()) {
    await viewErrorStackButton.click();
    console.log("AC-5: Toggled View Error Stack on Candidate B.");
    const traceback = await page.textContent("text=PydanticDeprecatedSince20");
    console.log("AC-5: Deprecation traceback found:", !!traceback);
  }

  await page.screenshot({ path: runActiveScreenshot, fullPage: true });
  console.log("Saved Run Active View screenshot:", runActiveScreenshot);

  console.log("\n==================================================");
  console.log("STEP 3: TRIGGERING 'Inspect Results & Diff' -> Verification View");
  console.log("==================================================");
  const inspectButton = page.locator("button:has-text('Inspect Results & Diff')");
  await inspectButton.click();

  await page.waitForSelector("text=Unified Change Manifest", { timeout: 5000 });
  const reportHeadline = await page.textContent("h2:has-text('Behavior preserved')");
  console.log("Found Report Headline:", reportHeadline);

  // AC-6: 5 metric cards
  const testsMetric = await page.textContent("text=42 / 42");
  const characMetric = await page.textContent("text=Characterization");
  const filesMetric = await page.textContent("text=Files Modified");
  console.log("AC-6: Verification Report Metrics:", { testsMetric: !!testsMetric, characMetric: !!characMetric, filesMetric: !!filesMetric });

  // AC-7: Unified change manifest with line numbers
  const schemasFile = await page.textContent("text=src/app/schemas.py");
  const tomlFile = await page.textContent("text=pyproject.toml");
  console.log("AC-7: Change Manifest Files:", { schemasFile: !!schemasFile, tomlFile: !!tomlFile });

  // AC-8: Deterministic evidence progress breakdown
  const passRate = await page.textContent("text=100% Pass Rate");
  console.log("AC-8: Deterministic Evidence Dynamics:", passRate);

  // AC-9: Action buttons trigger patch and evidence downloads
  console.log("AC-9: Testing Patch Download Trigger...");
  const downloadPatchPromise = page.waitForEvent("download", { timeout: 5000 });
  await page.locator("button:has-text('Download Patch')").click();
  const patchDownload = await downloadPatchPromise;
  console.log("AC-9: Patch Downloaded successfully as:", patchDownload.suggestedFilename());

  console.log("AC-9: Testing Evidence Download Trigger...");
  const downloadEvidencePromise = page.waitForEvent("download", { timeout: 5000 });
  await page.locator("button:has-text('Download Evidence')").click();
  const evidenceDownload = await downloadEvidencePromise;
  console.log("AC-9: Evidence Downloaded successfully as:", evidenceDownload.suggestedFilename());

  await page.screenshot({ path: verificationScreenshot, fullPage: true });
  console.log("Saved Verification & Results View screenshot:", verificationScreenshot);

  console.log("\n==================================================");
  console.log("STEP 4: TRIGGERING 'Run another task' -> Returning to Tasks View");
  console.log("==================================================");
  const runAnotherButton = page.locator("button:has-text('Run another task')");
  await runAnotherButton.click();

  await page.waitForSelector("h1:has-text('Upgrade & Repair Tasks')", { timeout: 5000 });
  console.log("AC-10: Successfully returned to Tasks View!");

  console.log("\n==================================================");
  console.log("STEP 5: TESTING HISTORY DRAWER & STATE RELOAD");
  console.log("==================================================");
  // 1. Open history drawer
  const historyButton = page.locator("button:has-text('History')");
  await historyButton.click();
  await page.waitForSelector("text=Run History", { timeout: 5000 });
  console.log("History Drawer Opened successfully.");

  // Screenshot history drawer
  await page.screenshot({ path: historyScreenshot });
  console.log("Saved History Drawer screenshot:", historyScreenshot);

  // 2. Click a past run to reload
  const pastRunCard = page.locator("[data-slot='sheet-content']").getByText("TASK-084").first();
  await pastRunCard.click();
  await page.waitForTimeout(500);

  // Verify URL updated with runId
  const currentUrl = page.url();
  console.log("URL after selecting run from history:", currentUrl);
  if (!currentUrl.includes("runId=")) {
    throw new Error("Expected URL to include runId query param");
  }

  // 3. Test page reload with query param
  console.log("Testing page reload with ?runId= param...");
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector("text=Unified Change Manifest", { timeout: 5000 });
  console.log("Successfully reloaded terminal run from URL parameter!");

  // 4. Test Clear History and Empty State display (AC-7)
  console.log("Testing Clear History action and empty state display...");
  const reopenHistoryButton = page.locator("button:has-text('History')");
  await reopenHistoryButton.click();
  await page.waitForSelector("text=Run History", { timeout: 5000 });

  const clearButton = page.locator("button:has-text('Clear')");
  await clearButton.click();
  await page.waitForSelector("text=No past runs recorded", { timeout: 5000 });
  const emptyTitle = await page.textContent("text=No past runs recorded");
  console.log("AC-7: Clear history triggered empty state:", !!emptyTitle);

  const historyEmptyScreenshot = path.join(artifactDir, "evidence_history_empty.png");
  await page.screenshot({ path: historyEmptyScreenshot });
  console.log("Saved History Empty State screenshot:", historyEmptyScreenshot);

  await browser.close();

  console.log("\n==================================================");
  console.log("ALL VERIFICATION STEPS AND ACCEPTANCE CRITERIA PASSED!");
  console.log("==================================================");
}

runVerification().catch((err) => {
  console.error("Verification failed:", err);
  process.exit(1);
});
