/* eslint-disable @typescript-eslint/no-explicit-any */
import { chromium } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "../..");
const SCREENSHOT_DIR = path.resolve(REPO_ROOT, "artifacts/landing_page_evidence");

async function main() {
  console.log("=== STARTING REPOMEDIC SEPARATE /home ROUTE PLAYWRIGHT SUITE ===");
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  // 1. Spawn next server
  console.log("Starting Next.js production server on port 3000...");
  const server = spawn("npx", ["next", "start", "-p", "3000"], {
    cwd: path.resolve(__dirname, ".."),
    stdio: "inherit",
    env: { ...process.env, PORT: "3000", NEXT_PUBLIC_API_TRANSPORT: "mock" },
  });

  const stopServer = () => {
    try {
      server.kill("SIGTERM");
    } catch {}
  };

  process.on("exit", stopServer);
  process.on("SIGINT", () => {
    stopServer();
    process.exit(1);
  });

  // Wait for server to become responsive
  const url = "http://localhost:3000";
  const homeUrl = `${url}/home`;
  let ready = false;
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) {
        ready = true;
        break;
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }

  if (!ready) {
    console.error("Server failed to respond on port 3000");
    stopServer();
    process.exit(1);
  }
  console.log("✔ Server is ready at http://localhost:3000\n");

  const launchOptions = {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  };
  const homeChromium = path.join(process.env.HOME || "", ".local/bin/chromium");
  if (process.env.CHROMIUM_PATH) {
    (launchOptions as any).executablePath = process.env.CHROMIUM_PATH;
  } else if (process.env.HOME && fs.existsSync(homeChromium)) {
    (launchOptions as any).executablePath = homeChromium;
  }

  const browser = await chromium.launch(launchOptions);

  try {
    // -------------------------------------------------------------
    // TEST 1: Dedicated /home Landing Page Route (1440x900)
    // -------------------------------------------------------------
    console.log("[TEST 1] Dedicated /home Landing Page - Starlit Abyss nebula atmosphere & layout");
    const desktopContext = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const homePage = await desktopContext.newPage();
    await homePage.goto(homeUrl, { waitUntil: "networkidle" });

    // Verify Home View is mounted on /home
    const homeView = homePage.locator('[data-testid="home-view"]');
    assert.ok(await homeView.isVisible(), "Dedicated /home page must render home-view");

    // Verify clean Landing Navbar
    const landingNavLaunch = homePage.locator('[data-testid="landing-nav-launch-app"]');
    assert.ok(await landingNavLaunch.isVisible(), "Landing navbar must have 'Open Workspace' button");

    const landingNavDemo = homePage.locator('[data-testid="landing-nav-view-demo"]');
    assert.ok(await landingNavDemo.isVisible(), "Landing navbar must have 'Saved Demo' button");
    console.log("  ✔ Clean landing navbar validated");

    // Verify Hero content
    const heroHeadline = await homePage.textContent("h1");
    assert.ok(heroHeadline?.includes("See what breaks."), "Hero headline must contain 'See what breaks.'");
    assert.ok(heroHeadline?.includes("Review what fixes it."), "Hero headline must contain 'Review what fixes it.'");
    console.log("  ✔ Hero headline validated");

    const heroCopy = await homePage.textContent('text="Reproduce a dependency upgrade failure, inspect a candidate patch, and review the verification evidence."');
    assert.ok(heroCopy, "Hero supporting copy must be visible");

    const disclaimer = await homePage.textContent('text="Custom repository execution is currently disabled. Active runs are restricted to controlled demo tasks."');
    assert.ok(disclaimer, "Hero disclaimer must be visible");
    console.log("  ✔ Truthful execution gate disclaimer validated");

    // Verify Spatial Repair Bench Scene
    const canvas = homePage.locator('canvas[role="img"]');
    assert.ok(await canvas.isVisible(), "Repair bench canvas must be visible on /home");

    const sequenceBadge = await homePage.textContent('text="Illustrative sequence"');
    assert.ok(sequenceBadge, "Illustrative sequence badge must be present");
    console.log("  ✔ Repair bench canvas and illustrative label validated");

    // Verify All 6 Sections on /home
    const problemHeading = await homePage.textContent('text="The silent break in dependency upgrades"');
    assert.ok(problemHeading, "The Problem section must be present");

    const worksHeading = await homePage.textContent('text="How RepoMedic resolves breaking upgrades"');
    assert.ok(worksHeading, "How it works section must be present");

    const previewHeading = await homePage.textContent('text="Reviewable patches and verifiable evidence"');
    assert.ok(previewHeading, "Product preview section must be present");

    const evidenceHeading = await homePage.textContent('text="Evidence, scope, and engineering limitations"');
    assert.ok(evidenceHeading, "Evidence and limitations section must be present");

    const finalCta = await homePage.textContent('text="Inspect a verified repair or explore repository recipes"');
    assert.ok(finalCta, "Final CTA section must be present");
    console.log("  ✔ All 6 page sections validated on /home");

    // Capture Desktop Screenshot
    const desktopShotPath = path.join(SCREENSHOT_DIR, "01_home_route_desktop_1440x900.png");
    await homePage.screenshot({ path: desktopShotPath, fullPage: true });
    console.log(`  ✔ Screenshot saved: ${desktopShotPath}`);

    // -------------------------------------------------------------
    // TEST 2: Interactive Scene Controls on /home
    // -------------------------------------------------------------
    console.log("\n[TEST 2] Testing Scene Controls on /home");
    const playPauseBtn = homePage.locator('[data-testid="btn-scene-play-pause"]');
    assert.ok(await playPauseBtn.isVisible(), "Play/Pause button must be visible");

    await playPauseBtn.click();
    await homePage.waitForTimeout(200);
    const playLabel = await playPauseBtn.getAttribute("aria-label");
    assert.equal(playLabel, "Play illustrative animation");
    console.log("  ✔ Pause toggled successfully");

    for (const step of [1, 2, 3, 4]) {
      const stepBtn = homePage.locator(`[data-testid="btn-scene-stage-${step}"]`);
      await stepBtn.click();
      await homePage.waitForTimeout(200);
      const isPressed = await stepBtn.getAttribute("aria-pressed");
      assert.equal(isPressed, "true");
      console.log(`  ✔ Stage ${step} selection verified (aria-pressed=true)`);
    }

    await playPauseBtn.click();

    // -------------------------------------------------------------
    // TEST 3: Workspace Header Cleanliness at /
    // -------------------------------------------------------------
    console.log("\n[TEST 3] Testing Clean Workspace Header at /");
    const workspacePage = await desktopContext.newPage();
    await workspacePage.goto(url, { waitUntil: "networkidle" });

    // Verify workspace header tabs: exactly 4 clean tabs, NO Overview or How it works clutter!
    const customRepoTab = workspacePage.locator('[data-testid="nav-tab-custom-repo"]');
    const tasksTab = workspacePage.locator('[data-testid="nav-tab-tasks"]');
    const runActiveTab = workspacePage.locator('[data-testid="nav-tab-run-active"]');
    const verificationTab = workspacePage.locator('[data-testid="nav-tab-verification"]');

    assert.ok(await customRepoTab.isVisible(), "Configure Repo tab must be visible");
    assert.ok(await tasksTab.isVisible(), "Demo Tasks tab must be visible");
    assert.ok(await runActiveTab.isVisible(), "Run Active tab must be visible");
    assert.ok(await verificationTab.isVisible(), "Verification tab must be visible");

    // Ensure no messy 'nav-tab-home' or 'nav-tab-how-it-works' in workspace tabs
    const overviewCount = await workspacePage.locator('[data-testid="nav-tab-home"]').count();
    const howCount = await workspacePage.locator('[data-testid="nav-tab-how-it-works"]').count();
    assert.equal(overviewCount, 0, "No 'Overview' tab clutter in workspace nav bar");
    assert.equal(howCount, 0, "No 'How it works' tab clutter in workspace nav bar");
    console.log("  ✔ Workspace header is clean and uncluttered with 4 focused tabs");

    // Capture Workspace Screenshot
    const workspaceShotPath = path.join(SCREENSHOT_DIR, "02_clean_workspace_header.png");
    await workspacePage.screenshot({ path: workspaceShotPath, fullPage: false });
    console.log(`  ✔ Clean workspace screenshot saved: ${workspaceShotPath}`);

    // -------------------------------------------------------------
    // TEST 4: Tablet Viewport on /home (768x1024)
    // -------------------------------------------------------------
    console.log("\n[TEST 4] Tablet Viewport on /home (768x1024)");
    const tabletContext = await browser.newContext({
      viewport: { width: 768, height: 1024 },
    });
    const tabletPage = await tabletContext.newPage();
    await tabletPage.goto(homeUrl, { waitUntil: "networkidle" });

    const tabletScrollWidth = await tabletPage.evaluate(() => document.documentElement.scrollWidth);
    const tabletClientWidth = await tabletPage.evaluate(() => document.documentElement.clientWidth);
    assert.ok(tabletScrollWidth <= tabletClientWidth + 1, "Tablet must not have horizontal scroll");

    const tabletShotPath = path.join(SCREENSHOT_DIR, "03_home_tablet_768x1024.png");
    await tabletPage.screenshot({ path: tabletShotPath, fullPage: true });
    console.log(`  ✔ Tablet screenshot saved: ${tabletShotPath}`);

    // -------------------------------------------------------------
    // TEST 5: Mobile Viewport on /home (375x812)
    // -------------------------------------------------------------
    console.log("\n[TEST 5] Mobile Viewport on /home (375x812)");
    const mobileContext = await browser.newContext({
      viewport: { width: 375, height: 812 },
    });
    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto(homeUrl, { waitUntil: "networkidle" });

    const mobileScrollWidth = await mobilePage.evaluate(() => document.documentElement.scrollWidth);
    const mobileClientWidth = await mobilePage.evaluate(() => document.documentElement.clientWidth);
    assert.ok(mobileScrollWidth <= mobileClientWidth + 1, "Mobile must not have horizontal scroll");

    const mobileShotPath = path.join(SCREENSHOT_DIR, "04_home_mobile_375x812.png");
    await mobilePage.screenshot({ path: mobileShotPath, fullPage: true });
    console.log(`  ✔ Mobile screenshot saved: ${mobileShotPath}`);

    // -------------------------------------------------------------
    // TEST 6: Narrow Mobile Viewport on /home (320px)
    // -------------------------------------------------------------
    console.log("\n[TEST 6] Narrow Mobile Viewport on /home (320px width)");
    const narrowContext = await browser.newContext({
      viewport: { width: 320, height: 640 },
    });
    const narrowPage = await narrowContext.newPage();
    await narrowPage.goto(homeUrl, { waitUntil: "networkidle" });

    const narrowScrollWidth = await narrowPage.evaluate(() => document.documentElement.scrollWidth);
    const narrowClientWidth = await narrowPage.evaluate(() => document.documentElement.clientWidth);
    assert.ok(narrowScrollWidth <= narrowClientWidth + 1, "Narrow mobile (320px) must not have horizontal scroll");

    const narrowShotPath = path.join(SCREENSHOT_DIR, "05_home_mobile_320px.png");
    await narrowPage.screenshot({ path: narrowShotPath, fullPage: true });
    console.log(`  ✔ Narrow mobile screenshot saved: ${narrowShotPath}`);

    // -------------------------------------------------------------
    // TEST 7: 200% Zoom / High-DPI Scaling on /home
    // -------------------------------------------------------------
    console.log("\n[TEST 7] 200% Zoom on /home");
    const zoomContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      deviceScaleFactor: 2,
    });
    const zoomPage = await zoomContext.newPage();
    await zoomPage.goto(homeUrl, { waitUntil: "networkidle" });
    await zoomPage.evaluate(() => {
      document.body.style.zoom = "200%";
    });
    await zoomPage.waitForTimeout(300);

    const zoomShotPath = path.join(SCREENSHOT_DIR, "06_home_zoom_200.png");
    await zoomPage.screenshot({ path: zoomShotPath, fullPage: true });
    console.log(`  ✔ 200% Zoom screenshot saved: ${zoomShotPath}`);

    // -------------------------------------------------------------
    // TEST 8: Prefers Reduced Motion on /home
    // -------------------------------------------------------------
    console.log("\n[TEST 8] Prefers Reduced Motion on /home");
    const motionContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      reducedMotion: "reduce",
    });
    const motionPage = await motionContext.newPage();
    await motionPage.goto(homeUrl, { waitUntil: "networkidle" });

    // Wait for hydration to settle prefers-reduced-motion initial pause
    await motionPage.waitForSelector(
      '[data-testid="btn-scene-play-pause"][aria-label="Play illustrative animation"]',
      { timeout: 5000 }
    );
    const motionPlayPause = motionPage.locator('[data-testid="btn-scene-play-pause"]');
    const motionLabel = await motionPlayPause.getAttribute("aria-label");
    assert.equal(motionLabel, "Play illustrative animation");
    console.log("  ✔ Reduced motion pauses scene animation by default");

    const motionShotPath = path.join(SCREENSHOT_DIR, "07_home_reduced_motion.png");
    await motionPage.screenshot({ path: motionShotPath, fullPage: true });
    console.log(`  ✔ Reduced motion screenshot saved: ${motionShotPath}`);

    // -------------------------------------------------------------
    // TEST 9: CTAs & Cross-Route Integration
    // -------------------------------------------------------------
    console.log("\n[TEST 9] Testing CTAs & Navigation from /home into /");
    const navTestPage = await desktopContext.newPage();
    await navTestPage.goto(homeUrl, { waitUntil: "networkidle" });

    // CTA 1: "Configure a repository" from /home goes to /?tab=custom_repo
    await navTestPage.click('[data-testid="hero-btn-configure-repo"]');
    await navTestPage.waitForSelector('[data-testid="custom-repo-form-view"]');
    console.log("  ✔ 'Configure a repository' on /home opened workspace custom repo view");

    // CTA 2: "View saved demo" from /home goes to retained production run
    await navTestPage.goto(homeUrl, { waitUntil: "networkidle" });
    await navTestPage.click('[data-testid="hero-btn-view-demo"]');
    await navTestPage.waitForTimeout(500);
    const runUrl = navTestPage.url();
    assert.ok(runUrl.includes("runId=run_a72af9a70dbc47ee9ba7c7b8b6ff1226"), "URL must contain ?runId=run_a72af9a70dbc47ee9ba7c7b8b6ff1226");
    console.log("  ✔ 'View saved demo' on /home navigated directly to saved demo");

    // CTA 3: "Open Workspace" in landing header goes to /
    await navTestPage.goto(homeUrl, { waitUntil: "networkidle" });
    await navTestPage.click('[data-testid="landing-nav-launch-app"]');
    await navTestPage.waitForSelector('[data-testid="nav-tab-custom-repo"]');
    console.log("  ✔ 'Open Workspace' in landing navbar navigated directly to workspace");

    console.log("\n========================================================");
    console.log("✔ ALL SEPARATE /home ROUTE TESTS PASSED SUCCESSFULLY!");
    console.log("========================================================");
  } finally {
    await browser.close();
    stopServer();
  }
}

main().catch((err) => {
  console.error("Test failed with error:", err);
  process.exit(1);
});
