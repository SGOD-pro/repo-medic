import { chromium } from "playwright";

async function runAudit() {
  const consoleMessages = [];
  const pageErrors = [];

  console.log("Launching browser to audit console warnings and edge cases...");
  let browser;
  try {
    browser = await chromium.launch({ channel: "chrome", headless: true });
  } catch (err) {
    browser = await chromium.launch({ channel: "msedge", headless: true });
  }

  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    permissions: ["clipboard-read", "clipboard-write"],
  });
  const page = await context.newPage();

  page.on("console", (msg) => {
    const type = msg.type();
    const text = msg.text();
    // Ignore normal Next.js Turbopack dev logs
    if (text.includes("[Fast Refresh]") || text.includes("Download the React DevTools")) {
      return;
    }
    if (type === "error" || type === "warning") {
      consoleMessages.push({ type, text, location: msg.location() });
    }
  });

  page.on("pageerror", (err) => {
    pageErrors.push(err.message);
  });

  console.log("Navigating to http://localhost:3000 to check initial load & hydration...");
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });

  // 1. Audit Task Switching
  console.log("Auditing task selection switching...");
  const task091 = page.locator("text=TASK-091");
  await task091.click();
  await page.waitForTimeout(300);

  const task097 = page.locator("text=TASK-097");
  await task097.click();
  await page.waitForTimeout(300);

  const task084 = page.locator("text=TASK-084");
  await task084.click();
  await page.waitForTimeout(300);

  // 2. Start repair run -> RunActiveView
  console.log("Auditing active pipeline run view...");
  await page.locator("button:has-text('Start repair run')").click();
  await page.waitForSelector("text=Active Candidate Matrices", { timeout: 5000 });

  // Copy log audit
  const copyButton = page.locator("button[aria-label='Copy logs']");
  if (await copyButton.isVisible()) {
    await copyButton.click();
    await page.waitForTimeout(200);
  }

  // Candidate B traceback expand and collapse
  const tracebackButton = page.locator("button:has-text('View Error Stack')");
  if (await tracebackButton.isVisible()) {
    await tracebackButton.click();
    await page.waitForTimeout(200);
    // Collapse again
    await tracebackButton.click();
    await page.waitForTimeout(200);
  }

  // 3. Inspect Results & Diff -> VerificationView
  console.log("Auditing verification view and diff folding...");
  await page.locator("button:has-text('Inspect Results & Diff')").click();
  await page.waitForSelector("text=Unified Change Manifest", { timeout: 5000 });

  // Test collapsible file headers in Change Manifest
  const schemasCollapse = page.locator("button:has-text('src/app/schemas.py')");
  if (await schemasCollapse.isVisible()) {
    // Collapse
    await schemasCollapse.click();
    await page.waitForTimeout(200);
    // Expand
    await schemasCollapse.click();
    await page.waitForTimeout(200);
  }

  // 4. Test Cancel / Reset flow
  console.log("Auditing return to tasks view...");
  await page.locator("button:has-text('Run another task')").click();
  await page.waitForSelector("h1:has-text('Upgrade & Repair Tasks')", { timeout: 5000 });

  // 5. Audit Cancel Run during active run
  console.log("Auditing cancel run action during active pipeline...");
  await page.locator("button:has-text('Start repair run')").click();
  await page.waitForSelector("button:has-text('Cancel Run')", { timeout: 5000 });
  await page.locator("button:has-text('Cancel Run')").click();
  await page.waitForTimeout(500);

  await browser.close();

  console.log("\n================ AUDIT SUMMARY ================");
  console.log("Page Errors Count:", pageErrors.length);
  if (pageErrors.length > 0) {
    console.log("Page Errors:", pageErrors);
  }
  console.log("Console Warnings/Errors Count:", consoleMessages.length);
  if (consoleMessages.length > 0) {
    console.log("Console Warnings/Errors:", consoleMessages);
  }
  console.log("===============================================");
}

runAudit().catch((err) => {
  console.error("Audit script failed:", err);
  process.exit(1);
});
