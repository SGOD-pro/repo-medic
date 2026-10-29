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
  ShieldCheck,
  Copy,
  Check,
  Download,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Play,
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
  patchApplied: boolean;
  preservedSubtitle: string;
}

export function resolveVerificationViewModel(
  activeRun?: RunSummary | null,
  evidenceData?: Record<string, unknown> | null
): VerificationViewModel {
  const runState = activeRun?.state || "unknown";
  const isPass = runState === "succeeded";
  const isFail = runState === "failed";
  const isCancelled = runState === "cancelled";

  const effectiveMode = activeRun?.mode || (evidenceData?.execution_mode as string) || null;
  let modeLabel = "UNAVAILABLE";
  if (effectiveMode === "live") {
    modeLabel = "LIVE SANDBOX (NEBIUS)";
  } else if (effectiveMode === "offline") {
    modeLabel = "OFFLINE MODE (TURSO)";
  } else if (effectiveMode === "replay") {
    modeLabel = "REPLAY MODE";
  } else if (!effectiveMode && (process.env.NEXT_PUBLIC_API_TRANSPORT || "mock") === "mock") {
    modeLabel = "MOCK TRANSPORT";
  }

  const checks = evidenceData?.checks as Record<string, boolean> | undefined;
  const patchApplied = checks?.patch_applied ?? true;

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

  const ratioDisplay = !patchApplied
    ? "Not Run"
    : testsPassed !== null && totalCollected !== null
    ? `${testsPassed} / ${totalCollected}`
    : "Unavailable";

  let headerTitle: string;
  if (!patchApplied) {
    headerTitle = "Candidate patch failed to apply cleanly";
  } else if (isPass) {
    headerTitle = testsPassed !== null && totalCollected !== null
      ? `Behavior preserved (${testsPassed}/${totalCollected} tests passing)`
      : "Verified Source Repair Completed";
  } else if (isFail) {
    headerTitle = testsFailed !== null && testsFailed > 0
      ? `Verification check failed (${testsFailed} tests failing)`
      : "Source Repair Failed";
  } else if (isCancelled) {
    headerTitle = "Run Cancelled";
  } else {
    headerTitle = `Run State: ${runState}`;
  }

  let regressionsBadgeText: string | null = null;
  if (!patchApplied) {
    regressionsBadgeText = "PATCH APPLY FAILED";
  } else if (isPass) {
    regressionsBadgeText = testsFailed === 0 ? "0 REGRESSIONS" : null;
  } else if (isFail) {
    regressionsBadgeText = testsFailed !== null && testsFailed > 0 ? `${testsFailed} FAILURES` : "VERIFICATION FAILED";
  }
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

  let preservedSubtitle: string;
  if (isPass && testsPassed !== null) {
    preservedSubtitle = "All assertions verified";
  } else if (isFail) {
    preservedSubtitle = !patchApplied
      ? "Patch application failed · 0 tests run"
      : "Verification not completed";
  } else {
    preservedSubtitle = "Test metrics unavailable";
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
    patchApplied,
    preservedSubtitle,
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
  const [downloadError, setDownloadError] = useState<string | null>(null);

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
    setDownloadError(null);
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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Download failed";
      setDownloadError(`Failed to download ${artifact.filename}: ${msg}`);
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

  // -------------------------------------------------------------
  // EMPTY STATE: When no run is selected
  // -------------------------------------------------------------
  if (!activeRun) {
    return (
      <div data-testid="verification-view" className="mx-auto w-full max-w-[1280px] px-4 sm:px-6 py-12">
        <div className="rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] p-8 sm:p-12 text-center max-w-xl mx-auto">
          <div className="size-12 rounded-full bg-[#1B3228] border border-[rgba(183,201,173,0.2)] flex items-center justify-center mx-auto mb-4">
            <ShieldCheck className="size-6 text-[#A9B8AD]" />
          </div>
          <h2 className="text-xl font-semibold text-[#F7F7F2] mb-2">
            No Verification Results Selected
          </h2>
          <p className="text-xs sm:text-sm text-[#A9B8AD] mb-6 leading-relaxed">
            Select a completed repair run or view a saved demo to inspect verified candidate patches, test logs, and contract evidence.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button
              type="button"
              onClick={onRunAnotherTask}
              className="h-10 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-xs sm:text-sm px-4 rounded-lg cursor-pointer"
            >
              <Play className="size-3.5 fill-current" />
              Choose a Demo Task
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                window.location.search = "?runId=run_c89257b365a247b0ab8d8f44fb04a779";
              }}
              className="h-10 border-[rgba(183,201,173,0.3)] bg-[#0D1915] text-[#F7F7F2] hover:bg-[#1B3228] text-xs sm:text-sm px-4 rounded-lg cursor-pointer"
            >
              Load Demo Shop Run
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="verification-view"
      className="mx-auto w-full max-w-[1280px] px-4 sm:px-6 py-6 sm:py-8 space-y-6"
    >
      {/* ------------------------------------------------------------- */}
      {/* TOP BANNER: OUTCOME & REASON                                  */}
      {/* ------------------------------------------------------------- */}
      <Card
        className={`rounded-xl p-5 sm:p-6 border shadow-none ${
          vm.isPass
            ? "bg-[#15271F] border-[rgba(183,201,173,0.2)]"
            : vm.isFail
            ? "bg-[#241414] border-[#E5736A]/30"
            : "bg-[#1D1A14] border-[#E0B45A]/30"
        }`}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div
              className={`mt-0.5 rounded-full p-1.5 border shrink-0 ${
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
                <h1 className="text-lg sm:text-xl font-semibold text-[#F7F7F2]">
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
                {vm.modeLabel && (
                  <Badge
                    variant="outline"
                    data-testid="verification-mode-badge"
                    className="border-[rgba(183,201,173,0.25)] bg-[#1B3228] font-mono text-xs text-[#B7C9AD]"
                  >
                    {vm.modeLabel}
                  </Badge>
                )}
                {activeRun?.run_id && (
                  <Badge
                    variant="outline"
                    className="border-[rgba(183,201,173,0.2)] bg-[#0D1915] font-mono text-xs text-[#A9B8AD]"
                  >
                    {activeRun.run_id}
                  </Badge>
                )}
                {vm.regressionsBadgeText && (
                  <Badge
                    className={`border-transparent font-mono text-xs px-2 py-0.5 ${
                      vm.isPass
                        ? "bg-[#5FCB8A]/15 text-[#5FCB8A]"
                        : "bg-[#E5736A]/20 text-[#E5736A]"
                    }`}
                  >
                    {vm.regressionsBadgeText}
                  </Badge>
                )}
              </div>
              {activeRun?.task_id && (
                <p className="mt-1 text-xs text-[#A9B8AD]">
                  Task <span className="font-mono text-[#F7F7F2] font-medium">{activeRun.task_id}</span>
                  {activeRun.search_mode ? ` · ${activeRun.search_mode === "branch_refine" ? "Branch & Refine" : "Sequential Direct"} strategy` : ""}
                </p>
              )}
              <p className="text-xs sm:text-sm text-[#A9B8AD] mt-1.5 leading-relaxed">
                {activeRun.reason || (vm.isPass
                  ? "All original test assertions passed in clean container verification. Patch ready for review."
                  : vm.isFail
                  ? "Repair candidates failed post-patch verification or safety validation."
                  : "Run was cancelled by operator.")}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0 self-end md:self-auto">
            {patchArtifact && (
              <Button
                variant="outline"
                size="sm"
                disabled={downloadingArtifactId === patchArtifact.artifact_id}
                onClick={() => handleDownloadArtifact(patchArtifact)}
                className="h-9 border-[rgba(183,201,173,0.3)] bg-[#0D1915] text-[#F7F7F2] hover:bg-[#1B3228] text-xs px-3 rounded-lg flex items-center gap-1.5 cursor-pointer"
              >
                <Download className="size-3.5 text-[#5FCB8A]" />
                <span>{downloadingArtifactId === patchArtifact.artifact_id ? "Downloading..." : "Download patch"}</span>
              </Button>
            )}
            {evidenceArtifact && (
              <Button
                variant="outline"
                size="sm"
                disabled={downloadingArtifactId === evidenceArtifact.artifact_id}
                onClick={() => handleDownloadArtifact(evidenceArtifact)}
                className="h-9 border-[rgba(183,201,173,0.3)] bg-[#0D1915] text-[#F7F7F2] hover:bg-[#1B3228] text-xs px-3 rounded-lg flex items-center gap-1.5 cursor-pointer"
              >
                <Download className="size-3.5 text-[#7FB3D5]" />
                <span>{downloadingArtifactId === evidenceArtifact.artifact_id ? "Downloading..." : "Download evidence"}</span>
              </Button>
            )}
            <Button
              size="sm"
              onClick={onRunAnotherTask}
              className="h-9 bg-[#1B3228] text-[#F7F7F2] hover:bg-[#203c30] border border-[rgba(183,201,173,0.2)] text-xs px-3 rounded-lg flex items-center gap-1.5 cursor-pointer"
            >
              <RotateCcw className="size-3.5" />
              <span>Run another task</span>
            </Button>
          </div>
        </div>

        {downloadError && (
          <div className="mt-3 p-2.5 rounded-lg bg-[#241414] border border-[#E5736A]/40 text-xs font-mono text-[#E5736A]">
            {downloadError}
          </div>
        )}
      </Card>

      {/* ------------------------------------------------------------- */}
      {/* EVIDENCE SUMMARY BENTO GRID                                   */}
      {/* ------------------------------------------------------------- */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
        {/* Metric 1: Preserved Tests */}
        <div className="rounded-xl bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-4">
          <div className="flex items-center justify-between text-xs font-mono text-[#A9B8AD] mb-1">
            <span>PRESERVED TESTS</span>
            {vm.isPass ? (
              <CheckCircle2 className="size-3.5 text-[#5FCB8A]" />
            ) : (
              <XCircle className="size-3.5 text-[#E5736A]" />
            )}
          </div>
          <div className="text-xl sm:text-2xl font-bold font-mono text-[#F7F7F2]">
            {vm.ratioDisplay}
          </div>
          <div className="text-[11px] text-[#A9B8AD] mt-1">
            {vm.preservedSubtitle}
          </div>
        </div>

        {/* Metric 2: Verification Time */}
        <div className="rounded-xl bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-4">
          <div className="flex items-center justify-between text-xs font-mono text-[#A9B8AD] mb-1">
            <span>VERIFICATION TIME</span>
            <Clock className="size-3.5 text-[#7FB3D5]" />
          </div>
          <div className="text-xl sm:text-2xl font-bold font-mono text-[#F7F7F2]">
            {vm.verificationTimeText}
          </div>
          <div className="text-[11px] text-[#A9B8AD] mt-1">
            Isolated container run
          </div>
        </div>

        {/* Metric 3: Integrity Check */}
        <div className="rounded-xl bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-4">
          <div className="flex items-center justify-between text-xs font-mono text-[#A9B8AD] mb-1">
            <span>TEST INTEGRITY</span>
            <ShieldCheck className="size-3.5 text-[#5FCB8A]" />
          </div>
          <div className="text-sm sm:text-base font-bold font-mono text-[#F7F7F2] truncate mt-1">
            {vm.testFilesUnchangedVisible ? "Unmodified" : vm.astProofSupported ? "Verified" : "Evaluated"}
          </div>
          <div className="text-[11px] text-[#A9B8AD] mt-1 truncate">
            {vm.hashCheckBadgeText}
          </div>
        </div>

        {/* Metric 4: Estimated Usage */}
        <div className="rounded-xl bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-4">
          <div className="flex items-center justify-between text-xs font-mono text-[#A9B8AD] mb-1">
            <span>ESTIMATED SPEND</span>
            <span className="text-[10px] text-[#A9B8AD]">USD</span>
          </div>
          <div className="text-xl sm:text-2xl font-bold font-mono text-[#F7F7F2]">
            {vm.costText}
          </div>
          <div className="text-[11px] text-[#A9B8AD] mt-1">
            Estimated model usage
          </div>
        </div>
      </div>

      {/* Proof Note when AST or checks exist */}
      {vm.astProofText && (
        <div className="rounded-lg bg-[#15271F] border border-[rgba(183,201,173,0.12)] px-4 py-2.5 flex items-center justify-between text-xs text-[#A9B8AD] font-mono">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-[#5FCB8A]" />
            <span>{vm.astProofText}</span>
          </div>
          {vm.signatureBadgeText && (
            <Badge className="bg-[#1B3228] text-[#5FCB8A] border-[rgba(183,201,173,0.2)] text-[10px] px-2 py-0">
              {vm.signatureBadgeText}
            </Badge>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* PATCH DIFF VIEWER                                             */}
      {/* ------------------------------------------------------------- */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileCode className="size-5 text-[#5FCB8A]" />
            <h2 className="text-base sm:text-lg font-semibold text-[#F7F7F2]">
              Synthesized Candidate Patch
            </h2>
            <Badge className="bg-[#1B3228] text-[#B7C9AD] border-[rgba(183,201,173,0.2)] font-mono text-xs px-2 py-0">
              {parsedDiffFiles.length} {parsedDiffFiles.length === 1 ? "file" : "files"} changed
            </Badge>
          </div>
          {parsedDiffFiles.length > 1 && (
            <button
              type="button"
              onClick={toggleCollapseAll}
              className="text-xs text-[#A9B8AD] hover:text-[#F7F7F2] font-mono cursor-pointer"
            >
              {collapsedFiles.size > 0 ? "Expand All" : "Collapse All"}
            </button>
          )}
        </div>

        {parsedDiffFiles.length === 0 ? (
          <div className="rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] p-8 text-center text-xs text-[#A9B8AD]">
            {activeRun.state === "succeeded"
              ? "Loading patch artifact..."
              : "No patch diff produced for this run."}
          </div>
        ) : (
          <div className="space-y-4">
            {parsedDiffFiles.map((file, idx) => {
              const isCollapsed = collapsedFiles.has(file.filename);
              return (
                <div
                  key={idx}
                  className="rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#0D1915] overflow-hidden"
                >
                  {/* File Header */}
                  <div
                    onClick={() => toggleCollapse(file.filename)}
                    className="flex items-center justify-between px-4 py-2.5 bg-[#15271F] border-b border-[rgba(183,201,173,0.12)] cursor-pointer select-none"
                  >
                    <div className="flex items-center gap-2">
                      {isCollapsed ? (
                        <ChevronDown className="size-4 text-[#A9B8AD]" />
                      ) : (
                        <ChevronUp className="size-4 text-[#A9B8AD]" />
                      )}
                      <span className="font-mono text-xs font-semibold text-[#F7F7F2]">
                        {file.filename}
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-[#5FCB8A]">+{file.additions}</span>
                        <span className="text-[#E5736A]">-{file.deletions}</span>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          copyFileDiff(file, idx);
                        }}
                        className="text-xs text-[#A9B8AD] hover:text-[#F7F7F2] flex items-center gap-1 cursor-pointer"
                        title="Copy diff"
                      >
                        {copiedFileIndex === idx ? (
                          <Check className="size-3 text-[#5FCB8A]" />
                        ) : (
                          <Copy className="size-3" />
                        )}
                        <span className="hidden sm:inline">{copiedFileIndex === idx ? "Copied" : "Copy"}</span>
                      </button>
                    </div>
                  </div>

                  {/* Diff Content Box */}
                  {!isCollapsed && (
                    <div className="p-3 font-mono text-xs overflow-x-auto max-h-[500px] leading-relaxed">
                      {file.lines.map((line, lIdx) => (
                        <div
                          key={lIdx}
                          className={`flex items-start px-2 py-0.5 rounded ${
                            line.type === "add"
                              ? "bg-[#5FCB8A]/10 text-[#5FCB8A]"
                              : line.type === "delete"
                              ? "bg-[#E5736A]/10 text-[#E5736A]"
                              : "text-[#A9B8AD]"
                          }`}
                        >
                          <span className="w-10 text-[10px] text-[#A9B8AD]/60 select-none text-right pr-3 shrink-0">
                            {line.newNum || line.oldNum || ""}
                          </span>
                          <span className="w-4 select-none shrink-0 font-bold">
                            {line.type === "add" ? "+" : line.type === "delete" ? "-" : " "}
                          </span>
                          <span className="whitespace-pre flex-1 break-all select-text">
                            {line.content}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------- */}
      {/* RUN ARTIFACTS LIST                                             */}
      {/* ------------------------------------------------------------- */}
      {activeRun.artifacts && activeRun.artifacts.length > 0 && (
        <Card className="rounded-xl bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-5 shadow-none">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="size-4 text-[#A9B8AD]" />
            <h3 className="text-sm font-semibold text-[#F7F7F2]">
              Run Artifacts ({activeRun.artifacts.length})
            </h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {activeRun.artifacts.map((art) => (
              <div
                key={art.artifact_id}
                className="rounded-lg bg-[#0D1915] border border-[rgba(183,201,173,0.12)] p-3 flex items-center justify-between gap-2"
              >
                <div>
                  <div className="font-mono text-xs font-semibold text-[#F7F7F2] truncate max-w-[180px]">
                    {art.filename}
                  </div>
                  <div className="font-mono text-[10px] text-[#A9B8AD]">
                    {art.kind.toUpperCase()} · {art.artifact_id.substring(0, 8)}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={downloadingArtifactId === art.artifact_id}
                  onClick={() => handleDownloadArtifact(art)}
                  className="h-7 text-xs text-[#5FCB8A] hover:bg-[#1B3228] px-2 cursor-pointer shrink-0"
                >
                  <Download className="size-3.5" />
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
