"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  FolderGit2,
  CheckCircle2,
  AlertTriangle,
  FileCode,
  ShieldCheck,
  ArrowRight,
  Terminal,
  Download,
  Lock,
} from "lucide-react";
import { RepairBenchScene } from "@/components/repair-bench-scene";

interface HomeViewProps {
  onConfigureRepo?: () => void;
  onViewSavedRun?: (runId: string) => void;
  onSelectDemoTasks?: () => void;
}

export function HomeView({
  onConfigureRepo,
  onViewSavedRun,
  onSelectDemoTasks,
}: HomeViewProps) {
  const router = useRouter();

  const handleOpenSavedDemo = () => {
    if (onViewSavedRun) {
      onViewSavedRun("run_a72af9a70dbc47ee9ba7c7b8b6ff1226");
    } else {
      router.push("/?runId=run_a72af9a70dbc47ee9ba7c7b8b6ff1226");
    }
  };

  const handleConfigure = () => {
    if (onConfigureRepo) {
      onConfigureRepo();
    } else {
      router.push("/?tab=custom_repo");
    }
  };

  const handleDemoTasks = () => {
    if (onSelectDemoTasks) {
      onSelectDemoTasks();
    } else {
      router.push("/?tab=tasks");
    }
  };

  return (
    <div
      className="relative w-full min-h-screen text-[#F7F7F2] overflow-hidden"
      data-testid="home-view"
      style={{
        backgroundColor: "#060908",
        backgroundImage: `
          /* Layer 1: Starlit Abyss scattered celestial stars */
          radial-gradient(circle at 10% 16%, rgba(255, 255, 255, 0.85) 1px, transparent 3px),
          radial-gradient(circle at 86% 12%, rgba(183, 201, 173, 0.9) 1.5px, transparent 4px),
          radial-gradient(circle at 92% 44%, rgba(255, 255, 255, 0.7) 1px, transparent 3px),
          radial-gradient(circle at 22% 64%, rgba(95, 203, 138, 0.95) 1.5px, transparent 4px),
          radial-gradient(circle at 6% 48%, rgba(255, 255, 255, 0.6) 1px, transparent 3px),
          radial-gradient(circle at 64% 8%, rgba(127, 179, 213, 0.85) 1px, transparent 3px),
          radial-gradient(circle at 44% 86%, rgba(255, 255, 255, 0.7) 1px, transparent 3px),
          radial-gradient(circle at 76% 74%, rgba(183, 201, 173, 0.8) 1.5px, transparent 4px),

          /* Layer 2: Nebula Celestial Cyan glow (upper-left aura) */
          radial-gradient(circle at 16% 20%, rgba(56, 189, 248, 0.15) 0%, transparent 45%),

          /* Layer 3: Starlit Abyss Deep Indigo underglow (bottom ambient core) */
          radial-gradient(ellipse at 50% 112%, rgba(79, 70, 229, 0.32) 0%, rgba(49, 46, 129, 0.12) 55%, transparent 80%),

          /* Layer 4: Aurora Emerald ambient glow around hero bench */
          radial-gradient(ellipse at 78% 32%, rgba(95, 203, 138, 0.18) 0%, rgba(27, 50, 40, 0.08) 55%, transparent 75%),

          /* Layer 5: Deep void into forest gradient */
          linear-gradient(180deg, #060908 0%, #0A1410 40%, #0D1C16 75%, #060908 100%)
        `,
      }}
    >
      {/* ------------------------------------------------------------- */}
      {/* SECTION 1: HERO (SPLIT LAYOUT AT DESKTOP)                     */}
      {/* ------------------------------------------------------------- */}
      <section
        aria-label="Hero overview"
        className="mx-auto w-full max-w-[1280px] px-4 sm:px-6 pt-10 pb-16 sm:pt-16 sm:pb-20"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          {/* Left Column: Direct Copy, Primary Actions, Disclaimers */}
          <div className="lg:col-span-6 space-y-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-[rgba(183,201,173,0.22)] bg-[#15271F]/70 px-3 py-1 backdrop-blur-md">
              <span className="size-2 rounded-full bg-[#5FCB8A] animate-pulse" />
              <span className="font-mono text-[11px] font-semibold tracking-wider uppercase text-[#B7C9AD]">
                AUTOMATED DEPENDENCY REPAIR
              </span>
              <span className="text-[10px] text-[#A9B8AD]">·</span>
              <span className="font-mono text-[10px] text-[#5FCB8A] font-medium">
                CONTROLLED SPEC
              </span>
            </div>

            <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-[52px] font-semibold tracking-tight text-[#F7F7F2] leading-[1.12]">
              See what breaks.
              <br />
              <span className="bg-gradient-to-r from-[#B7C9AD] via-[#5FCB8A] to-[#7FB3D5] bg-clip-text text-transparent">
                Review what fixes it.
              </span>
            </h1>

            <p className="text-base sm:text-lg text-[#A9B8AD] leading-relaxed max-w-xl">
              Reproduce a dependency upgrade failure, inspect a candidate patch,
              and review the verification evidence.
            </p>

            {/* Clear Primary & Secondary Actions */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Button
                type="button"
                onClick={handleOpenSavedDemo}
                data-testid="hero-btn-view-demo"
                className="h-11 sm:h-12 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-sm px-6 rounded-lg flex items-center gap-2 transition-all cursor-pointer shadow-lg shadow-[#5FCB8A]/10 hover:shadow-[#5FCB8A]/20 focus-visible:ring-2 focus-visible:ring-[#B7C9AD]"
              >
                <CheckCircle2 className="size-4 text-[#102D25]" />
                View saved demo
              </Button>

              <Button
                type="button"
                variant="outline"
                onClick={handleConfigure}
                data-testid="hero-btn-configure-repo"
                className="h-11 sm:h-12 border-[rgba(183,201,173,0.3)] bg-[#15271F]/70 hover:bg-[#1B3228] text-[#F7F7F2] text-sm px-6 rounded-lg flex items-center gap-2 transition-all cursor-pointer backdrop-blur-md focus-visible:ring-2 focus-visible:ring-[#B7C9AD]"
              >
                <FolderGit2 className="size-4 text-[#A9B8AD]" />
                Configure a repository
              </Button>
            </div>

            {/* Truthful Limitation Notice */}
            <div className="pt-2">
              <div className="rounded-lg border border-[rgba(183,201,173,0.18)] bg-[#0A1410]/80 p-3 backdrop-blur-sm">
                <p className="text-xs text-[#A9B8AD] flex items-center gap-2 leading-relaxed">
                  <Lock className="size-3.5 text-[#E0B45A] shrink-0" />
                  <span>
                    Custom repository execution is currently disabled. Active runs are restricted to controlled demo tasks.
                  </span>
                </p>
              </div>
            </div>
          </div>

          {/* Right Column: Spatial 2.5D Repair Bench Scene */}
          <div className="lg:col-span-6 w-full">
            <RepairBenchScene />
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* SECTION 2: THE PROBLEM (BREAKING UPGRADES EXCERPT)            */}
      {/* ------------------------------------------------------------- */}
      <section
        id="the-problem"
        aria-label="The dependency upgrade problem"
        className="w-full border-y border-[rgba(183,201,173,0.14)] bg-[#0C1612]/75 backdrop-blur-md py-14 sm:py-20"
      >
        <div className="mx-auto max-w-[1280px] px-4 sm:px-6">
          <div className="max-w-3xl mb-8">
            <span className="font-mono text-xs font-semibold tracking-wider uppercase text-[#B7C9AD]">
              THE BOTTLENECK
            </span>
            <h2 className="mt-2 text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-[#F7F7F2]">
              The silent break in dependency upgrades
            </h2>
            <p className="mt-3 text-sm sm:text-base text-[#A9B8AD] leading-relaxed">
              When a library bumps a major version, code that compiled cleanly yesterday crashes today.
              Subtle API removals, renamed keyword parameters, and altered return shapes break CI test suites.
              Developers spend hours digging through migration notes to fix small syntactical mismatches.
            </p>
          </div>

          {/* Code & Error Excerpt Card */}
          <Card className="rounded-2xl border border-[rgba(183,201,173,0.2)] bg-[#08100C]/90 overflow-hidden shadow-2xl backdrop-blur-md">
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-6 py-3.5 border-b border-[rgba(183,201,173,0.12)] bg-[#12221B]/80">
              <div className="flex items-center gap-2">
                <Terminal className="size-4 text-[#5FCB8A]" />
                <span className="font-mono text-xs font-medium text-[#F7F7F2]">
                  sqlalchemy 1.4 → 2.0.19 breaking change
                </span>
              </div>
              <Badge
                variant="outline"
                className="font-mono text-[10px] text-[#A9B8AD] border-[rgba(183,201,173,0.25)] bg-[#15271F]/50"
              >
                Example excerpt (sanitized fixture)
              </Badge>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-[rgba(183,201,173,0.12)]">
              {/* Baseline passing code */}
              <div className="p-5 font-mono text-xs space-y-3">
                <div className="flex items-center justify-between text-[#A9B8AD] text-[11px] pb-1.5 border-b border-[rgba(183,201,173,0.08)]">
                  <span className="text-[#5FCB8A] font-semibold">1. Baseline (sqlalchemy 1.4.48) — PASS</span>
                  <span>src/shop/database.py</span>
                </div>
                <pre className="text-[#F7F7F2] overflow-x-auto leading-relaxed py-1">
                  <code>{`# Legacy SQLAlchemy 1.4 execution syntax
engine = create_engine(DATABASE_URL)

def get_active_orders():
    # Direct string execution allowed in 1.4
    result = engine.execute("SELECT id, total FROM orders")
    return [dict(row) for row in result]`}</code>
                </pre>
                <div className="text-[11px] text-[#5FCB8A] bg-[#5FCB8A]/10 border border-[#5FCB8A]/20 rounded-md px-3 py-1.5 flex items-center gap-2">
                  <CheckCircle2 className="size-3.5 shrink-0" />
                  <span>pytest: 1 passed in 0.12s (Baseline verified)</span>
                </div>
              </div>

              {/* Upgraded failing traceback */}
              <div className="p-5 font-mono text-xs space-y-3 bg-[#1A0D0D]/40">
                <div className="flex items-center justify-between text-[#A9B8AD] text-[11px] pb-1.5 border-b border-[rgba(229,115,106,0.15)]">
                  <span className="text-[#E5736A] font-semibold">2. Target Upgrade (sqlalchemy 2.0.19) — FAIL</span>
                  <span>pytest traceback</span>
                </div>
                <pre className="text-[#E5736A] overflow-x-auto leading-relaxed py-1">
                  <code>{`Traceback (most recent call last):
  File "src/shop/database.py", line 6, in get_active_orders
    result = engine.execute("SELECT id, total FROM orders")
AttributeError: 'Engine' object has no attribute 'execute'

# In 2.0, explicit connection context and text() required`}</code>
                </pre>
                <div className="text-[11px] text-[#E5736A] bg-[#E5736A]/10 border border-[#E5736A]/20 rounded-md px-3 py-1.5 flex items-center gap-2">
                  <AlertTriangle className="size-3.5 shrink-0" />
                  <span>FAILED tests/test_orders.py::test_database_connection</span>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* SECTION 3: HOW REPOMEDIC WORKS (4-STEP PROGRESSION)           */}
      {/* ------------------------------------------------------------- */}
      <section
        id="how-it-works"
        aria-label="How RepoMedic works"
        className="mx-auto w-full max-w-[1280px] px-4 sm:px-6 py-14 sm:py-20"
      >
        <div className="max-w-3xl mb-10">
          <span className="font-mono text-xs font-semibold tracking-wider uppercase text-[#B7C9AD]">
            THE PROCESS
          </span>
          <h2 className="mt-2 text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-[#F7F7F2]">
            How RepoMedic resolves breaking upgrades
          </h2>
          <p className="mt-3 text-sm sm:text-base text-[#A9B8AD] leading-relaxed">
            A disciplined four-stage pipeline isolates the upgrade, tests the failure,
            generates a candidate patch, and proves the fix in a sandbox.
          </p>
        </div>

        {/* 4 Sequential Stages Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Step 1 */}
          <div className="rounded-2xl border border-[rgba(183,201,173,0.16)] bg-[#12221B]/70 p-5 flex flex-col justify-between backdrop-blur-md hover:border-[rgba(183,201,173,0.3)] transition-colors">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="size-8 rounded-lg bg-[#1B3228] border border-[rgba(183,201,173,0.25)] text-xs font-mono font-bold flex items-center justify-center text-[#B7C9AD]">
                  01
                </span>
                <span className="text-[11px] font-mono text-[#5FCB8A] font-medium">PASS CHECK</span>
              </div>
              <h3 className="text-base font-semibold text-[#F7F7F2] mb-2">
                1. Baseline Check
              </h3>
              <p className="text-xs text-[#A9B8AD] leading-relaxed">
                Pins the exact repository commit and runs existing test suites in a clean container to prove the baseline was green before any version bump.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-[rgba(183,201,173,0.1)] text-[11px] font-mono text-[#A9B8AD]">
              Input: Pinned commit SHA
            </div>
          </div>

          {/* Step 2 */}
          <div className="rounded-2xl border border-[rgba(183,201,173,0.16)] bg-[#12221B]/70 p-5 flex flex-col justify-between backdrop-blur-md hover:border-[#E5736A]/40 transition-colors">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="size-8 rounded-lg bg-[#2E1B1B] border border-[#E5736A]/35 text-xs font-mono font-bold flex items-center justify-center text-[#E5736A]">
                  02
                </span>
                <span className="text-[11px] font-mono text-[#E5736A] font-medium">REPRODUCE</span>
              </div>
              <h3 className="text-base font-semibold text-[#F7F7F2] mb-2">
                2. Reproduce Failure
              </h3>
              <p className="text-xs text-[#A9B8AD] leading-relaxed">
                Upgrades target dependency in isolation. Extracts full pytest output and stack trace to verify the exact failure matches expectations.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-[rgba(183,201,173,0.1)] text-[11px] font-mono text-[#A9B8AD]">
              Output: Sanitized trace
            </div>
          </div>

          {/* Step 3 */}
          <div className="rounded-2xl border border-[rgba(183,201,173,0.16)] bg-[#12221B]/70 p-5 flex flex-col justify-between backdrop-blur-md hover:border-[#E0B45A]/40 transition-colors">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="size-8 rounded-lg bg-[#1B3228] border border-[rgba(183,201,173,0.25)] text-xs font-mono font-bold flex items-center justify-center text-[#B7C9AD]">
                  03
                </span>
                <span className="text-[11px] font-mono text-[#E0B45A] font-medium">SYNTHESIS</span>
              </div>
              <h3 className="text-base font-semibold text-[#F7F7F2] mb-2">
                3. Candidate Patch
              </h3>
              <p className="text-xs text-[#A9B8AD] leading-relaxed">
                Model analyzes failure and AST constraints to propose candidate source edits. Test files are never modified.
              </p>
              <div className="mt-2.5 text-[11px] text-[#E0B45A] bg-[#E0B45A]/10 border border-[#E0B45A]/20 rounded p-2 leading-snug">
                Note: A model-generated patch is a candidate; verification may fail.
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-[rgba(183,201,173,0.1)] text-[11px] font-mono text-[#A9B8AD]">
              Output: Unified diff patch
            </div>
          </div>

          {/* Step 4 */}
          <div className="rounded-2xl border border-[rgba(183,201,173,0.16)] bg-[#12221B]/70 p-5 flex flex-col justify-between backdrop-blur-md hover:border-[#5FCB8A]/40 transition-colors">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="size-8 rounded-lg bg-[#1B3228] border border-[#5FCB8A]/35 text-xs font-mono font-bold flex items-center justify-center text-[#5FCB8A]">
                  04
                </span>
                <span className="text-[11px] font-mono text-[#5FCB8A] font-medium">VERIFIED</span>
              </div>
              <h3 className="text-base font-semibold text-[#F7F7F2] mb-2">
                4. Verify &amp; Evidence
              </h3>
              <p className="text-xs text-[#A9B8AD] leading-relaxed">
                Evaluates candidate in clean sandbox against the full test suite. Generates downloadable patch, execution logs, and cryptographic evidence.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-[rgba(183,201,173,0.1)] text-[11px] font-mono text-[#A9B8AD]">
              Evidence: SHA256 &amp; JSON
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* SECTION 4: INSIDE THE WORKFLOW (PRODUCT PREVIEW)              */}
      {/* ------------------------------------------------------------- */}
      <section
        id="product-preview"
        aria-label="Inside the workflow preview"
        className="w-full border-y border-[rgba(183,201,173,0.14)] bg-[#0C1612]/75 backdrop-blur-md py-14 sm:py-20"
      >
        <div className="mx-auto max-w-[1280px] px-4 sm:px-6">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8">
            <div className="max-w-2xl">
              <span className="font-mono text-xs font-semibold tracking-wider uppercase text-[#B7C9AD]">
                PRODUCT PREVIEW
              </span>
              <h2 className="mt-2 text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-[#F7F7F2]">
                Reviewable patches and verifiable evidence
              </h2>
              <p className="mt-2 text-sm sm:text-base text-[#A9B8AD] leading-relaxed">
                RepoMedic produces verifiable evidence artifacts: exact git diffs, execution timings,
                AST integrity checks, and full container logs.
              </p>
            </div>

            <Button
              type="button"
              onClick={handleOpenSavedDemo}
              className="h-10 border border-[rgba(183,201,173,0.32)] bg-[#1B3228] hover:bg-[#223E32] text-[#F7F7F2] text-xs sm:text-sm px-4 rounded-lg flex items-center gap-2 transition-colors cursor-pointer shrink-0 shadow-sm"
            >
              <span>Inspect saved run in product</span>
              <ArrowRight className="size-3.5 text-[#5FCB8A]" />
            </Button>
          </div>

          {/* Semantic UI Preview Card */}
          <div className="rounded-2xl border border-[rgba(183,201,173,0.2)] bg-[#08100C]/90 p-5 sm:p-7 shadow-2xl backdrop-blur-md">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-5 border-b border-[rgba(183,201,173,0.12)]">
              <div className="flex items-center gap-3">
                <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-mono text-xs px-2.5 py-0.5">
                  VERIFIED · 42/42 PASS
                </Badge>
                <span className="font-semibold text-sm sm:text-base text-[#F7F7F2]">
                  TASK-084 · pydantic v1.10.8 → v2.0.2 migration in fastapi-service
                </span>
              </div>
              <span className="text-[11px] font-mono text-[#A9B8AD]">
                Illustrative product preview
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-6">
              {/* Diff Viewer Excerpt */}
              <div className="lg:col-span-8 rounded-xl bg-[#12221B]/90 border border-[rgba(183,201,173,0.14)] p-4 font-mono text-xs space-y-2">
                <div className="flex items-center justify-between text-[#A9B8AD] text-[11px] pb-2 border-b border-[rgba(183,201,173,0.08)]">
                  <span>Candidate Patch · src/app/schemas.py</span>
                  <span className="text-[#5FCB8A]">+3 additions, -2 deletions</span>
                </div>
                <pre className="text-xs leading-relaxed overflow-x-auto py-2">
                  <code>
                    <span className="text-[#A9B8AD]">@@ -3,9 +3,8 @@</span>{"\n"}
                    <span className="text-[#E5736A]">-from pydantic import BaseModel, Field</span>{"\n"}
                    <span className="text-[#5FCB8A]">+from pydantic import BaseModel, Field, ConfigDict</span>{"\n"}
                    <span className="text-[#A9B8AD]"> class AccountPayload(BaseModel):</span>{"\n"}
                    <span className="text-[#A9B8AD]">     account_id: str</span>{"\n"}
                    <span className="text-[#E5736A]">-    tenant_slug: str = Field(..., regex=&quot;^[a-zA-Z0-9]+$&quot;)</span>{"\n"}
                    <span className="text-[#5FCB8A]">+    tenant_slug: str = Field(..., pattern=&quot;^[a-zA-Z0-9]+$&quot;)</span>{"\n"}
                    <span className="text-[#A9B8AD]">     is_active: bool = True</span>{"\n"}
                    <span className="text-[#E5736A]">-    class Config:</span>{"\n"}
                    <span className="text-[#E5736A]">-        orm_mode = True</span>{"\n"}
                    <span className="text-[#5FCB8A]">+    model_config = ConfigDict(from_attributes=True)</span>
                  </code>
                </pre>
              </div>

              {/* Evidence Metrics Summary */}
              <div className="lg:col-span-4 rounded-xl bg-[#12221B]/90 border border-[rgba(183,201,173,0.14)] p-4 flex flex-col justify-between space-y-4">
                <div>
                  <span className="text-xs font-mono font-semibold uppercase text-[#A9B8AD] tracking-wider block mb-3">
                    Verification Telemetry
                  </span>
                  <div className="space-y-2.5 text-xs font-mono">
                    <div className="flex items-center justify-between">
                      <span className="text-[#A9B8AD]">Tests verified:</span>
                      <span className="text-[#5FCB8A] font-semibold">42 / 42 passed (100%)</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#A9B8AD]">Execution time:</span>
                      <span className="text-[#F7F7F2]">24.2s</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#A9B8AD]">AST hash:</span>
                      <span className="text-[#7FB3D5] text-[11px] truncate max-w-[130px]">
                        sha256:d8a261...
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#A9B8AD]">Estimated usage:</span>
                      <span className="text-[#F7F7F2]">$0.04 USD</span>
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-[rgba(183,201,173,0.1)] space-y-2">
                  <span className="text-[11px] font-mono text-[#A9B8AD] block">
                    Downloadable Artifacts:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="outline" className="text-[10px] font-mono border-[rgba(183,201,173,0.2)] bg-[#1B3228]">
                      repomedic-fix.patch
                    </Badge>
                    <Badge variant="outline" className="text-[10px] font-mono border-[rgba(183,201,173,0.2)] bg-[#1B3228]">
                      verification-evidence.json
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* SECTION 5: EVIDENCE & LIMITATIONS (HONEST PRODUCT TRUTH)       */}
      {/* ------------------------------------------------------------- */}
      <section
        id="evidence-and-limitations"
        aria-label="Evidence and limitations"
        className="mx-auto w-full max-w-[1280px] px-4 sm:px-6 py-14 sm:py-20"
      >
        <div className="max-w-3xl mb-8">
          <span className="font-mono text-xs font-semibold tracking-wider uppercase text-[#B7C9AD]">
            PRODUCT INTEGRITY
          </span>
          <h2 className="mt-2 text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-[#F7F7F2]">
            Evidence, scope, and engineering limitations
          </h2>
          <p className="mt-3 text-sm sm:text-base text-[#A9B8AD] leading-relaxed">
            We prioritize technical transparency over exaggerated claims.
            Here is what RepoMedic can and cannot do in this release.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-2xl border border-[rgba(183,201,173,0.16)] bg-[#12221B]/70 p-5 space-y-2 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <Download className="size-4 text-[#5FCB8A]" />
              <h3 className="text-sm font-semibold text-[#F7F7F2]">
                Downloadable Artifacts
              </h3>
            </div>
            <p className="text-xs text-[#A9B8AD] leading-relaxed">
              Every verified repair emits the exact candidate patch diff, full pytest execution logs,
              and machine-readable JSON evidence with AST integrity signatures.
            </p>
          </div>

          <div className="rounded-2xl border border-[rgba(183,201,173,0.16)] bg-[#12221B]/70 p-5 space-y-2 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-[#E0B45A]" />
              <h3 className="text-sm font-semibold text-[#F7F7F2]">
                Controlled Fixture Scope
              </h3>
            </div>
            <p className="text-xs text-[#A9B8AD] leading-relaxed">
              Demonstrated successes are controlled fixtures (demo-shop has 1 test; pydantic has 42 tests).
              Controlled demo success does not establish arbitrary repository reliability.
            </p>
          </div>

          <div className="rounded-2xl border border-[rgba(183,201,173,0.16)] bg-[#12221B]/70 p-5 space-y-2 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <FileCode className="size-4 text-[#7FB3D5]" />
              <h3 className="text-sm font-semibold text-[#F7F7F2]">
                Developer Review Required
              </h3>
            </div>
            <p className="text-xs text-[#A9B8AD] leading-relaxed">
              Candidate patches are synthesized for developer review, not autonomous blind merges.
              A human engineer must inspect the candidate diff before committing to production.
            </p>
          </div>

          <div className="rounded-2xl border border-[rgba(183,201,173,0.16)] bg-[#12221B]/70 p-5 space-y-2 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <Lock className="size-4 text-[#E5736A]" />
              <h3 className="text-sm font-semibold text-[#F7F7F2]">
                Server-Side Execution Gating
              </h3>
            </div>
            <p className="text-xs text-[#A9B8AD] leading-relaxed">
              Custom repository execution is disabled server-side to protect system stability.
              Custom configurations can be validated locally for format and contract rules.
            </p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* SECTION 6: FINAL ACTION & CTA                                  */}
      {/* ------------------------------------------------------------- */}
      <section
        aria-label="Final action"
        className="mx-auto w-full max-w-[1280px] px-4 sm:px-6 py-16 sm:py-24 text-center border-t border-[rgba(183,201,173,0.14)]"
      >
        <div className="max-w-2xl mx-auto space-y-5">
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-[#F7F7F2]">
            Inspect a verified repair or explore repository recipes
          </h2>
          <p className="text-sm sm:text-base text-[#A9B8AD] leading-relaxed">
            Open our saved live run to view diffs, execution traces, and cryptographic evidence,
            or validate a custom repository configuration.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3 pt-3">
            <Button
              type="button"
              onClick={handleOpenSavedDemo}
              data-testid="final-btn-view-demo"
              className="h-11 sm:h-12 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-sm px-6 rounded-lg flex items-center gap-2 transition-all cursor-pointer shadow-lg shadow-[#5FCB8A]/10 hover:shadow-[#5FCB8A]/20 focus-visible:ring-2 focus-visible:ring-[#B7C9AD]"
            >
              <CheckCircle2 className="size-4 text-[#102D25]" />
              View saved demo
            </Button>

            <Button
              type="button"
              variant="outline"
              onClick={handleConfigure}
              data-testid="final-btn-configure-repo"
              className="h-11 sm:h-12 border-[rgba(183,201,173,0.32)] bg-[#15271F]/80 hover:bg-[#1B3228] text-[#F7F7F2] text-sm px-6 rounded-lg flex items-center gap-2 transition-all cursor-pointer backdrop-blur-md focus-visible:ring-2 focus-visible:ring-[#B7C9AD]"
            >
              <FolderGit2 className="size-4 text-[#A9B8AD]" />
              Configure a repository
            </Button>

            <Button
              type="button"
              variant="ghost"
              onClick={handleDemoTasks}
              data-testid="final-btn-demo-tasks"
              className="h-11 sm:h-12 text-[#A9B8AD] hover:text-[#F7F7F2] hover:bg-[#1B3228]/60 text-sm px-5 rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <span>Explore demo tasks</span>
              <ArrowRight className="size-3.5 text-[#A9B8AD]" />
            </Button>
          </div>

          <p className="pt-2 text-xs text-[#A9B8AD]">
            Controlled demo scenarios are available. Custom execution is gated.
          </p>
        </div>
      </section>
    </div>
  );
}