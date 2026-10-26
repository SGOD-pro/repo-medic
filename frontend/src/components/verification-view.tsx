"use client";

import React, { useState, useEffect, useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CheckCircle2,
  CheckCircle,
  XCircle,
  AlertTriangle,
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
import { RunSummary, ArtifactSummary } from "@/lib/contracts";
import { RepoMedicApiClient } from "@/lib/api";

interface VerificationViewProps {
  onRunAnotherTask: () => void;
  activeRun?: RunSummary | null;
  apiClient?: RepoMedicApiClient;
}

interface ParsedDiffFile {
  filename: string;
  additions: number;
  deletions: number;
  lines: Array<{
    type: "add" | "delete" | "normal";
    content: string;
    oldNum?: number;
    newNum?: number;
  }>;
}

function parseUnifiedDiff(diffText: string): ParsedDiffFile[] {
  if (!diffText.trim()) return [];
  const files: ParsedDiffFile[] = [];
  const rawSections = diffText.split(/(?=^--- )/m);

  for (const section of rawSections) {
    if (!section.trim()) continue;
    const lines = section.split("\n");
    let filename = "modified_file";
    let additions = 0;
    let deletions = 0;
    const parsedLines: ParsedDiffFile["lines"] = [];

    let oldLine = 1;
    let newLine = 1;

    for (const line of lines) {
      if (line.startsWith("--- ")) {
        const match = line.match(/^--- (?:a\/)?(.*)/);
        if (match) filename = match[1];
        continue;
      }
      if (line.startsWith("+++ ")) {
        const match = line.match(/^\+\+\+ (?:b\/)?(.*)/);
        if (match) filename = match[1];
        continue;
      }
      if (line.startsWith("@@ ")) {
        const hunkMatch = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
        if (hunkMatch) {
          oldLine = parseInt(hunkMatch[1], 10);
          newLine = parseInt(hunkMatch[2], 10);
        }
        continue;
      }

      if (line.startsWith("+")) {
        additions++;
        parsedLines.push({
          type: "add",
          content: line.slice(1),
          newNum: newLine++,
        });
      } else if (line.startsWith("-")) {
        deletions++;
        parsedLines.push({
          type: "delete",
          content: line.slice(1),
          oldNum: oldLine++,
        });
      } else {
        parsedLines.push({
          type: "normal",
          content: line.startsWith(" ") ? line.slice(1) : line,
          oldNum: oldLine++,
          newNum: newLine++,
        });
      }
    }

    if (parsedLines.length > 0) {
      files.push({ filename, additions, deletions, lines: parsedLines });
    }
  }

  return files;
}

export interface VerificationViewModel {
  runState: string;
  isPass: boolean;
  isFail: boolean;
  isCancelled: boolean;
  modeLabel: string;
  testsPassed: number | null;
  testsFailed: number | null;
  totalCollected: number | null;
  ratioDisplay: string;
  headerTitle: string;
  regressionsBadgeText: string | null;
  astBadgeVisible: boolean;
  testFilesUnchangedVisible: boolean;
  hashCheckBadgeText: string;
  astProofSupported: boolean;
  astProofText: string;
  characterizationTestsText: string;
  verificationTimeText: string;
  costText: string;
  signatureBadgeText: string | null;
}

export function resolveVerificationViewModel(
  activeRun?: RunSummary | null,
  evidenceData?: Record<string, unknown> | null
): VerificationViewModel {
  const runState = activeRun?.state || "unknown";
  const isPass = runState === "succeeded";
  const isFail = runState === "failed";
  const isCancelled = runState === "cancelled";

  const effectiveMode = activeRun?.mode || (evidenceData?.execution_mode as string) || "offline";
  let modeLabel = "OFFLINE MODE (TURSO)";
  if ((process.env.NEXT_PUBLIC_API_TRANSPORT || "mock") === "mock") {
    modeLabel = "MOCK TRANSPORT";
  } else if (effectiveMode === "live") {
    modeLabel = "LIVE SANDBOX (NEBIUS)";
  } else if (effectiveMode === "replay") {
    modeLabel = "REPLAY MODE";
  }

  const testSummary = evidenceData?.test_summary as Record<string, number> | undefined;
  const testsPassed = typeof testSummary?.passed_count === "number"
    ? testSummary.passed_count
    : (typeof evidenceData?.tests_passed === "number"
      ? (evidenceData.tests_passed as number)
      : null);

  const testsFailed = typeof testSummary?.failed_count === "number"
    ? testSummary.failed_count
    : (typeof evidenceData?.tests_failed === "number"
      ? (evidenceData.tests_failed as number)
      : null);

  const totalCollected = typeof testSummary?.collected_count === "number"
    ? testSummary.collected_count
    : (testsPassed !== null && testsFailed !== null
      ? testsPassed + testsFailed
      : null);

  const ratioDisplay = testsPassed !== null && totalCollected !== null
    ? `${testsPassed} / ${totalCollected}`
    : "Unavailable";

  let headerTitle: string;
  if (isPass) {
    headerTitle = testsPassed !== null && totalCollected !== null
      ? `Behavior preserved (${testsPassed}/${totalCollected} tests passing)`
      : "Verified Source Repair Completed";
  } else if (isFail) {
    headerTitle = testsFailed !== null
      ? `Verification check failed (${testsFailed} tests failing)`
      : "Source Repair Failed";
  } else if (isCancelled) {
    headerTitle = "Run Cancelled";
  } else {
    headerTitle = `Run State: ${runState}`;
  }

  let regressionsBadgeText: string | null = null;
  if (testsFailed !== null) {
    regressionsBadgeText = testsFailed === 0 ? "0 REGRESSIONS" : `${testsFailed} FAILURES`;
  }

  const checks = evidenceData?.checks as Record<string, boolean> | undefined;
  const testFilesUnchangedVisible = isPass && Boolean(checks?.post_patch_hash_match);
  const hashCheckBadgeText = "Test files unchanged";
  const astBadgeVisible = testFilesUnchangedVisible;

  let astProofSupported = false;
  let astProofText = "Evidence proof unavailable";
  if (checks?.post_patch_hash_match && checks?.version_intact) {
    astProofSupported = true;
    astProofText = "AST Proof: 0 test files modified · exact dependency verified";
  } else if (checks?.post_patch_hash_match) {
    astProofSupported = true;
    astProofText = "AST Proof: 0 test files modified";
  } else if (checks) {
    astProofSupported = false;
    astProofText = "Verification checks evaluated without AST proof";
  }

  const characterizationTestsText = typeof evidenceData?.contract_assertions === "number"
    ? `+${evidenceData.contract_assertions} generated`
    : "Unavailable";

  const verificationTimeText = typeof evidenceData?.duration_seconds === "number"
    ? `${evidenceData.duration_seconds.toFixed(1)}s`
    : typeof evidenceData?.execution_time === "string"
    ? evidenceData.execution_time
    : "Unavailable";

  let costText = "Unavailable";
  if (typeof activeRun?.usage?.estimated_usd === "number") {
    costText = `$${activeRun.usage.estimated_usd.toFixed(2)}`;
  } else if (typeof evidenceData?.cost_usd === "number") {
    costText = `$${(evidenceData.cost_usd as number).toFixed(2)}`;
  }

  let signatureBadgeText: string | null = null;
  if (typeof evidenceData?.signature === "string") {
    signatureBadgeText = `Signature: ${evidenceData.signature}`;
  } else if (checks?.tests_passed) {
    signatureBadgeText = "Verification Checks Passed";
  }

  return {
    runState,
    isPass,
    isFail,
    isCancelled,
    modeLabel,
    testsPassed,
    testsFailed,
    totalCollected,
    ratioDisplay,
    headerTitle,
    regressionsBadgeText,
    astBadgeVisible,
    testFilesUnchangedVisible,
    hashCheckBadgeText,
    astProofSupported,
    astProofText,
    characterizationTestsText,
    verificationTimeText,
    costText,
    signatureBadgeText,
  };
}

export function VerificationView({
  onRunAnotherTask,
  activeRun,
  apiClient,
}: VerificationViewProps) {
  const [collapsedFiles, setCollapsedFiles] = useState<Set<string>>(new Set());
  const [copiedFileIndex, setCopiedFileIndex] = useState<number | null>(null);
  const [patchContent, setPatchContent] = useState<string | null>(null);
  const [evidenceData, setEvidenceData] = useState<Record<string, unknown> | null>(null);
  const [downloadingArtifactId, setDownloadingArtifactId] = useState<string | null>(null);

  useEffect(() => {
    if (!activeRun || !apiClient) return;
    let isCancelled = false;

    const patchArt = activeRun.artifacts?.find((a) => a.kind === "patch");
    const evArt = activeRun.artifacts?.find((a) => a.kind === "evidence");

    if (patchArt) {
      apiClient
        .getArtifact(activeRun.run_id, patchArt.artifact_id)
        .then((content) => {
          if (!isCancelled) setPatchContent(content);
        })
        .catch(() => {
          if (!isCancelled) setPatchContent(null);
        });
    } else {
      queueMicrotask(() => {
        if (!isCancelled) setPatchContent(null);
      });
    }

    if (evArt) {
      apiClient
        .getArtifact(activeRun.run_id, evArt.artifact_id)
        .then((raw) => {
          if (!isCancelled) {
            try {
              setEvidenceData(JSON.parse(raw));
            } catch {
              setEvidenceData(null);
            }
          }
        })
        .catch(() => {
          if (!isCancelled) setEvidenceData(null);
        });
    } else {
      queueMicrotask(() => {
        if (!isCancelled) setEvidenceData(null);
      });
    }

    return () => {
      isCancelled = true;
    };
  }, [activeRun, apiClient]);

  const parsedDiffFiles = useMemo(() => {
    return patchContent ? parseUnifiedDiff(patchContent) : [];
  }, [patchContent]);

  const vm = useMemo(
    () => resolveVerificationViewModel(activeRun, evidenceData),
    [activeRun, evidenceData]
  );

  const toggleCollapse = (filename: string) => {
    setCollapsedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) {
        next.delete(filename);
      } else {
        next.add(filename);
      }
      return next;
    });
  };

  const toggleCollapseAll = () => {
    if (collapsedFiles.size > 0) {
      setCollapsedFiles(new Set());
    } else {
      setCollapsedFiles(new Set(parsedDiffFiles.map((f) => f.filename)));
    }
  };

  const handleDownloadArtifact = async (artifact: ArtifactSummary) => {
    if (!activeRun || !apiClient) return;
    setDownloadingArtifactId(artifact.artifact_id);
    try {
      const content = await apiClient.getArtifact(
        activeRun.run_id,
        artifact.artifact_id
      );
      const mimeType =
        artifact.kind === "evidence"
          ? "application/json"
          : "text/plain;charset=utf-8";
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = artifact.filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      console.error("Failed to download artifact:", err);
    } finally {
      setDownloadingArtifactId(null);
    }
  };

  const copyFileDiff = (file: ParsedDiffFile, index: number) => {
    const text = file.lines
      .map((l) => (l.type === "add" ? `+${l.content}` : l.type === "delete" ? `-${l.content}` : ` ${l.content}`))
      .join("\n");
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        setCopiedFileIndex(index);
        setTimeout(() => setCopiedFileIndex(null), 2000);
      });
    }
  };

  const patchArtifact = activeRun?.artifacts?.find((a) => a.kind === "patch");
  const evidenceArtifact = activeRun?.artifacts?.find((a) => a.kind === "evidence");

  return (
    <div className="mx-auto w-full max-w-[1280px] px-6 py-8">
      {/* Top Banner Card: Render Selected Run State and Reason */}
      <Card
        className={`rounded-[20px] p-6 mb-6 border ${
          vm.isPass
            ? "bg-[#15271F] border-[rgba(183,201,173,0.2)]"
            : vm.isFail
            ? "bg-[#271515] border-[#E5736A]/30"
            : vm.isCancelled
            ? "bg-[#272015] border-[#E0B45A]/30"
            : "bg-[#15271F] border-[rgba(183,201,173,0.2)]"
        }`}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div
              className={`mt-0.5 rounded-full p-1.5 border ${
                vm.isPass
                  ? "bg-[#5FCB8A]/20 border-[#5FCB8A]/30"
                  : vm.isFail
                  ? "bg-[#E5736A]/20 border-[#E5736A]/30"
                  : "bg-[#E0B45A]/20 border-[#E0B45A]/30"
              }`}
            >
              {vm.isPass ? (
                <CheckCircle className="size-5 text-[#5FCB8A]" />
              ) : vm.isFail ? (
                <XCircle className="size-5 text-[#E5736A]" />
              ) : (
                <AlertTriangle className="size-5 text-[#E0B45A]" />
              )}
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-xl font-semibold text-[#F7F7F2]">
                  {vm.isPass
                    ? "Verified Source Repair Completed"
                    : vm.isFail
                    ? "Source Repair Failed"
                    : vm.isCancelled
                    ? "Run Cancelled"
                    : `Run State: ${vm.runState}`}
                </h1>
                <Badge
                  className={`border-transparent font-mono text-xs font-semibold px-2 py-0.5 ${
                    vm.isPass
                      ? "bg-[#5FCB8A]/20 text-[#5FCB8A]"
                      : vm.isFail
                      ? "bg-[#E5736A]/20 text-[#E5736A]"
                      : "bg-[#E0B45A]/20 text-[#E0B45A]"
                  }`}
                >
                  {vm.runState.toUpperCase()}
                </Badge>
                {activeRun?.run_id && (
                  <Badge
                    variant="outline"
                    className="border-[rgba(183,201,173,0.24)] bg-transparent font-mono text-[11px] text-[#A9B8AD] px-2 py-0.5"
                  >
                    {activeRun.run_id}
                  </Badge>
                )}
                <Badge
                  variant="outline"
                  className="border-[rgba(183,201,173,0.24)] bg-transparent font-mono text-[11px] text-[#A9B8AD] px-2 py-0.5"
                >
                  {vm.modeLabel}
                </Badge>
              </div>

              {activeRun?.task_id && (
                <p className="mt-1 text-xs text-[#A9B8AD]">
                  Task <span className="font-mono text-[#F7F7F2]">{activeRun.task_id}</span>
                  {activeRun.search_mode ? ` using ${activeRun.search_mode} strategy` : ""}
                </p>
              )}

              {activeRun?.reason && (
                <p className="mt-2 text-xs font-mono text-[#E5736A] bg-[#E5736A]/10 border border-[#E5736A]/20 rounded px-2.5 py-1">
                  Reason: {activeRun.reason}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1.5 font-mono text-xs text-[#A9B8AD] whitespace-nowrap">
            <span
              className={`size-2 rounded-full ${
                vm.isPass ? "bg-[#5FCB8A]" : vm.isFail ? "bg-[#E5736A]" : "bg-[#E0B45A]"
              }`}
            />
            <span>{vm.isPass ? "Sandbox Terminated Cleanly" : "Process Halted"}</span>
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
            {vm.regressionsBadgeText && (
              <Badge
                className={`border-transparent font-mono text-xs px-2 py-0.5 ${
                  vm.testsFailed === 0
                    ? "bg-[#5FCB8A]/15 text-[#5FCB8A]"
                    : "bg-[#E5736A]/15 text-[#E5736A]"
                }`}
              >
                {vm.regressionsBadgeText}
              </Badge>
            )}
            {vm.testFilesUnchangedVisible && (
              <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-mono text-xs px-2 py-0.5">
                {vm.hashCheckBadgeText}
              </Badge>
            )}
          </div>
        </div>

        <h2 className="text-2xl font-semibold text-[#F7F7F2] mb-6">
          {vm.headerTitle}
        </h2>

        {/* 5 Metric Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          <div className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between">
            <span className="text-[11px] font-mono text-[#A9B8AD] mb-3">
              Tests Pass / Total
            </span>
            <div className="flex items-center justify-between">
              <span
                className={`font-mono text-sm font-semibold ${
                  vm.isPass ? "text-[#5FCB8A]" : "text-[#E5736A]"
                }`}
              >
                {vm.ratioDisplay}
              </span>
              {vm.isPass ? (
                <CheckCircle2 className="size-4 text-[#5FCB8A]" />
              ) : (
                <XCircle className="size-4 text-[#E5736A]" />
              )}
            </div>
          </div>

          <div className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between">
            <span className="text-[11px] font-mono text-[#A9B8AD] mb-3">
              Characterization Tests
            </span>
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold text-[#F7F7F2]">
                {vm.characterizationTestsText}
              </span>
              <FileCode className="size-4 text-[#A9B8AD]" />
            </div>
          </div>

          <div className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between">
            <span className="text-[11px] font-mono text-[#A9B8AD] mb-3">
              Files Changed
            </span>
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold text-[#F7F7F2]">
                {parsedDiffFiles.length} {parsedDiffFiles.length === 1 ? "file" : "files"}
              </span>
              <FileText className="size-4 text-[#A9B8AD]" />
            </div>
          </div>

          <div className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between">
            <span className="text-[11px] font-mono text-[#A9B8AD] mb-3">
              Verification Time
            </span>
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold text-[#F7F7F2]">
                {vm.verificationTimeText}
              </span>
              <Clock className="size-4 text-[#A9B8AD]" />
            </div>
          </div>

          <div className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between col-span-2 md:col-span-1">
            <span className="text-[11px] font-mono text-[#A9B8AD] mb-3">
              Estimated Cost
            </span>
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold text-[#F7F7F2]">
                {vm.costText}
              </span>
              <Cpu className="size-4 text-[#A9B8AD]" />
            </div>
          </div>
        </div>

        {/* Proof Detail Bar */}
        <div className="rounded-xl bg-[#0D1915] border border-[rgba(183,201,173,0.12)] px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono text-[#A9B8AD]">
          <div className="flex items-center gap-2">
            <ShieldCheck
              className={`size-4 shrink-0 ${
                vm.astProofSupported ? "text-[#5FCB8A]" : "text-[#A9B8AD]"
              }`}
            />
            <span className={vm.astProofSupported ? "text-[#F7F7F2]" : "text-[#A9B8AD]"}>
              {vm.astProofText}
            </span>
          </div>
          <div className="whitespace-nowrap">
            <span>Mode: </span>
            <span className="text-[#F7F7F2]">{vm.modeLabel}</span>
          </div>
        </div>
      </Card>

      {/* Actual Artifacts Section with Download by artifact_id */}
      {activeRun?.artifacts && activeRun.artifacts.length > 0 && (
        <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-[#F7F7F2]">
              Run Artifacts ({activeRun.artifacts.length})
            </h3>
            <span className="font-mono text-xs text-[#A9B8AD]">
              Downloads addressable by artifact id
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {activeRun.artifacts.map((art) => (
              <div
                key={art.artifact_id}
                className="rounded-xl bg-[#1B3228] border border-[rgba(183,201,173,0.12)] p-4 flex flex-col justify-between gap-3"
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <Badge className="bg-[#15271F] text-[#5FCB8A] border-[rgba(183,201,173,0.2)] font-mono text-[10px] uppercase">
                      {art.kind}
                    </Badge>
                    <span className="font-mono text-[10px] text-[#A9B8AD]">
                      {art.artifact_id}
                    </span>
                  </div>
                  <div className="font-mono text-xs font-semibold text-[#F7F7F2] truncate">
                    {art.filename}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleDownloadArtifact(art)}
                  disabled={downloadingArtifactId === art.artifact_id}
                  className="w-full h-8 border-[rgba(183,201,173,0.24)] bg-[#15271F] hover:bg-[#1B3228] text-xs text-[#F7F7F2] gap-1.5"
                >
                  <Download className="size-3" />
                  {downloadingArtifactId === art.artifact_id ? "Downloading..." : `Download ${art.kind}`}
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Unified Change Manifest / Patch Diff */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-baseline gap-2">
            <h3 className="text-lg font-semibold text-[#F7F7F2]">
              Unified Change Manifest
            </h3>
            <span className="text-xs text-[#A9B8AD]">
              {parsedDiffFiles.length} {parsedDiffFiles.length === 1 ? "file inspected" : "files inspected"}
            </span>
          </div>

          {parsedDiffFiles.length > 0 && (
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleCollapseAll}
                className="text-xs text-[#A9B8AD] hover:text-[#F7F7F2] h-7 px-2"
              >
                {collapsedFiles.size > 0 ? "Expand All" : "Collapse All"}
              </Button>
            </div>
          )}
        </div>

        {parsedDiffFiles.length > 0 ? (
          parsedDiffFiles.map((file, idx) => {
            const isCollapsed = collapsedFiles.has(file.filename);
            return (
              <Card
                key={file.filename}
                className="rounded-[16px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] overflow-hidden mb-4"
              >
                <div className="flex items-center justify-between bg-[#1B3228] px-4 py-2.5 border-b border-[rgba(183,201,173,0.12)] font-mono text-xs">
                  <div
                    className="flex items-center gap-2 cursor-pointer"
                    onClick={() => toggleCollapse(file.filename)}
                  >
                    <FileCode className="size-4 text-[#A9B8AD]" />
                    <span className="font-semibold text-[#F7F7F2]">
                      {file.filename}
                    </span>
                    {isCollapsed ? (
                      <ChevronDown className="size-3.5 text-[#A9B8AD]" />
                    ) : (
                      <ChevronUp className="size-3.5 text-[#A9B8AD]" />
                    )}
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5 font-mono text-[11px]">
                      <span className="text-[#5FCB8A] font-semibold">
                        +{file.additions}
                      </span>
                      <span className="text-[#E5736A] font-semibold">
                        -{file.deletions}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => copyFileDiff(file, idx)}
                      className="text-[#A9B8AD] hover:text-[#F7F7F2] transition-colors p-1"
                      title="Copy file diff"
                    >
                      {copiedFileIndex === idx ? (
                        <Check className="size-3.5 text-[#5FCB8A]" />
                      ) : (
                        <Copy className="size-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                {!isCollapsed && (
                  <div className="p-3 font-mono text-[12px] bg-[#0D1915] overflow-x-auto leading-relaxed">
                    <table className="w-full border-collapse">
                      <tbody>
                        {file.lines.map((line, lIdx) => (
                          <tr
                            key={lIdx}
                            className={
                              line.type === "add"
                                ? "bg-[#5FCB8A]/10 text-[#5FCB8A]"
                                : line.type === "delete"
                                ? "bg-[#E5736A]/10 text-[#E5736A]"
                                : "hover:bg-[#15271F]/50"
                            }
                          >
                            <td className="w-8 select-none text-right pr-3 text-[#A9B8AD]/50">
                              {line.oldNum ?? ""}
                            </td>
                            <td className="w-8 select-none text-right pr-4 text-[#A9B8AD]/50">
                              {line.newNum ?? ""}
                            </td>
                            <td className="pl-2">
                              {line.type === "add"
                                ? `+ ${line.content}`
                                : line.type === "delete"
                                ? `- ${line.content}`
                                : `  ${line.content}`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            );
          })
        ) : (
          <div className="rounded-xl bg-[#15271F] border border-[rgba(183,201,173,0.12)] p-6 text-center text-xs font-mono text-[#A9B8AD]">
            No patch artifact produced for this run.
          </div>
        )}
      </div>

      {/* Bottom Actions Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2">
        <div className="flex flex-wrap items-center gap-3">
          {patchArtifact && (
            <Button
              onClick={() => handleDownloadArtifact(patchArtifact)}
              className="h-10 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-xs px-4 rounded-lg flex items-center gap-2 cursor-pointer shadow-none"
            >
              <Download className="size-3.5" />
              Download Patch (.diff)
            </Button>
          )}

          {evidenceArtifact && (
            <Button
              variant="outline"
              onClick={() => handleDownloadArtifact(evidenceArtifact)}
              className="h-10 border-[rgba(183,201,173,0.32)] bg-[#15271F] hover:bg-[#1B3228] text-[#F7F7F2] text-xs px-4 rounded-lg flex items-center gap-2 cursor-pointer"
            >
              <Download className="size-3.5 text-[#A9B8AD]" />
              Download Evidence Package (.json)
            </Button>
          )}

          <Button
            variant="ghost"
            onClick={onRunAnotherTask}
            className="h-10 text-[#A9B8AD] hover:text-[#F7F7F2] hover:bg-[#1B3228] text-xs px-3 rounded-lg flex items-center gap-1.5 cursor-pointer"
          >
            <RotateCcw className="size-3.5" />
            Run another task
          </Button>
        </div>

        {vm.signatureBadgeText && (
          <Badge className="bg-[#15271F] border border-[rgba(183,201,173,0.24)] text-[#5FCB8A] font-mono text-xs px-3 py-1.5 rounded-full flex items-center gap-1.5 self-start sm:self-auto">
            <ShieldCheck className="size-3.5" />
            {vm.signatureBadgeText}
          </Badge>
        )}
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
