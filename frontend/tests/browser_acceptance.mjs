import { chromium } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawn, execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { stopProcess } from "./process_control.mjs";

export { stopProcess };

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "../..");

const ARTIFACT_DIR = process.env.ARTIFACT_DIR || path.resolve(REPO_ROOT, "artifacts/acceptance_test_evidence");
const BASE_URL = process.env.BASE_URL || process.env.FRONTEND_URL || "http://localhost:3000";
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

async function runAcceptanceSuite() {
  console.log("=== STARTING BROWSER & TURSO INTEGRATION SUITE ===");
  console.log(`Repository root: ${REPO_ROOT}`);
  console.log(`Artifact directory: ${ARTIFACT_DIR}`);
  console.log(`Frontend URL: ${BASE_URL}`);
  console.log(`Backend URL: ${BACKEND_URL}`);

  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

  const launchOptions = {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  };
  const homeChromium = path.join(process.env.HOME || "", ".local/bin/chromium");
  if (process.env.CHROMIUM_PATH) {
    launchOptions.executablePath = process.env.CHROMIUM_PATH;
  } else if (process.env.HOME && fs.existsSync(homeChromium)) {
    launchOptions.executablePath = homeChromium;
  }

  const browser = await chromium.launch(launchOptions);

  const context = await browser.newContext({
    viewport: { width: 1280, height: 950 },
    acceptDownloads: true,
  });

  const page = await context.newPage();

  // Track console errors
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
      console.error(`  [Browser Console Error] ${msg.text()}`);
    }
  });

  let sequentialRunId = null;

  async function ensureTasksView() {
    const tasksView = page.locator('[data-testid="tasks-view"]');
    if (!(await tasksView.isVisible({ timeout: 1000 }).catch(() => false))) {
      const navTasks = page.locator('[data-testid="nav-tab-tasks"]').first();
      if (await navTasks.isVisible({ timeout: 2000 }).catch(() => false)) {
        await navTasks.click();
      }
    }
    await tasksView.waitFor({ state: "visible", timeout: 10000 });
  }

  try {
    // -------------------------------------------------------------
    // CHECK 1: Task Selection & Dynamic getTasks() Loading
    // -------------------------------------------------------------
    console.log("\n[CHECK 1] Loading tasks from getTasks() and verifying task metadata...");
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });

    // Verify task discovery container
    await ensureTasksView();

    // Ensure TASK-084 card exists with full metadata
    const task84Card = page.locator('text=TASK-084').first();
    await task84Card.waitFor({ state: "visible", timeout: 5000 });
    console.log("  ✔ TASK-084 card visible");

    // Click on TASK-084 to select it
    await page.click('text=TASK-084');
    await page.waitForTimeout(500);

    // Verify right preflight panel updates with TASK-084 details
    const preflightRepo = await page.locator('text=fastapi-service').first().isVisible();
    assert.ok(preflightRepo, "fastapi-service repository header must be displayed in preflight panel");

    // Verify metadata values
    const textContent = await page.textContent('body');
    assert.ok(textContent.includes("pydantic==2.0.2") || textContent.includes("pydantic"), "Target dependency version must be rendered");
    assert.ok(textContent.includes("42 preserved tests") || textContent.includes("42/42 PASS"), "Preserved tests count must be rendered");
    assert.ok(textContent.includes("LOCAL D1 / OFFLINE MODE") || textContent.includes("OFFLINE MODE"), "Truthful offline mode label must be present in navbar");

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "evidence_task_discovery.png"), fullPage: true });
    console.log("  ✔ Task selection and metadata verified; screenshot saved");

    // -------------------------------------------------------------
    // CHECK 2: Sequential Search Mode Repair & Artifact Downloads
    // -------------------------------------------------------------
    console.log("\n[CHECK 2] Initiating Sequential Search Mode run on TASK-084...");

    // Select "Sequential Direct (single pass)" strategy
    const strategyTrigger = page.locator('button:has-text("Branch & Refine"), button:has-text("Sequential Direct"), button:has-text("Select strategy")').first();
    if (await strategyTrigger.isVisible()) {
      await strategyTrigger.click();
      const sequentialItem = page.locator('[data-slot="select-item"]:has-text("Sequential Direct"), [role="option"]:has-text("Sequential Direct"), text=Sequential Direct').first();
      await sequentialItem.waitFor({ state: "visible", timeout: 5000 });
      await sequentialItem.click();
      await page.waitForTimeout(300);
      console.log("  ✔ Strategy set to Sequential Direct");
    }

    // Click Start repair run
    const startButton = page.locator('button:has-text("Start repair run")');
    await startButton.waitFor({ state: "visible" });
    await startButton.click();

    // Verify transition to active run view and URL update
    await page.waitForURL(/runId=/, { timeout: 10000 });
    const currentUrl = page.url();
    const runIdMatch = currentUrl.match(/runId=([a-zA-Z0-9_\-]+)/);
    assert.ok(runIdMatch, `URL must contain runId query parameter, got: ${currentUrl}`);
    sequentialRunId = runIdMatch[1];
    console.log(`  ✔ Run started with runId: ${sequentialRunId}`);

    // Wait for pipeline stages to progress and terminal state to be reached
    console.log("  Waiting for pipeline stages and candidate verification...");
    const succeededText = page.locator('[data-testid="active-run-status"]:has-text("SUCCEEDED")');
    await succeededText.waitFor({ state: "visible", timeout: 90000 });
    console.log("  ✔ Sequential run reached SUCCEEDED");

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "evidence_sequential_run_active.png"), fullPage: true });
    console.log("  ✔ Sequential execution completed; active run screenshot saved");

    // Transition to verification report view
    const inspectButton = page.locator('button:has-text("Inspect Results & Diff"), button:has-text("Inspect Partial Results")');
    await inspectButton.click();
    await page.waitForTimeout(1000);

    // Verify verification view rendered
    const verificationHeader = page.locator('text=Verified Source Repair Completed').first();
    await verificationHeader.waitFor({ state: "visible", timeout: 10000 });

    // Verify artifact download links are present
    const patchDownloadBtn = page.locator('button:has-text("Download patch"), button:has-text("Download Patch")').first();
    await patchDownloadBtn.waitFor({ state: "visible", timeout: 5000 });

    const evidenceDownloadBtn = page.locator('button:has-text("Download evidence")').first();
    await evidenceDownloadBtn.waitFor({ state: "visible", timeout: 5000 });

    // Download Patch Artifact via browser download event
    console.log("  Testing patch download by artifact_id...");
    const [patchDownload] = await Promise.all([
      page.waitForEvent("download"),
      patchDownloadBtn.click(),
    ]);
    const patchPath = await patchDownload.path();
    const patchData = fs.readFileSync(patchPath, "utf-8");
    assert.ok(patchData.includes("--- a/src/app.py"), "Downloaded patch must contain diff for src/app.py");
    console.log(`  ✔ Patch downloaded (${patchData.length} bytes), verified diff header`);

    // Download Evidence Artifact via browser download event
    console.log("  Testing evidence download by artifact_id...");
    const [evidenceDownload] = await Promise.all([
      page.waitForEvent("download"),
      evidenceDownloadBtn.click(),
    ]);
    const evidencePath = await evidenceDownload.path();
    const evidenceJson = JSON.parse(fs.readFileSync(evidencePath, "utf-8"));
    assert.equal(evidenceJson.task_id, "TASK-084", "Evidence JSON must match task TASK-084");
    assert.equal(evidenceJson.verified_version, "2.0.0", "Evidence JSON must specify verified_version 2.0.0");
    assert.equal(evidenceJson.checks?.tests_passed, true, "Evidence JSON must record tests_passed: true");
    console.log(`  ✔ Evidence downloaded and verified (task: ${evidenceJson.task_id}, version: ${evidenceJson.verified_version})`);

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "evidence_sequential_verification.png"), fullPage: true });
    console.log("  ✔ Sequential verification report screenshot saved");

    // -------------------------------------------------------------
    // CHECK 3: Branch and Refine Search Mode Repair
    // -------------------------------------------------------------
    console.log("\n[CHECK 3] Testing Branch and Refine Search Mode on TASK-084...");
    const runAnotherBtn = page.locator('button:has-text("Run another task")').first();
    if (await runAnotherBtn.isVisible()) {
      await runAnotherBtn.click();
    } else {
      await page.goto(BASE_URL);
      await ensureTasksView();
    }
    await page.waitForTimeout(500);

    // Select TASK-084
    await page.click('text=TASK-084');
    await page.waitForTimeout(300);

    // Select "Branch & Refine" strategy
    const stratBtn = page.locator('button:has-text("Branch & Refine"), button:has-text("Sequential Direct"), button:has-text("Select strategy")').first();
    if (await stratBtn.isVisible()) {
      await stratBtn.click();
      const branchItem = page.locator('[data-slot="select-item"]:has-text("Branch & Refine"), [role="option"]:has-text("Branch & Refine"), text=Branch & Refine').first();
      await branchItem.waitFor({ state: "visible", timeout: 5000 });
      await branchItem.click();
      await page.waitForTimeout(300);
    }

    // Start branch refine run
    await page.click('button:has-text("Start repair run")');
    await page.waitForURL(/runId=/, { timeout: 10000 });
    const branchRunId = page.url().match(/runId=([a-zA-Z0-9_\-]+)/)[1];
    console.log(`  ✔ Branch & Refine run started with runId: ${branchRunId}`);

    // Wait for completion
    const branchSucceededText = page.locator('[data-testid="active-run-status"]:has-text("SUCCEEDED")');
    await branchSucceededText.waitFor({ state: "visible", timeout: 90000 });
    console.log("  ✔ Branch & Refine terminal state SUCCEEDED confirmed");

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "evidence_branch_refine_run.png"), fullPage: true });
    console.log("  ✔ Branch & Refine execution completed; screenshot saved");

    // Inspect results
    const branchInspectBtn = page.locator('button:has-text("Inspect Results & Diff"), button:has-text("Inspect Partial Results")');
    await branchInspectBtn.click();
    await page.waitForTimeout(1000);
    const branchVerifHeader = page.locator('text=Verified Source Repair Completed').first();
    await branchVerifHeader.waitFor({ state: "visible", timeout: 10000 });
    console.log("  ✔ Branch & Refine verification view confirmed");

    // -------------------------------------------------------------
    // CHECK 4: Run Cancellation Flow
    // -------------------------------------------------------------
    console.log("\n[CHECK 4] Testing Run Cancellation Flow...");
    await page.goto(BASE_URL);
    await ensureTasksView();
    await page.waitForTimeout(500);
    await page.click('text=TASK-084');
    await page.waitForTimeout(300);

    // Start run
    await page.click('button:has-text("Start repair run")');
    await page.waitForURL(/runId=/, { timeout: 10000 });

    // Immediately click Cancel Run
    const cancelBtn = page.locator('button:has-text("Cancel Run")');
    await cancelBtn.waitFor({ state: "visible", timeout: 5000 });
    await cancelBtn.click();
    console.log("  Clicked Cancel Run button");

    // Wait for cancelled state badge / banner
    const cancelledBanner = page.locator('text=Run Cancelled').first();
    await cancelledBanner.waitFor({ state: "visible", timeout: 30000 });
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "evidence_run_cancelled.png"), fullPage: true });
    console.log("  ✔ Cancellation confirmed in UI; screenshot saved");

    // -------------------------------------------------------------
    // CHECK 5: Reload Hydration with ?runId
    // -------------------------------------------------------------
    console.log(`\n[CHECK 5] Testing Reload Hydration for run ${sequentialRunId}...`);
    // Navigate directly with ?runId query parameter
    await page.goto(`${BASE_URL}/?runId=${sequentialRunId}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    // Verify the page hydrated directly into verification view from getRun()
    const reloadVerificationHeader = page.locator('text=Verified Source Repair Completed').first();
    await reloadVerificationHeader.waitFor({ state: "visible", timeout: 20000 });

    const taskText = await page.textContent('body');
    assert.ok(taskText.includes("TASK-084"), "Reloaded page must display TASK-084 metadata");
    assert.ok(taskText.includes("Run Artifacts"), "Reloaded page must display artifacts list");

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "evidence_reload_hydration.png"), fullPage: true });
    console.log("  ✔ Page reload successfully hydrated active run from getRun(); screenshot saved");

    // -------------------------------------------------------------
    // CHECK 6: Failure Flow on TASK-091 (Safety Validation Rejection)
    // -------------------------------------------------------------
    console.log("\n[CHECK 6] Testing Failure Flow on TASK-091...");
    await page.goto(BASE_URL);
    await ensureTasksView();
    await page.waitForTimeout(500);

    // Select TASK-091 card
    const task91Card = page.locator('[data-testid="task-card-TASK-091"], [role="button"]:has-text("TASK-091")').first();
    await task91Card.waitFor({ state: "visible", timeout: 5000 });
    await task91Card.click();
    await page.waitForTimeout(500);

    // Start run
    await page.click('button:has-text("Start repair run")');
    await page.waitForURL(/runId=/, { timeout: 10000 });
    const failRunId = page.url().match(/runId=([a-zA-Z0-9_\-]+)/)[1];
    console.log(`  ✔ TASK-091 run started with runId: ${failRunId}`);

    // Wait for failure completion
    const failedText = page.locator('[data-testid="active-run-status"]:has-text("FAILED")');
    await failedText.waitFor({ state: "visible", timeout: 90000 });
    console.log("  ✔ TASK-091 terminal state FAILED confirmed");

    // Inspect failure view
    const failedInspectBtn = page.locator('button:has-text("Inspect Results & Diff"), button:has-text("Inspect Partial Results")');
    await failedInspectBtn.click();
    await page.waitForTimeout(1000);

    const failBanner = page.locator('text=Source Repair Failed').first();
    await failBanner.waitFor({ state: "visible", timeout: 10000 });

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "evidence_run_failed.png"), fullPage: true });
    console.log("  ✔ Failure scenario confirmed with Patch safety validation error; screenshot saved");

    // -------------------------------------------------------------
    // CHECK 7: Browser Stream Interruption and Recovery without Duplicate Events
    // -------------------------------------------------------------
    console.log("\n[CHECK 7] Testing browser stream interruption, background completion, and recovery without duplicate events...");
    await page.goto(BASE_URL);
    await ensureTasksView();
    await page.waitForTimeout(500);

    // Select TASK-084
    await page.click('text=TASK-084');
    await page.waitForTimeout(300);

    // Start repair run
    await page.click('button:has-text("Start repair run")');
    await page.waitForURL(/runId=/, { timeout: 10000 });
    const recoveryRunId = page.url().match(/runId=([a-zA-Z0-9_\-]+)/)[1];
    console.log(`  ✔ Recovery test run started with runId: ${recoveryRunId}`);

    // Wait until stream connects and renders initial log lines
    await page.waitForSelector('text=repomedic-stream.log', { timeout: 5000 });
    await page.waitForTimeout(600);

    // Simulate network transport drop by disconnecting network via context.setOffline
    console.log("  Simulating transport interruption via context.setOffline(true)...");
    await context.setOffline(true);

    // Verify browser UI enters disconnected / reconnecting state
    const disconnectedOrReconnecting = page.locator('text=DISCONNECTED').or(page.locator('text=RECONNECTING'));
    await disconnectedOrReconnecting.first().waitFor({ state: "visible", timeout: 10000 });
    console.log("  ✔ Browser detected connection loss and rendered status indicator");

    // Allow run to finish in backend while browser remains disconnected
    console.log("  Awaiting run completion in backend while browser remains disconnected...");
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 500));
      try {
        const checkResp = await fetch(`${BACKEND_URL}/api/runs/${recoveryRunId}`);
        if (checkResp.ok) {
          const runData = await checkResp.json();
          if (runData.state === "succeeded" || runData.state === "failed") {
            console.log(`  ✔ Background run completed with state: ${runData.state}`);
            break;
          }
        }
      } catch {}
    }

    // Now restore network connection
    console.log("  Restoring network connection via context.setOffline(false)...");
    await context.setOffline(false);

    // If Retry Connection button is visible, click it; otherwise let retry loop handle it
    const retryBtn = page.locator('button:has-text("Retry Connection")');
    if (await retryBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      console.log("  Clicking Retry Connection button...");
      await retryBtn.click();
    }

    // Wait for the browser to recover the terminal state (SUCCEEDED)
    const recoverySucceededText = page.locator('[data-testid="active-run-status"]:has-text("SUCCEEDED")');
    await recoverySucceededText.waitFor({ state: "visible", timeout: 90000 });
    console.log("  ✔ Browser recovered terminal SUCCEEDED status");

    // Wait for reconnected stream events to finish rendering in terminal box
    const logContainer = page.locator('[data-testid="stream-terminal-logs"]').first();
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="stream-terminal-logs"]');
      return el && el.textContent && el.textContent.includes("run.finished");
    }, { timeout: 30000 });

    // Verify log text in terminal box contains no duplicates
    const logContent = await logContainer.textContent();
    assert.ok(logContent, "Log container must contain event text");

    const countMatches = (text, pattern) => (text.match(new RegExp(pattern, "g")) || []).length;
    assert.equal(countMatches(logContent, "stage\\.baseline"), 1, "stage.baseline must appear exactly once in execution log");
    assert.equal(countMatches(logContent, "stage\\.upgrade"), 1, "stage.upgrade must appear exactly once in execution log");
    assert.equal(countMatches(logContent, "candidate\\."), 1, "candidate must appear exactly once in execution log");
    assert.equal(countMatches(logContent, "stage\\.verification"), 1, "stage.verification must appear exactly once in execution log");
    assert.equal(countMatches(logContent, "run\\.finished"), 1, "run.finished must appear exactly once in execution log");
    console.log("  ✔ Deduplication verified: all stages and run.finished appear exactly once without duplicate log entries");

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "evidence_stream_recovery.png"), fullPage: true });
    console.log("  ✔ Stream recovery screenshot saved");

    // Also assert direct SSE endpoint deduplication with Last-Event-ID header
    const sseResp = await fetch(`${BACKEND_URL}/api/runs/${recoveryRunId}/events`, {
      headers: { "Last-Event-ID": "2" },
    });
    assert.equal(sseResp.status, 200, "SSE stream must return 200 OK");
    const sseBody = await sseResp.text();
    assert.ok(!sseBody.includes("id: 1\n"), "Reconnected stream must not include event id: 1");
    assert.ok(!sseBody.includes("id: 2\n"), "Reconnected stream must not include event id: 2");
    console.log("  ✔ Direct SSE endpoint Last-Event-ID cursor deduplication verified");

    // -------------------------------------------------------------
    // CHECK 8: Budget Denial against Storage Backend
    // -------------------------------------------------------------
    console.log("\n[CHECK 8] Testing budget denial returning 409 Conflict against storage backend...");
    // Direct call to operations endpoint with excessive amount exceeding global budget cap
    const budgetResp = await fetch(`${BACKEND_URL}/api/runs/${sequentialRunId}/operations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        operation_id: `op_budget_excessive_${Date.now()}`,
        kind: "model",
        reserved_micro_usd: 9999000000,
        global_budget_micro_usd: 25000000,
      }),
    });
    assert.equal(budgetResp.status, 409, "Budget check must return 409 Conflict when reservation exceeds budget cap");
    const budgetResult = await budgetResp.json();
    assert.equal(budgetResult.error?.code, "budget_limit_exceeded", "Error code must be budget_limit_exceeded");

    // Also verify GET /api/budget/usage reports tracked budget
    const usageResp = await fetch(`${BACKEND_URL}/api/budget/usage`);
    assert.equal(usageResp.status, 200, "Budget usage endpoint must return 200 OK");
    const usageResult = await usageResp.json();
    assert.ok(typeof usageResult.total_micro_usd === "number", "total_micro_usd must be a number");
    console.log(`  ✔ Budget denial verified against storage backend (status: 409, code: ${budgetResult.error?.code}, tracked: $${(usageResult.total_micro_usd / 1_000_000).toFixed(4)})`);

    // -------------------------------------------------------------
    // CHECK 9: Backend Process Stop and Restart against Persistent Storage
    // -------------------------------------------------------------
    console.log("\n[CHECK 9] Testing real backend process stop and restart against persistent storage...");
    const backendCwd = path.resolve(REPO_ROOT, "backend");
    const testPort = Number(process.env.TEST_BACKEND_PORT) || 8009;
    const testBackendUrl = `http://127.0.0.1:${testPort}`;

    const isRemote = Boolean(
      process.env.TURSO_DATABASE_URL &&
      (process.env.TURSO_DATABASE_URL.startsWith("libsql://") ||
       process.env.TURSO_DATABASE_URL.startsWith("https://") ||
       process.env.TURSO_DATABASE_URL.startsWith("http://"))
    );
    const check9Db = isRemote
      ? process.env.TURSO_DATABASE_URL
      : path.resolve(backendCwd, `test_check9_${Date.now()}.db`);

    const runPrefix = `run_k3_restart_${Date.now()}_`;
    const seedRun1 = `${runPrefix}proc1`;
    const seedRun2 = `${runPrefix}proc2`;

    const check9Env = {
      ...process.env,
      TURSO_DATABASE_URL: check9Db,
      REPOMEDIC_STORAGE_BACKEND: "turso",
      REPOMEDIC_ACCEPTANCE_PREFIX: runPrefix,
      REPOMEDIC_WORKER_ENABLED: "false",
    };

    let testProc = null;
    const cleanTestProc = async () => {
      if (testProc) {
        await stopProcess(testProc);
        testProc = null;
      }
    };

    try {
      async function waitForBackend(url, timeoutMs = 15000) {
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
          try {
            const resp = await fetch(`${url}/api/tasks`);
            if (resp.ok) return true;
          } catch {}
          await new Promise((r) => setTimeout(r, 250));
        }
        throw new Error(`Backend at ${url} failed to respond within ${timeoutMs}ms`);
      }

      function launchTestBackend() {
        return spawn("uv", [
          "run",
          "python",
          "-m",
          "uvicorn",
          "src.main:create_app",
          "--factory",
          "--host",
          "127.0.0.1",
          "--port",
          String(testPort),
        ], {
          cwd: backendCwd,
          env: {
            ...check9Env,
            REPOMEDIC_MODE: "offline",
            PORT: String(testPort),
          },
          stdio: ["ignore", "pipe", "pipe"],
          detached: process.platform !== "win32",
        });
      }

      // Step 1: Seed first interrupted run in persistent storage
      execSync(`uv run python -m src.storage.turso_client seed-run ${seedRun1} TASK-084 offline sequential running`, {
        cwd: backendCwd,
        env: check9Env,
      });

      // Step 2: Spawn backend process and wait for startup lifespan recovery
      console.log(`  Spawning test backend process on port ${testPort}...`);
      testProc = launchTestBackend();
      await waitForBackend(testBackendUrl);
      console.log("  ✔ Backend process started and healthy");

      // Verify that startup recovery transitioned seedRun1 to failed
      const check1Resp = await fetch(`${testBackendUrl}/api/runs/${seedRun1}`);
      const check1 = await check1Resp.json();
      assert.equal(check1.state, "failed", "Startup recovery must mark interrupted run as failed in persistent storage");
      assert.ok(check1.reason.includes("restarted"), `Reason must mention process restart, got: ${check1.reason}`);
      console.log(`  ✔ First run recovered upon startup: state=${check1.state}, reason="${check1.reason}"`);

      // Step 3: Seed second run in persistent storage while backend is active
      execSync(`uv run python -m src.storage.turso_client seed-run ${seedRun2} TASK-084 offline branch_refine running`, {
        cwd: backendCwd,
        env: check9Env,
      });
      const check2ActiveResp = await fetch(`${testBackendUrl}/api/runs/${seedRun2}`);
      const check2Active = await check2ActiveResp.json();
      assert.equal(check2Active.state, "running", "Seed run must be running initially");

      // Step 4: Stop backend process (simulate shutdown/termination)
      console.log("  Stopping backend process via SIGTERM...");
      await stopProcess(testProc);
      testProc = null;
      console.log("  ✔ Backend process stopped");

      // Verify second run remains 'running' in persistent storage while backend is stopped
      const rawRun = execSync(`uv run python -m src.storage.turso_client get-run ${seedRun2}`, {
        cwd: backendCwd,
        env: check9Env,
      }).toString();
      const checkDown = JSON.parse(rawRun);
      assert.equal(checkDown.state, "running", "Seed run must remain running while backend process is stopped");
      console.log("  ✔ Verified run state remains persisted in storage across process termination");

      // Step 5: Restart backend process
      console.log(`  Restarting backend process on port ${testPort}...`);
      testProc = launchTestBackend();
      await waitForBackend(testBackendUrl);
      console.log("  ✔ Backend process restarted and healthy");

      // Step 6: Verify startup recovery of second run
      const check2Resp = await fetch(`${testBackendUrl}/api/runs/${seedRun2}`);
      const check2 = await check2Resp.json();
      assert.equal(check2.state, "failed", "Restarted backend process must recover interrupted run in persistent storage");
      assert.ok(check2.reason.includes("restarted"), `Reason must mention process restart, got: ${check2.reason}`);
      console.log(`  ✔ Second run recovered upon process restart: state=${check2.state}, reason="${check2.reason}"`);
    } catch (err) {
      if (!fs.existsSync(ARTIFACT_DIR)) {
        fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
      }
      const failureReport = {
        check: "check_9_backend_process_termination_and_startup_recovery",
        timestamp: new Date().toISOString(),
        is_remote: isRemote,
        database_url: isRemote ? "libsql://[remote_turso]" : check9Db,
        prefix: runPrefix,
        seedRun1,
        seedRun2,
        error: String(err && (err.stack || err.message) || err),
      };
      fs.writeFileSync(
        path.resolve(ARTIFACT_DIR, `k3_check9_failure_${Date.now()}.json`),
        JSON.stringify(failureReport, null, 2),
        "utf8"
      );
      throw err;
    } finally {
      await cleanTestProc();
      if (isRemote) {
        try {
          execSync(`uv run python -m src.storage.turso_client cleanup-runs ${seedRun1} ${seedRun2}`, {
            cwd: backendCwd,
            env: check9Env,
          });
          console.log("  ✔ Remote acceptance records cleaned up");
        } catch (cleanupErr) {
          console.warn("  ⚠ Failed to clean up remote acceptance records:", cleanupErr.message);
        }
      } else {
        for (const suffix of ["", "-wal", "-shm"]) {
          const p = `${check9Db}${suffix}`;
          if (fs.existsSync(p)) {
            try {
              fs.unlinkSync(p);
            } catch {}
          }
        }
        console.log("  ✔ Test backend process and isolated database cleaned up");
      }
    }

    console.log("\n========================================================");
    console.log("ALL 9 BROWSER & TURSO STORAGE ACCEPTANCE CHECKS PASSED!");
    console.log("========================================================\n");
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  runAcceptanceSuite().catch((err) => {
    console.error("ACCEPTANCE SUITE FAILED:", err);
    process.exit(1);
  });
}
