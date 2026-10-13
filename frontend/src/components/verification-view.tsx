"use client";

import React, { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CheckCircle2,
  CheckCircle,
  FileCode,
  FileText,
  Clock,
  Cpu,
  ShieldCheck,
  Copy,
  Check,
  Download,
  RotateCcw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface VerificationViewProps {
  onRunAnotherTask: () => void;
}

export function VerificationView({ onRunAnotherTask }: VerificationViewProps) {
  const [collapsedFiles, setCollapsedFiles] = useState<Set<string>>(new Set());
  const [copiedPatch, setCopiedPatch] = useState(false);
  const [copiedSchemas, setCopiedSchemas] = useState(false);
  const [copiedToml, setCopiedToml] = useState(false);

  const toggleCollapseAll = () => {
    if (collapsedFiles.size > 0) {
      setCollapsedFiles(new Set());
    } else {
      setCollapsedFiles(new Set(["schemas", "toml"]));
    }
  };

  const downloadPatch = () => {
    const patchContent = `--- a/src/app/schemas.py
+++ b/src/app/schemas.py
@@ -3,9 +3,8 @@
-from pydantic import BaseModel, Field
+from pydantic import BaseModel, Field, ConfigDict
 
 class AccountPayload(BaseModel):
     account_id: str
-    tenant_slug: str = Field(..., regex="^[a-zA-Z0-9]+$")
+    tenant_slug: str = Field(..., pattern="^[a-zA-Z0-9]+$")
     is_active: bool = True
-    class Config:
-        orm_mode = True
+    model_config = ConfigDict(from_attributes=True)
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -20,2 +20,3 @@
-    "pydantic>=1.10.8,<2.0.0",
+    "pydantic>=2.0.2,<3.0.0",
+    "pydantic-settings>=2.0.0",
`;
    const blob = new Blob([patchContent], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "repomedic-fix.patch";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const downloadEvidence = () => {
    const evidenceData = {
      task_id: "TASK-084",
      status: "PASSED",
      ast_hash: "sha256:d8a261f9c09b8841a12e5661c478",
      tests_passed: 42,
      tests_failed: 0,
      execution_time: "24.2s",
      sandbox_id: "nb-sand-9941a",
      kernel: "Linux 6.2-cgroup2",
      contract_assertions: 2,
      model: "Nemotron-70B",
      cost_usd: 0.04,
    };
    const blob = new Blob([JSON.stringify(evidenceData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "verification-evidence.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="mx-auto w-full max-w-[1280px] px-6 py-8">
      {/* Top Banner Card: Verified Source Repair Completed */}
      <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.2)] p-6 mb-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="mt-0.5 rounded-full bg-[#5FCB8A]/20 p-1.5 border border-[#5FCB8A]/30">
              <CheckCircle className="size-5 text-[#5FCB8A]" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-xl font-semibold text-[#F7F7F2]">
                  Verified Source Repair Completed
                </h1>
                <Badge className="bg-[#5FCB8A]/20 text-[#5FCB8A] border-transparent font-mono text-xs font-semibold px-2 py-0.5">
                  PASS
                </Badge>
                <Badge
                  variant="outline"
                  className="border-[rgba(183,201,173,0.24)] bg-transparent font-mono text-[11px] text-[#A9B8AD] px-2 py-0.5"
                >
                  SHA 8A4F21D
                </Badge>
              </div>
              <p className="mt-1 text-xs text-[#A9B8AD]">
                pydantic v1.10.8 → v2.0.2 in{" "}
                <span className="font-mono text-[#F7F7F2]">
                  fastapi-service@8a4f21d
                </span>
                . Behavior preserved with fresh isolated test execution.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 font-mono text-xs text-[#5FCB8A] whitespace-nowrap">
            <span className="size-2 rounded-full bg-[#5FCB8A]" />
            <span>Sandbox Terminated Cleanly</span>
          </div>
        </div>
      </Card>

      {/* Verification Report Card */}
      <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-6 mb-8">
        <div className="flex items-center justify-between mb-2">
          <span className="font-mono text-xs tracking-wider text-[#A9B8AD] uppercase">
            VERIFICATION REPORT
          </span>
          <div className="flex items-center gap-2">
            <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-mono text-xs px-2 py-0.5">
              0 REGRESSIONS
            </Badge>
            <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-mono text-xs px-2 py-0.5">
              AST VERIFIED
            </Badge>
          </div>
        </div>

        <h2 className="text-2xl font-semibold text-[#F7F7F2] mb-6">
          Behavior preserved (42/42 tests passing)
        </h2>

        {/* 5 Metric Cards in a row */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {/* Metric 1 */}
          <div className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between">
            <span className="text-[11px] font-mono text-[#A9B8AD] mb-3">
              Tests Before/After
            </span>
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold text-[#5FCB8A]">
                42 / 42 pass
              </span>
              <CheckCircle2 className="size-4 text-[#5FCB8A]" />
            </div>
          </div>

          {/* Metric 2 */}
          <div className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between">
            <span className="text-[11px] font-mono text-[#A9B8AD] mb-3">
              Characterization Tests
            </span>
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold text-[#F7F7F2]">
                +2 generated
              </span>
              <FileCode className="size-4 text-[#A9B8AD]" />
            </div>
          </div>

          {/* Metric 3 */}
          <div className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between">
            <span className="text-[11px] font-mono text-[#A9B8AD] mb-3">
              Files Changed
            </span>
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold text-[#F7F7F2]">
                2 files (+18, -12)
              </span>
              <FileText className="size-4 text-[#A9B8AD]" />
            </div>
          </div>

          {/* Metric 4 */}
          <div className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between">
            <span className="text-[11px] font-mono text-[#A9B8AD] mb-3">
              Execution Time
            </span>
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold text-[#F7F7F2]">
                24.2s (isolated)
              </span>
              <Clock className="size-4 text-[#A9B8AD]" />
            </div>
          </div>

          {/* Metric 5 */}
          <div className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between col-span-2 md:col-span-1">
            <span className="text-[11px] font-mono text-[#A9B8AD] mb-3">
              Model &amp; Token Cost
            </span>
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold text-[#F7F7F2]">
                Nemotron-70B · $0.04
              </span>
              <Cpu className="size-4 text-[#A9B8AD]" />
            </div>
          </div>
        </div>

        {/* AST Proof Detail Bar */}
        <div className="rounded-xl bg-[#0D1915] border border-[rgba(183,201,173,0.12)] px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono text-[#A9B8AD]">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-[#5FCB8A] shrink-0" />
            <span>
              AST Proof: 0 test files modified · 0 skips/xfail introduced · Exact
              dependency <span className="text-[#F7F7F2]">pydantic==2.0.2</span>{" "}
              verified
            </span>
          </div>
          <div className="whitespace-nowrap">
            <span>Determinism: 100% · Seed: </span>
            <span className="text-[#F7F7F2]">#08291f</span>
          </div>
        </div>
      </Card>

      {/* Unified Change Manifest */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-baseline gap-2">
            <h3 className="text-lg font-semibold text-[#F7F7F2]">
              Unified Change Manifest
            </h3>
            <span className="text-xs text-[#A9B8AD]">2 files inspected</span>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="border-[rgba(183,201,173,0.2)] bg-[#15271F] text-xs text-[#F7F7F2] h-7 px-2.5 rounded-md"
            >
              Unified View
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleCollapseAll}
              className="text-xs text-[#A9B8AD] hover:text-[#F7F7F2] h-7 px-2"
            >
              {collapsedFiles.size > 0 ? "Expand All" : "Collapse All"}
            </Button>
          </div>
        </div>

        {/* Diff File 1: src/app/schemas.py */}
        <Card className="rounded-[16px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] overflow-hidden mb-4">
          <div className="flex items-center justify-between bg-[#1B3228] px-4 py-2.5 border-b border-[rgba(183,201,173,0.12)] font-mono text-xs">
            <div className="flex items-center gap-2">
              <FileCode className="size-4 text-[#A9B8AD]" />
              <span className="font-semibold text-[#F7F7F2]">
                src/app/schemas.py
              </span>
              <span className="text-[#A9B8AD] text-[11px] hidden sm:inline">
                fastapi-service/src/app/schemas.py
              </span>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 font-mono text-[11px]">
                <span className="text-[#5FCB8A] font-semibold">+14</span>
                <span className="text-[#E5736A] font-semibold">-10</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setCopiedSchemas(true);
                  setTimeout(() => setCopiedSchemas(false), 2000);
                }}
                className="text-[#A9B8AD] hover:text-[#F7F7F2] transition-colors p-1"
                title="Copy file diff"
              >
                {copiedSchemas ? (
                  <Check className="size-3.5 text-[#5FCB8A]" />
                ) : (
                  <Copy className="size-3.5" />
                )}
              </button>
            </div>
          </div>

          {!collapsedFiles.has("schemas") && (
            <div className="p-3 font-mono text-[12px] bg-[#0D1915] overflow-x-auto leading-relaxed">
              <table className="w-full border-collapse">
                <tbody>
                  <tr className="hover:bg-[#15271F]/50">
                    <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">1</td>
                    <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">1</td>
                    <td className="text-[#A9B8AD] pl-2">from typing import List, Optional, Dict, Any</td>
                  </tr>
                  <tr className="hover:bg-[#15271F]/50">
                    <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">2</td>
                    <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">2</td>
                    <td className="text-[#A9B8AD] pl-2">from datetime import datetime</td>
                  </tr>
                  <tr className="bg-[#E5736A]/10 text-[#E5736A]">
                    <td className="w-8 select-none text-right pr-3 text-[#E5736A]/60">3</td>
                    <td className="w-8 select-none text-right pr-4"></td>
                    <td className="pl-2">- from pydantic import BaseModel, Field</td>
                  </tr>
                  <tr className="bg-[#5FCB8A]/10 text-[#5FCB8A]">
                    <td className="w-8 select-none text-right pr-3"></td>
                    <td className="w-8 select-none text-right pr-4 text-[#5FCB8A]/60">3</td>
                    <td className="pl-2">+ from pydantic import BaseModel, Field, ConfigDict</td>
                  </tr>
                  <tr className="hover:bg-[#15271F]/50">
                    <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">4</td>
                    <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">4</td>
                    <td className="text-[#A9B8AD] pl-2"></td>
                  </tr>
                  <tr className="hover:bg-[#15271F]/50">
                    <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">5</td>
                    <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">5</td>
                    <td className="text-[#A9B8AD] pl-2">class AccountPayload(BaseModel):</td>
                  </tr>
                  <tr className="hover:bg-[#15271F]/50">
                    <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">6</td>
                    <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">6</td>
                    <td className="text-[#A9B8AD] pl-2">    account_id: str</td>
                  </tr>
                  <tr className="bg-[#E5736A]/10 text-[#E5736A]">
                    <td className="w-8 select-none text-right pr-3 text-[#E5736A]/60">7</td>
                    <td className="w-8 select-none text-right pr-4"></td>
                    <td className="pl-2">-     tenant_slug: str = Field(..., regex=&quot;^[a-zA-Z0-9]+$&quot;)</td>
                  </tr>
                  <tr className="bg-[#5FCB8A]/10 text-[#5FCB8A]">
                    <td className="w-8 select-none text-right pr-3"></td>
                    <td className="w-8 select-none text-right pr-4 text-[#5FCB8A]/60">7</td>
                    <td className="pl-2">+     tenant_slug: str = Field(..., pattern=&quot;^[a-zA-Z0-9]+$&quot;)</td>
                  </tr>
                  <tr className="hover:bg-[#15271F]/50">
                    <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">8</td>
                    <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">8</td>
                    <td className="text-[#A9B8AD] pl-2">    is_active: bool = True</td>
                  </tr>
                  <tr className="bg-[#E5736A]/10 text-[#E5736A]">
                    <td className="w-8 select-none text-right pr-3 text-[#E5736A]/60">9</td>
                    <td className="w-8 select-none text-right pr-4"></td>
                    <td className="pl-2">-     class Config:</td>
                  </tr>
                  <tr className="bg-[#E5736A]/10 text-[#E5736A]">
                    <td className="w-8 select-none text-right pr-3 text-[#E5736A]/60">10</td>
                    <td className="w-8 select-none text-right pr-4"></td>
                    <td className="pl-2">-         orm_mode = True</td>
                  </tr>
                  <tr className="bg-[#5FCB8A]/10 text-[#5FCB8A]">
                    <td className="w-8 select-none text-right pr-3"></td>
                    <td className="w-8 select-none text-right pr-4 text-[#5FCB8A]/60">9</td>
                    <td className="pl-2">+     model_config = ConfigDict(from_attributes=True)</td>
                  </tr>
                  <tr className="hover:bg-[#15271F]/50">
                    <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">11</td>
                    <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">10</td>
                    <td className="text-[#A9B8AD] pl-2"></td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Diff File 2: pyproject.toml */}
        <Card className="rounded-[16px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] overflow-hidden mb-6">
          <div className="flex items-center justify-between bg-[#1B3228] px-4 py-2.5 border-b border-[rgba(183,201,173,0.12)] font-mono text-xs">
            <div className="flex items-center gap-2">
              <FileCode className="size-4 text-[#A9B8AD]" />
              <span className="font-semibold text-[#F7F7F2]">
                pyproject.toml
              </span>
              <span className="text-[#A9B8AD] text-[11px] hidden sm:inline">
                fastapi-service/pyproject.toml
              </span>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 font-mono text-[11px]">
                <span className="text-[#5FCB8A] font-semibold">+4</span>
                <span className="text-[#E5736A] font-semibold">-2</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setCopiedToml(true);
                  setTimeout(() => setCopiedToml(false), 2000);
                }}
                className="text-[#A9B8AD] hover:text-[#F7F7F2] transition-colors p-1"
                title="Copy file diff"
              >
                {copiedToml ? (
                  <Check className="size-3.5 text-[#5FCB8A]" />
                ) : (
                  <Copy className="size-3.5" />
                )}
              </button>
            </div>
          </div>

          {!collapsedFiles.has("toml") && (
            <div className="p-3 font-mono text-[12px] bg-[#0D1915] overflow-x-auto leading-relaxed">
              <table className="w-full border-collapse">
                <tbody>
                  <tr className="hover:bg-[#15271F]/50">
                    <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">18</td>
                    <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">18</td>
                    <td className="text-[#A9B8AD] pl-2">dependencies = [</td>
                  </tr>
                  <tr className="hover:bg-[#15271F]/50">
                    <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">19</td>
                    <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">19</td>
                    <td className="text-[#A9B8AD] pl-2">    &quot;fastapi&gt;=0.98.0&quot;,</td>
                  </tr>
                  <tr className="bg-[#E5736A]/10 text-[#E5736A]">
                    <td className="w-8 select-none text-right pr-3 text-[#E5736A]/60">20</td>
                    <td className="w-8 select-none text-right pr-4"></td>
                    <td className="pl-2">-     &quot;pydantic&gt;=1.10.8,&lt;2.0.0&quot;,</td>
                  </tr>
                  <tr className="bg-[#5FCB8A]/10 text-[#5FCB8A]">
                    <td className="w-8 select-none text-right pr-3"></td>
                    <td className="w-8 select-none text-right pr-4 text-[#5FCB8A]/60">20</td>
                    <td className="pl-2">+     &quot;pydantic&gt;=2.0.2,&lt;3.0.0&quot;,</td>
                  </tr>
                  <tr className="bg-[#5FCB8A]/10 text-[#5FCB8A]">
                    <td className="w-8 select-none text-right pr-3"></td>
                    <td className="w-8 select-none text-right pr-4 text-[#5FCB8A]/60">21</td>
                    <td className="pl-2">+     &quot;pydantic-settings&gt;=2.0.0&quot;,</td>
                  </tr>
                  <tr className="hover:bg-[#15271F]/50">
                    <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">21</td>
                    <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">22</td>
                    <td className="text-[#A9B8AD] pl-2">    &quot;uvicorn[standard]&gt;=0.22.0&quot;,</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* Regression Suite Dynamics */}
      <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-6 mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
          <div>
            <span className="font-mono text-xs tracking-wider text-[#A9B8AD] uppercase">
              REGRESSION SUITE DYNAMICS
            </span>
            <h3 className="text-base font-semibold text-[#F7F7F2]">
              Deterministic Sandbox Evidence Breakdown
            </h3>
          </div>
          <span className="font-mono text-xs text-[#A9B8AD]">
            Sandbox ID: <span className="text-[#F7F7F2]">nb-sand-9941a</span> · Kernel:{" "}
            <span className="text-[#F7F7F2]">Linux 6.2-cgroup2</span>
          </span>
        </div>

        {/* Progress bar with pass sections */}
        <div className="h-2 w-full rounded-full bg-[#1B3228] flex overflow-hidden mb-3">
          <div className="w-[95%] bg-[#5FCB8A]" />
          <div className="w-[5%] bg-[#B7C9AD]" />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-[#A9B8AD]">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-[#5FCB8A]" />
              <span>42 Regression Suite Passes</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-[#B7C9AD]" />
              <span>2 Auto-Generated Contract Assertions</span>
            </div>
          </div>

          <span className="text-[#5FCB8A] font-semibold">
            100% Pass Rate (0 failures)
          </span>
        </div>
      </Card>

      {/* Bottom Actions Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2">
        <div className="flex flex-wrap items-center gap-3">
          {/* Primary Action Button per DESIGN.md */}
          <Button
            onClick={downloadPatch}
            className="h-10 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-xs px-4 rounded-lg flex items-center gap-2 cursor-pointer shadow-none"
          >
            <Download className="size-3.5" />
            Download Patch (.diff)
          </Button>

          <Button
            variant="outline"
            onClick={downloadEvidence}
            className="h-10 border-[rgba(183,201,173,0.32)] bg-[#15271F] hover:bg-[#1B3228] text-[#F7F7F2] text-xs px-4 rounded-lg flex items-center gap-2 cursor-pointer"
          >
            <Download className="size-3.5 text-[#A9B8AD]" />
            Download Evidence Package (.json + logs)
          </Button>

          <Button
            variant="ghost"
            onClick={onRunAnotherTask}
            className="h-10 text-[#A9B8AD] hover:text-[#F7F7F2] hover:bg-[#1B3228] text-xs px-3 rounded-lg flex items-center gap-1.5 cursor-pointer"
          >
            <RotateCcw className="size-3.5" />
            Run another task
          </Button>
        </div>

        <Badge className="bg-[#15271F] border border-[rgba(183,201,173,0.24)] text-[#5FCB8A] font-mono text-xs px-3 py-1.5 rounded-full flex items-center gap-1.5 self-start sm:self-auto">
          <ShieldCheck className="size-3.5" />
          Patch Sig: ed25519-verified
        </Badge>
      </div>

      <p className="mt-4 text-[11px] font-mono text-[#A9B8AD]">
        RepoMedic does not automatically merge or alter your git remote. Review
        and apply via{" "}
        <code className="text-[#F7F7F2] bg-[#15271F] px-1.5 py-0.5 rounded border border-[rgba(183,201,173,0.16)]">
          git apply repomedic-fix.patch
        </code>
        .
      </p>
    </div>
  );
}
