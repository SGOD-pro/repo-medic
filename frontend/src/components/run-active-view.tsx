"use client";

import React, { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCw,
  Hourglass,
  Clock,
  ShieldCheck,
  Copy,
  Check,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Wrench,
  RefreshCw,
} from "lucide-react";
import { ConnectionStatus, ErrorDetail, RunSummary } from "@/lib/contracts";

interface RunActiveViewProps {
  onInspectResults: () => void;
  onCancelRun: () => void | Promise<void>;
  startedAt?: number;
  activeRun?: RunSummary | null;
  onReturnToTasks?: () => void;
}

export function RunActiveView({
  onInspectResults,
  onCancelRun,
  startedAt,
  activeRun,
  onReturnToTasks,
}: RunActiveViewProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(() =>
    startedAt ? Math.max(0, Math.floor((Date.now() - startedAt) / 1000)) : 105
  );
  const [copiedLog, setCopiedLog] = useState(false);
  const [showStackB, setShowStackB] = useState(false);

  // Connection, Cancellation & Error States (AC-1..AC-8)
  const [isCancelling, setIsCancelling] = useState(false);
  const [isCancelled, setIsCancelled] = useState(() => activeRun?.state === "cancelled");
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connected");
  const [reconnectAttempt, setReconnectAttempt] = useState<number>(0);
  const [errorDetail, setErrorDetail] = useState<ErrorDetail | null>(null);
  const [showTraceback, setShowTraceback] = useState(false);
  const [copiedTraceback, setCopiedTraceback] = useState(false);

  useEffect(() => {
    if (activeRun?.state === "cancelled") {
      queueMicrotask(() => {
        setIsCancelled(true);
      });
    }
  }, [activeRun?.state]);

  useEffect(() => {
    if (isCancelled) return;
    const timer = setInterval(() => {
      if (startedAt) {
        setElapsedSeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
      } else {
        setElapsedSeconds((prev) => prev + 1);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [startedAt, isCancelled]);

  const formatElapsed = (sec: number) => {
    const safeSec = Math.max(0, Math.floor(Number.isFinite(sec) ? sec : 0));
    const m = Math.floor(safeSec / 60);
    const s = safeSec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}s`;
  };

  const candidateALog = `[00:01.12] sandbox: creating isolated container environment (python 3.11, pydantic 2.0.2)
[00:03.45] agent: generating patch for src/app/schemas.py
[00:08.20] verifier: applying untrusted patch to clean repo
[00:09.11] verifier: ast check passed (0 test files modified, source allowlist respected)
[00:14.30] pytest: running full test suite (42 tests)...
[00:22.04] pytest: test_users_schema.py::test_validation PASSED
[00:23.95] pytest: ================= 42 passed in 1.48s =================
[00:24.20] verifier: candidate A verified successfully`;

  const fallbackCopy = () => {
    try {
      const textarea = document.createElement("textarea");
      textarea.value = candidateALog;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopiedLog(true);
      setTimeout(() => setCopiedLog(false), 2000);
    } catch {
      // Ignore if document is not available
    }
  };

  const copyLogToClipboard = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(candidateALog)
        .then(() => {
          setCopiedLog(true);
          setTimeout(() => setCopiedLog(false), 2000);
        })
        .catch(() => {
          fallbackCopy();
        });
    } else {
      fallbackCopy();
    }
  };

  const handleCancelClick = async () => {
    setIsCancelling(true);
    try {
      await Promise.resolve(onCancelRun());
    } finally {
      setIsCancelling(false);
      setIsCancelled(true);
    }
  };

  const handleSimulateDisconnect = () => {
    setConnectionStatus("reconnecting");
    setReconnectAttempt(1);
    setTimeout(() => {
      setReconnectAttempt(2);
      setTimeout(() => {
        setReconnectAttempt(3);
        setTimeout(() => {
          setConnectionStatus("connected");
          setReconnectAttempt(0);
        }, 1200);
      }, 1000);
    }, 1000);
  };

  const handleSimulateError = () => {
    setErrorDetail({
      code: "ENGINE_EXECUTION_FAILURE",
      message: "Sandbox container exited unexpectedly with exit code 137 (OOM killed) during Candidate B synthesis.",
      traceback: `EngineError: Process 1420 killed by cgroup memory limit (512MB)
  at verify_sandbox_execution (engine/sandbox.py:214)
  at execute_refinement_cycle (engine/repair.py:182)
  at run_candidate_matrix (engine/orchestrator.py:94)`,
      timestamp: new Date().toISOString(),
      recoverable: false,
    });
  };

  const handleSimulateExceededRetries = () => {
    setConnectionStatus("reconnecting");
    setReconnectAttempt(5);
    setTimeout(() => {
      setConnectionStatus("disconnected");
      setReconnectAttempt(0);
    }, 600);
  };

  const handleRetryConnection = () => {
    setConnectionStatus("reconnecting");
    setReconnectAttempt(1);
    setTimeout(() => {
      setConnectionStatus("connected");
      setReconnectAttempt(0);
    }, 800);
  };

  const handleClearSimulation = () => {
    setConnectionStatus("connected");
    setReconnectAttempt(0);
    setErrorDetail(null);
  };

  const copyTraceback = () => {
    if (!errorDetail?.traceback) return;
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(errorDetail.traceback)
        .then(() => {
          setCopiedTraceback(true);
          setTimeout(() => setCopiedTraceback(false), 2000);
        })
        .catch(() => {
          // Gracefully ignore or fallback
        });
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1280px] px-6 py-8">
      {/* Top Pipeline Status & Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-6 border-b border-[rgba(183,201,173,0.16)] mb-8">
        {/* Left: Active Pipeline details */}
        <div className="flex flex-wrap items-center gap-3">
          {isCancelled ? (
            <Badge className="bg-[#E5736A]/15 text-[#E5736A] border-transparent font-medium gap-1.5 px-2.5 py-1 rounded-full">
              <XCircle className="size-3.5" />
              RUN CANCELLED
            </Badge>
          ) : (
            <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-medium gap-1.5 px-2.5 py-1 rounded-full">
              <span className="size-1.5 rounded-full bg-[#5FCB8A] animate-pulse" />
              ACTIVE PIPELINE
            </Badge>
          )}

          <span className="text-lg font-semibold text-[#F7F7F2]">
            fastapi-service
          </span>
          <span className="text-sm font-mono text-[#A9B8AD]">
            (pydantic 1.10.8 → 2.0.2)
          </span>

          {connectionStatus === "connected" && !isCancelled && (
            <Badge
              variant="outline"
              className="border-[rgba(183,201,173,0.24)] bg-[#15271F] text-[#A9B8AD] text-xs font-mono px-2 py-0.5 rounded-full"
            >
              <span className="size-1.5 rounded-full bg-[#7FB3D5] mr-1.5" />
              LIVE SANDBOX (NEBIUS / CONTREE)
            </Badge>
          )}

          {connectionStatus === "reconnecting" && !isCancelled && (
            <Badge
              className="bg-[#E0B45A]/20 text-[#E0B45A] border-transparent font-mono text-xs gap-1.5 px-2.5 py-1 rounded-full animate-pulse"
            >
              <RotateCw className="size-3 animate-spin" />
              RECONNECTING ({reconnectAttempt}/5)...
            </Badge>
          )}

          {connectionStatus === "disconnected" && !isCancelled && (
            <Badge
              className="bg-[#E5736A]/20 text-[#E5736A] border-transparent font-mono text-xs gap-1.5 px-2.5 py-1 rounded-full"
            >
              <AlertTriangle className="size-3" />
              DISCONNECTED
            </Badge>
          )}
        </div>

        {/* Right: Metrics & Actions */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-3 font-mono text-xs">
            <div className="rounded-lg bg-[#15271F] border border-[rgba(183,201,173,0.16)] px-3 py-1.5">
              <span className="text-[#A9B8AD] mr-1.5">SPEND MATRIX</span>
              <span className="text-[#F7F7F2] font-semibold">$0.18</span>
              <span className="text-[#A9B8AD]"> / $0.50 cap</span>
            </div>

            <div className="rounded-lg bg-[#15271F] border border-[rgba(183,201,173,0.16)] px-3 py-1.5">
              <span className="text-[#A9B8AD] mr-1.5">ELAPSED</span>
              <span className="text-[#5FCB8A] font-semibold">
                {formatElapsed(elapsedSeconds)}
              </span>
            </div>

            <div className="rounded-lg bg-[#15271F] border border-[rgba(183,201,173,0.16)] px-3 py-1.5">
              <span className="text-[#A9B8AD] mr-1.5">SANDBOXES</span>
              <span className="text-[#F7F7F2] font-semibold">3 Isolated</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {!isCancelled ? (
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelClick}
                disabled={isCancelling}
                className="border-[rgba(229,115,106,0.3)] bg-transparent text-[#E5736A] hover:bg-[#E5736A]/10 text-xs h-8 px-3 rounded-md gap-1.5"
              >
                {isCancelling ? (
                  <>
                    <RotateCw className="size-3.5 animate-spin" />
                    Cancelling...
                  </>
                ) : (
                  <>
                    <XCircle className="size-3.5" />
                    Cancel Run
                  </>
                )}
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={onReturnToTasks}
                className="border-[rgba(183,201,173,0.3)] bg-transparent text-[#F7F7F2] text-xs h-8 px-3 rounded-md"
              >
                Return to Tasks
              </Button>
            )}
            <Button
              variant="secondary"
              size="sm"
              disabled
              className="bg-[#1B3228] text-[#A9B8AD] opacity-50 cursor-not-allowed text-xs h-8 px-3 rounded-md"
            >
              Run Pipeline
            </Button>
          </div>
        </div>
      </div>

      {/* Cancellation Banner (AC-2) */}
      {isCancelled && (
        <div className="rounded-xl bg-[#241414] border border-[#E5736A]/30 p-4 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <XCircle className="size-5 text-[#E5736A] shrink-0" />
            <div>
              <h4 className="text-sm font-semibold text-[#F7F7F2]">
                Run Cancelled by Maintainer
              </h4>
              <p className="text-xs text-[#A9B8AD]">
                Execution was halted upon user request. Historical logs and partial candidate artifacts have been preserved.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onInspectResults}
            className="text-xs border-[#E5736A]/40 text-[#F7F7F2] hover:bg-[#E5736A]/10 shrink-0"
          >
            Inspect Partial Results
          </Button>
        </div>
      )}

      {/* Disconnection Banner (AC-5) */}
      {connectionStatus === "disconnected" && !isCancelled && (
        <div className="rounded-xl bg-[#261E14] border border-[#E0B45A]/40 p-4 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <AlertTriangle className="size-5 text-[#E0B45A] shrink-0" />
            <div>
              <h4 className="text-sm font-semibold text-[#F7F7F2]">
                Event Stream Connection Lost
              </h4>
              <p className="text-xs text-[#A9B8AD]">
                Failed to reconnect after 5 attempts. Click retry to resume using the Last-Event-ID header.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              size="sm"
              onClick={handleRetryConnection}
              className="bg-[#E0B45A] text-black hover:bg-[#E0B45A]/90 text-xs gap-1.5"
            >
              <RotateCw className="size-3" />
              Retry Connection
            </Button>
          </div>
        </div>
      )}

      {/* Inline Error Banner with Monospace Traceback (AC-6) */}
      {errorDetail && (
        <div className="rounded-xl bg-[#221313] border border-[#E5736A]/40 p-5 mb-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="size-5 text-[#E5736A] shrink-0 mt-0.5" />
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs font-semibold text-[#E5736A] bg-[#E5736A]/10 px-2 py-0.5 rounded border border-[#E5736A]/20">
                    {errorDetail.code}
                  </span>
                  <span className="text-[11px] font-mono text-[#A9B8AD]">
                    {errorDetail.timestamp}
                  </span>
                </div>
                <h4 className="text-sm font-semibold text-[#F7F7F2] mb-1">
                  {errorDetail.message}
                </h4>
              </div>
            </div>
            {errorDetail.traceback && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowTraceback(!showTraceback)}
                className="text-xs text-[#A9B8AD] hover:text-[#F7F7F2] shrink-0"
              >
                {showTraceback ? "Hide Traceback" : "View Traceback"}
              </Button>
            )}
          </div>

          {showTraceback && errorDetail.traceback && (
            <div className="mt-3 pt-3 border-t border-[#E5736A]/20">
              <div className="flex items-center justify-between mb-1.5 text-xs text-[#A9B8AD]">
                <span className="font-mono text-[11px]">Execution Error Traceback:</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={copyTraceback}
                  className="h-6 px-2 text-[11px] text-[#A9B8AD] hover:text-[#F7F7F2] gap-1"
                >
                  {copiedTraceback ? <Check className="size-3 text-[#5FCB8A]" /> : <Copy className="size-3" />}
                  {copiedTraceback ? "Copied" : "Copy Traceback"}
                </Button>
              </div>
              <pre className="font-mono text-xs bg-[#0D1915] text-[#E5736A] p-3 rounded-lg overflow-x-auto border border-[#E5736A]/20 whitespace-pre-wrap">
                {errorDetail.traceback}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Main Content: Left Stages + Right Matrices */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Pipeline Stages (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <RotateCw className="size-4 text-[#A9B8AD]" />
                <h3 className="text-sm font-semibold text-[#F7F7F2]">
                  Pipeline Stages
                </h3>
              </div>
              <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-mono text-[11px] px-2 py-0.5">
                4/6 Complete
              </Badge>
            </div>

            <div className="flex flex-col gap-3">
              {/* Stage 1 */}
              <div className="rounded-xl bg-[#1B3228]/50 border border-[rgba(183,201,173,0.1)] p-3">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 text-xs font-medium text-[#F7F7F2]">
                    <CheckCircle2 className="size-3.5 text-[#5FCB8A]" />
                    <span>1. Baseline Check</span>
                  </div>
                  <Badge className="bg-[#5FCB8A]/20 text-[#5FCB8A] border-transparent text-[10px] font-mono px-1.5 py-0">
                    PASS
                  </Badge>
                </div>
                <p className="text-[11px] font-mono text-[#A9B8AD] pl-5.5">
                  42/42 tests pass on pinned commit 8a4f21d
                </p>
              </div>

              {/* Stage 2 */}
              <div className="rounded-xl bg-[#1B3228]/50 border border-[rgba(183,201,173,0.1)] p-3">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 text-xs font-medium text-[#F7F7F2]">
                    <CheckCircle2 className="size-3.5 text-[#5FCB8A]" />
                    <span>2. Upgrade Reproduction</span>
                  </div>
                  <Badge className="bg-[#5FCB8A]/20 text-[#5FCB8A] border-transparent text-[10px] font-mono px-1.5 py-0">
                    PASS
                  </Badge>
                </div>
                <p className="text-[11px] font-mono text-[#A9B8AD] pl-5.5">
                  Expected failure confirmed: ValidationError regex removed
                </p>
              </div>

              {/* Stage 3 */}
              <div className="rounded-xl bg-[#1B3228]/50 border border-[rgba(183,201,173,0.1)] p-3">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 text-xs font-medium text-[#F7F7F2]">
                    <CheckCircle2 className="size-3.5 text-[#5FCB8A]" />
                    <span>3. Allowlist Context</span>
                  </div>
                  <Badge className="bg-[#5FCB8A]/20 text-[#5FCB8A] border-transparent text-[10px] font-mono px-1.5 py-0">
                    PASS
                  </Badge>
                </div>
                <p className="text-[11px] font-mono text-[#A9B8AD] pl-5.5">
                  Bounded context: schemas.py:14-48, config.py:22-38
                </p>
              </div>

              {/* Stage 4 - Active */}
              <div className="rounded-xl bg-[#1B3228] border border-[#7FB3D5]/40 p-3 ring-1 ring-[#7FB3D5]/20">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 text-xs font-medium text-[#F7F7F2]">
                    <RotateCw className="size-3.5 text-[#7FB3D5] animate-spin" />
                    <span>4. Candidate Gen</span>
                  </div>
                  <Badge className="bg-[#7FB3D5]/20 text-[#7FB3D5] border-transparent text-[10px] font-mono px-1.5 py-0">
                    RUNNING
                  </Badge>
                </div>
                <p className="text-[11px] font-mono text-[#A9B8AD] pl-5.5">
                  NVIDIA Nemotron 70B via Nebius Token Factory (3 parallel shards)
                </p>
              </div>

              {/* Stage 5 - Queued */}
              <div className="rounded-xl bg-[#1B3228]/25 border border-[rgba(183,201,173,0.06)] p-3 opacity-60">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 text-xs font-medium text-[#A9B8AD]">
                    <Hourglass className="size-3.5" />
                    <span>5. Sandbox Verify</span>
                  </div>
                  <Badge className="bg-[#15271F] text-[#A9B8AD] border-[rgba(183,201,173,0.16)] text-[10px] font-mono px-1.5 py-0">
                    QUEUED
                  </Badge>
                </div>
                <p className="text-[11px] font-mono text-[#A9B8AD] pl-5.5">
                  ConTree Pytest container (ephemeral mount)
                </p>
              </div>

              {/* Stage 6 - Queued */}
              <div className="rounded-xl bg-[#1B3228]/25 border border-[rgba(183,201,173,0.06)] p-3 opacity-60">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 text-xs font-medium text-[#A9B8AD]">
                    <Clock className="size-3.5" />
                    <span>6. Preservation Proof</span>
                  </div>
                  <Badge className="bg-[#15271F] text-[#A9B8AD] border-[rgba(183,201,173,0.16)] text-[10px] font-mono px-1.5 py-0">
                    QUEUED
                  </Badge>
                </div>
                <p className="text-[11px] font-mono text-[#A9B8AD] pl-5.5">
                  AST check invariant: 0 test files modified
                </p>
              </div>
            </div>
          </Card>

          {/* Sandbox Host Health Card */}
          <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-4 text-xs font-mono">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[#A9B8AD] uppercase tracking-wider text-[11px]">
                SANDBOX HOST
              </span>
              <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent text-[10px] px-2 py-0">
                HEALTHY
              </Badge>
            </div>
            <div className="flex flex-col gap-1.5 text-[#A9B8AD]">
              <div className="flex justify-between">
                <span>Cluster:</span>
                <span className="text-[#F7F7F2]">nebius-eu-west-1a</span>
              </div>
              <div className="flex justify-between">
                <span>Runtime:</span>
                <span className="text-[#F7F7F2]">firecracker-microvm</span>
              </div>
              <div className="flex justify-between">
                <span>Memory Cgroup:</span>
                <span className="text-[#F7F7F2]">1.2 GB / 4.0 GB</span>
              </div>
            </div>
          </Card>
        </div>

        {/* Right: Candidate Matrices (8 cols) */}
        <div className="lg:col-span-8 flex flex-col gap-5">
          {/* Section Header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-[#F7F7F2]">
                Active Candidate Matrices
              </h2>
              <p className="text-xs text-[#A9B8AD] mt-0.5">
                Three parallel migration strategies executing in ephemeral clean
                containers.
              </p>
            </div>
            <div className="text-xs font-mono text-[#A9B8AD]">
              STRATEGY SORT:{" "}
              <span className="text-[#F7F7F2]">Confidence Metric</span>
            </div>
          </div>

          {/* Candidate A - Selected & Winning */}
          <Card className="rounded-[20px] bg-[#15271F] border-l-4 border-l-[#5FCB8A] border-y border-r border-[rgba(183,201,173,0.3)] p-5">
            {/* Header: Badge, Title, Time, Test Count */}
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <Badge className="bg-[#5FCB8A]/20 text-[#5FCB8A] border-transparent font-mono text-xs font-semibold px-2 py-0.5">
                  SELECTED / PASS
                </Badge>
                <h3 className="text-sm font-semibold text-[#F7F7F2]">
                  Candidate A{" "}
                  <span className="font-normal text-[#A9B8AD]">
                    (Direct ConfigDict &amp; Field(pattern=...))
                  </span>
                </h3>
              </div>

              <div className="flex items-center gap-3 font-mono text-xs text-[#A9B8AD]">
                <div className="flex items-center gap-1">
                  <Clock className="size-3.5" />
                  <span>24.2s</span>
                </div>
                <div className="flex items-center gap-1 text-[#5FCB8A]">
                  <CheckCircle2 className="size-3.5" />
                  <span>42 passed · 0 failed</span>
                </div>
              </div>
            </div>

            {/* Strategy description & diff summary */}
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs mb-3 text-[#A9B8AD]">
              <div className="flex items-center gap-1.5 text-[#F7F7F2]">
                <CheckCircle2 className="size-3.5 text-[#5FCB8A] shrink-0" />
                <span>
                  Direct schema transformation using native Pydantic V2{" "}
                  <code className="text-[#5FCB8A] font-mono text-[11px]">
                    model_config = ConfigDict(populate_by_name=True)
                  </code>
                </span>
              </div>
              <span className="font-mono text-[#5FCB8A]">
                Delta: +18 lines -14 lines
              </span>
            </div>

            {/* Terminal Log Box */}
            <div className="rounded-xl bg-[#0D1915] border border-[rgba(183,201,173,0.16)] overflow-hidden mb-4">
              {/* Terminal header */}
              <div className="flex items-center justify-between bg-[#11221B] px-3.5 py-2 border-b border-[rgba(183,201,173,0.12)]">
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="size-2 rounded-full bg-[#E5736A]" />
                    <span className="size-2 rounded-full bg-[#E0B45A]" />
                    <span className="size-2 rounded-full bg-[#5FCB8A]" />
                  </div>
                  <span className="font-mono text-xs text-[#A9B8AD] ml-1">
                    container-eval-candidate-a.log
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1 text-[11px] font-mono text-[#5FCB8A]">
                    <span className="size-1.5 rounded-full bg-[#5FCB8A]" />
                    STREAM COMPLETED
                  </div>
                  <button
                    type="button"
                    onClick={copyLogToClipboard}
                    className="text-[#A9B8AD] hover:text-[#F7F7F2] transition-colors p-1"
                    title="Copy logs"
                    aria-label="Copy logs"
                  >
                    {copiedLog ? (
                      <Check className="size-3.5 text-[#5FCB8A]" />
                    ) : (
                      <Copy className="size-3.5" />
                    )}
                  </button>
                </div>
              </div>

              {/* Terminal log text */}
              <div className="p-4 font-mono text-[12px] leading-relaxed text-[#A9B8AD] overflow-x-auto whitespace-pre">
                {candidateALog.split("\n").map((line, idx) => {
                  const isPass = line.includes("PASSED") || line.includes("successfully") || line.includes("42 passed");
                  return (
                    <div
                      key={idx}
                      className={isPass ? "text-[#5FCB8A] font-medium" : ""}
                    >
                      {line}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Candidate A Bottom Action Row: Readiness + Primary Button */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
              <div className="font-mono text-xs text-[#A9B8AD]">
                <span>Commit Readiness: </span>
                <span className="text-[#5FCB8A] font-medium">100%</span>
                <span className="mx-2">·</span>
                <span>AST Preservation Hash: </span>
                <span className="text-[#F7F7F2]">sha256:d8a2...3f</span>
              </div>

              {/* The single primary Sage button for this view per DESIGN.md */}
              <Button
                onClick={onInspectResults}
                className="h-10 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-xs px-4 rounded-lg flex items-center gap-2 cursor-pointer shadow-none"
              >
                <span>Inspect Results &amp; Diff</span>
                <ArrowRight className="size-4" />
              </Button>
            </div>
          </Card>

          {/* Candidate B - Flaky / Rejected */}
          <Card className="rounded-[20px] bg-[#15271F]/80 border border-[rgba(183,201,173,0.12)] p-5 opacity-85">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <Badge className="bg-[#E0B45A]/20 text-[#E0B45A] border-transparent font-mono text-xs font-semibold px-2 py-0.5">
                  FLAKY / REJECTED
                </Badge>
                <h3 className="text-sm font-semibold text-[#F7F7F2]">
                  Candidate B{" "}
                  <span className="font-normal text-[#A9B8AD]">
                    (pydantic.v1 compatibility shim)
                  </span>
                </h3>
              </div>

              <div className="flex items-center gap-3 font-mono text-xs text-[#A9B8AD]">
                <div className="flex items-center gap-1">
                  <Clock className="size-3.5" />
                  <span>19.8s</span>
                </div>
                <div className="flex items-center gap-1 text-[#E0B45A]">
                  <AlertTriangle className="size-3.5" />
                  <span>38 passed · 4 failed</span>
                </div>
              </div>
            </div>

            {/* Warning summary box */}
            <div className="rounded-lg bg-[#0D1915] p-3 border border-[rgba(224,180,90,0.2)] text-xs mb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[#A9B8AD]">
                  <AlertTriangle className="size-3.5 text-[#E0B45A]" />
                  <span>
                    Summary: 38 passed · 4 failed (
                    <span className="text-[#E0B45A]">DeprecationWarning</span>{" "}
                    treated as error by pytest flags)
                  </span>
                </div>
                <span className="font-mono text-[#E5736A] font-semibold text-[11px]">
                  FAILED ASSERTION IN STRICT CI
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-[#A9B8AD]">
              <span>
                Strategy rejected: Temporary bridge creates technical debt and
                triggers runtime warnings
              </span>
              <button
                type="button"
                onClick={() => setShowStackB(!showStackB)}
                className="flex items-center gap-1 text-[#F7F7F2] hover:text-[#B7C9AD] font-mono text-[11px]"
              >
                <span>View Error Stack</span>
                {showStackB ? (
                  <ChevronUp className="size-3.5" />
                ) : (
                  <ChevronDown className="size-3.5" />
                )}
              </button>
            </div>

            {showStackB && (
              <div className="mt-3 rounded-lg bg-[#0D1915] p-3 font-mono text-[11px] text-[#E5736A] border border-[rgba(229,115,106,0.2)]">
                <code>
                  tests/test_api.py:44: PydanticDeprecatedSince20: The
                  `pydantic.v1` module is deprecated. Use Pydantic V2 core models
                  instead. PytestConfigError: warnings are treated as errors
                  (-W error).
                </code>
              </div>
            )}
          </Card>

          {/* Candidate C - Fail */}
          <Card className="rounded-[20px] bg-[#15271F]/60 border border-[rgba(183,201,173,0.08)] p-5 opacity-70">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <Badge className="bg-[#E5736A]/20 text-[#E5736A] border-transparent font-mono text-xs font-semibold px-2 py-0.5">
                  FAIL
                </Badge>
                <h3 className="text-sm font-semibold text-[#F7F7F2]">
                  Candidate C{" "}
                  <span className="font-normal text-[#A9B8AD]">
                    (Pydantic V2 Migration Codegen)
                  </span>
                </h3>
              </div>

              <div className="flex items-center gap-3 font-mono text-xs text-[#A9B8AD]">
                <div className="flex items-center gap-1">
                  <Clock className="size-3.5" />
                  <span>31.1s</span>
                </div>
                <div className="flex items-center gap-1 text-[#E5736A]">
                  <XCircle className="size-3.5" />
                  <span>0 passed · 1 SyntaxError</span>
                </div>
              </div>
            </div>

            {/* Error box */}
            <div className="rounded-lg bg-[#0D1915] p-3 border border-[rgba(229,115,106,0.2)] text-xs mb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[#A9B8AD]">
                  <XCircle className="size-3.5 text-[#E5736A]" />
                  <span>
                    Summary: SyntaxError in generated schema patch at{" "}
                    <code className="text-[#E5736A]">schemas.py:34</code>
                  </span>
                </div>
                <span className="font-mono text-[#E5736A] font-semibold text-[11px]">
                  ABORTED AT VERIFICATION
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-[#A9B8AD]">
              <span>
                Strategy rejected: Automated codegen generated malformed
                trailing comma in ModelConfig tuple
              </span>
              <span className="font-mono text-[11px] text-[#A9B8AD]">
                Discarded from ranking pool
              </span>
            </div>
          </Card>

          {/* Proof of Invariant Preservation Card */}
          <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-[#1B3228] p-2 border border-[rgba(183,201,173,0.16)]">
                <ShieldCheck className="size-5 text-[#5FCB8A]" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-[#F7F7F2]">
                  Proof of Invariant Preservation
                </h4>
                <p className="text-xs text-[#A9B8AD]">
                  Strict verification guarantee: test suite integrity is
                  cryptographically preserved.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4 font-mono text-xs">
              <div>
                <span className="text-[#A9B8AD] mr-1">Modified Tests:</span>
                <span className="text-[#5FCB8A] font-semibold">0 files</span>
              </div>
              <div>
                <span className="text-[#A9B8AD] mr-1">Boundary Leak:</span>
                <span className="text-[#5FCB8A] font-semibold">0 violations</span>
              </div>
              <div>
                <span className="text-[#A9B8AD] mr-1">Sandbox Isolation:</span>
                <span className="text-[#5FCB8A] font-semibold">Ephemeral-OK</span>
              </div>
            </div>
          </Card>

          {/* Developer Simulation Controls (AC-8) */}
          <Card className="rounded-[20px] bg-[#102019] border border-[rgba(183,201,173,0.16)] p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-[#1B3228] p-2 border border-[rgba(183,201,173,0.16)]">
                <Wrench className="size-5 text-[#E0B45A]" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-[#F7F7F2]">
                  Developer Simulation Controls
                </h4>
                <p className="text-xs text-[#A9B8AD]">
                  Simulate network disconnects, retry ceiling timeouts, and synthetic engine errors offline.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSimulateDisconnect}
                className="text-xs h-8 px-3 border-[rgba(183,201,173,0.24)] bg-[#15271F] text-[#F7F7F2] hover:bg-[#1B3228] gap-1.5"
              >
                <RotateCw className="size-3" />
                Disconnect Stream
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleSimulateExceededRetries}
                className="text-xs h-8 px-3 border-[#E0B45A]/30 bg-[#15271F] text-[#E0B45A] hover:bg-[#E0B45A]/10 gap-1.5"
              >
                <AlertTriangle className="size-3" />
                Retry Limit
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleSimulateError}
                className="text-xs h-8 px-3 border-[#E5736A]/30 bg-[#15271F] text-[#E5736A] hover:bg-[#E5736A]/10 gap-1.5"
              >
                <XCircle className="size-3" />
                Engine Error
              </Button>
              {(connectionStatus !== "connected" || errorDetail !== null) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearSimulation}
                  className="text-xs h-8 px-3 text-[#A9B8AD] hover:text-[#F7F7F2] gap-1.5"
                >
                  <RefreshCw className="size-3" />
                  Reset
                </Button>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
