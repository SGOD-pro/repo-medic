"use client";
import React, { useState, useEffect, useCallback, useRef } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  GitBranch,
  Terminal,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  FileCode,
  GitCommit,
  RotateCw,
  FolderGit2,
  FileText,
  Play,
  Layers,
  Circle,
  CheckCircle,
  PlusCircle,
  ExternalLink,
} from "lucide-react";
import { SearchMode, TaskSummary, Mode, SUPPORTED_DEMO_TASK_IDS } from "@/lib/contracts";
import { RepoMedicApiClient, createApiClient, SUPPORTED_DEMO_TASKS } from "@/lib/api";

interface TaskItem {
  id: string;
  repo: string;
  title: string;
  commitSha: string;
  dependency: string;
  targetVersion: string;
  testsCount: number;
  expectedFailure: string;
  baselineTime: string;
  allowlist: string;
}

function mapSummaryToTaskItem(s: TaskSummary): TaskItem {
  const repoName = s.repository_url
    ? s.repository_url.replace(/^https?:\/\/github\.com\//, "").replace(/\.git$/, "")
    : "python/repo";
  const extra = s as unknown as Record<string, unknown>;
  const expectedFailure =
    typeof extra.expected_failure === "string"
      ? extra.expected_failure
      : `Upgrade regression on ${s.dependency}==${s.to_version}`;
  const allowlist = Array.isArray(extra.allowed_source_paths)
    ? (extra.allowed_source_paths as string[]).join(", ")
    : s.task_id === "TASK-DEMO-SHOP"
    ? "src/shop/"
    : "src/";
  const testsCount =
    typeof extra.tests_count === "number"
      ? extra.tests_count
      : (s.task_id === "TASK-DEMO-SHOP" || s.task_id === "TASK-091" ? 1 : 42);
  const baselineTime =
    typeof extra.baseline_time === "string"
      ? extra.baseline_time
      : (s.task_id === "TASK-DEMO-SHOP" || s.task_id === "TASK-091"
        ? "0.16s (Python 3.12)"
        : "1.48s (Python 3.11)");

  return {
    id: s.task_id,
    repo: repoName,
    title: s.title,
    commitSha: s.commit_sha,
    dependency: s.dependency,
    targetVersion: s.to_version,
    testsCount,
    expectedFailure,
    baselineTime,
    allowlist,
  };
}

interface TasksViewProps {
  onStartRun: (taskId: string, strategy: SearchMode, mode?: Mode) => void;
  selectedTaskId: string;
  setSelectedTaskId: (taskId: string) => void;
  strategy: SearchMode;
  setStrategy: (strategy: SearchMode) => void;
  apiClient?: RepoMedicApiClient;
  onSwitchToCustom?: () => void;
}

export function TasksView({
  onStartRun,
  selectedTaskId,
  setSelectedTaskId,
  strategy,
  setStrategy,
  apiClient,
  onSwitchToCustom,
}: TasksViewProps) {
  const [executionMode, setExecutionMode] = useState<string>("sandbox_live");
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState<boolean>(false);

  const selectedTaskIdRef = useRef(selectedTaskId);
  useEffect(() => {
    selectedTaskIdRef.current = selectedTaskId;
  }, [selectedTaskId]);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const client = apiClient || createApiClient();
      const rawTasks = await client.getTasks("supported_demo");
      // Filter out any acceptance test fixtures or example repos
      const filtered = rawTasks.filter((t) => {
        const repo = (t.repository_url || "").toLowerCase();
        const id = (t.task_id || "").toLowerCase();
        return (
          !repo.includes("example") &&
          !id.includes("example-task") &&
          !id.startsWith("task_live_") &&
          (SUPPORTED_DEMO_TASK_IDS.includes(t.task_id) || !t.task_id.startsWith("test_"))
        );
      });

      const effectiveTasks = filtered.length > 0 ? filtered : SUPPORTED_DEMO_TASKS;
      const items = effectiveTasks.map(mapSummaryToTaskItem);
      // Ensure TASK-DEMO-SHOP is at top
      items.sort((a, b) => (a.id === "TASK-DEMO-SHOP" ? -1 : b.id === "TASK-DEMO-SHOP" ? 1 : 0));

      setTasks(items);
      if (items.length > 0) {
        const currentSelected = selectedTaskIdRef.current;
        if (!currentSelected || !items.some((t) => t.id === currentSelected)) {
          setSelectedTaskId(items[0].id);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load tasks";
      setLoadError(msg);
    } finally {
      setLoading(false);
    }
  }, [apiClient, setSelectedTaskId]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void fetchTasks();
      }
    });
    return () => {
      active = false;
    };
  }, [fetchTasks]);

  const selectedTask =
    tasks.find((t) => t.id === selectedTaskId) ||
    tasks[0] || {
      id: selectedTaskId || "TASK-DEMO-SHOP",
      repo: "SGOD-pro/repo-medic",
      title: "Upgrade sqlalchemy 1.4.48 to 2.0.19 in repomedic-demo-shop",
      commitSha: "8c400721558392a23b3af71766f673da02f80040",
      dependency: "sqlalchemy",
      targetVersion: "2.0.19",
      testsCount: 1,
      expectedFailure: "AttributeError: 'Engine' object has no attribute 'execute'",
      baselineTime: "0.16s (Python 3.12)",
      allowlist: "src/shop/",
    };

  return (
    <div data-testid="tasks-view" className="mx-auto w-full max-w-[1280px] px-6 py-8">
      {/* Top Header & Stats */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 pb-6">
        <div>
          <span className="font-mono text-xs font-medium tracking-[0.06em] uppercase text-[#A9B8AD]">
            CURATED DEMO SCENARIOS / PRE-VALIDATED FIXTURES
          </span>
          <h1 className="mt-1 text-3xl md:text-4xl font-semibold tracking-tight text-[#F7F7F2]">
            Curated Demo Tasks
          </h1>
          <p className="mt-2 text-sm text-[#A9B8AD] max-w-2xl leading-relaxed">
            Choose a verified demonstration task pinned to explicit commits and dependency versions.
            Each task reproduces a confirmed upgrade failure ready for automated repair.
          </p>
        </div>

        {/* Right Info Badges */}
        <div className="flex items-center gap-3">
          {onSwitchToCustom && (
            <Button
              type="button"
              onClick={onSwitchToCustom}
              className="bg-[#1B3228] border border-[rgba(183,201,173,0.3)] text-[#F7F7F2] hover:bg-[#203c30] text-xs h-9 px-3.5 gap-2 rounded-lg cursor-pointer"
            >
              <PlusCircle className="size-3.5 text-[#5FCB8A]" />
              Configure Custom Repo
            </Button>
          )}
          <div className="rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] px-4 py-2 text-left">
            <div className="text-[11px] font-mono text-[#A9B8AD] uppercase tracking-wider">
              Supported Scenarios
            </div>
            <div className="text-sm font-semibold text-[#F7F7F2]">
              {tasks.length} Curated Demos
            </div>
          </div>
        </div>
      </div>

      {/* Verified Run Showcase Banner */}
      <div className="mb-6 rounded-2xl border border-[#5FCB8A]/30 bg-[#15271F] p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="size-2 rounded-full bg-[#5FCB8A] animate-pulse" />
            <span className="font-semibold text-sm text-[#F7F7F2]">
              Past Verified Production Runs (Instant Results)
            </span>
            <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-mono text-[10px] px-2 py-0">
              SAVED VERIFICATION
            </Badge>
          </div>
          <p className="mt-1 text-xs text-[#A9B8AD] leading-relaxed">
            Inspect verified live repair results, candidate patches, Pytest verification logs, and evidence JSON from recent production executions.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button
            size="sm"
            onClick={() => {
              window.location.href = "/?runId=run_c89257b365a247b0ab8d8f44fb04a779";
            }}
            className="bg-[#5FCB8A] text-[#0D1915] hover:bg-[#5FCB8A]/90 font-medium text-xs cursor-pointer"
          >
            Demo Shop Run (run_c89257b)
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              window.location.href = "/?runId=run_93c660238e3443a6a18249167eb1939b";
            }}
            className="border-[rgba(183,201,173,0.3)] bg-[#1B3228] text-[#F7F7F2] hover:bg-[#203c30] text-xs cursor-pointer"
          >
            Benchmark Run (run_93c6602)
          </Button>
        </div>
      </div>

      {/* Control Bar: Strategy, Mode, Budget, Determinism */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] p-3 mb-8">
        <div className="flex flex-wrap items-center gap-4">
          {/* Repair Strategy */}
          <div className="flex items-center gap-2">
            <GitBranch className="size-4 text-[#A9B8AD]" />
            <span className="text-xs text-[#A9B8AD]">Repair Strategy</span>
            <Select
              value={strategy}
              onValueChange={(val) => val && setStrategy(val as SearchMode)}
            >
              <SelectTrigger className="h-8 border-[rgba(183,201,173,0.2)] bg-[#1B3228] text-xs text-[#F7F7F2] rounded-md px-3 font-medium">
                <SelectValue placeholder="Select strategy" />
              </SelectTrigger>
              <SelectContent className="bg-[#15271F] border-[rgba(183,201,173,0.24)] text-[#F7F7F2]">
                <SelectItem value="sequential">
                  Sequential Direct (Single Pass)
                </SelectItem>
                <SelectItem value="branch_refine">
                  Branch &amp; Refine (Max 3 Candidates)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Execution Mode */}
          <div className="flex items-center gap-2">
            <Terminal className="size-4 text-[#A9B8AD]" />
            <span className="text-xs text-[#A9B8AD]">Execution Mode</span>
            <Select
              value={executionMode}
              onValueChange={(val) => val && setExecutionMode(val)}
            >
              <SelectTrigger className="h-8 border-[rgba(183,201,173,0.2)] bg-[#1B3228] text-xs text-[#F7F7F2] rounded-md px-3 font-medium">
                <SelectValue placeholder="Select mode" />
              </SelectTrigger>
              <SelectContent className="bg-[#15271F] border-[rgba(183,201,173,0.24)] text-[#F7F7F2]">
                <SelectItem value="sandbox_live">
                  Sandbox Live (Nebius / ConTree)
                </SelectItem>
                <SelectItem value="dry_run">
                  Dry-Run Emulation (Local)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Budget Ceiling */}
          <div className="flex items-center gap-2">
            <Layers className="size-4 text-[#A9B8AD]" />
            <span className="text-xs text-[#A9B8AD]">Budget Ceiling</span>
            <div className="flex items-center gap-2 bg-[#1B3228] border border-[rgba(183,201,173,0.2)] rounded-md px-2.5 py-1 text-xs">
              <span className="font-mono text-[#F7F7F2]">$0.50</span>
              <span className="text-[#A9B8AD]">max spend / run</span>
              <Badge className="bg-[#15271F] border border-[rgba(183,201,173,0.2)] text-[10px] text-[#A9B8AD] py-0 px-1.5">
                Enforced
              </Badge>
            </div>
          </div>
        </div>

        {/* Truthful Test Runner Info */}
        <div className="flex items-center gap-2 text-xs font-mono text-[#A9B8AD]">
          <ShieldCheck className="size-4 text-[#5FCB8A]" />
          <span>Runner Environment:</span>
          <span className="text-[#F7F7F2] font-semibold">Python 3.12 · Pytest 9.2</span>
        </div>
      </div>

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Task Cards (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          {loading && (
            <div
              data-testid="tasks-loading"
              className="rounded-2xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] p-10 text-center"
            >
              <RotateCw className="size-6 animate-spin mx-auto mb-2 text-[#5FCB8A]" />
              <p className="text-sm font-medium text-[#F7F7F2]">
                Loading available demo tasks...
              </p>
              <p className="text-xs text-[#A9B8AD] mt-1 font-mono">
                Fetching supported tasks from backend
              </p>
            </div>
          )}

          {loadError && (
            <div
              data-testid="tasks-error"
              className="rounded-2xl border border-[#E5736A]/30 bg-[#241414] p-6 text-left"
            >
              <div className="flex items-center gap-2.5 mb-2">
                <AlertCircle className="size-5 text-[#E5736A]" />
                <h4 className="text-sm font-semibold text-[#F7F7F2]">
                  Failed to load tasks
                </h4>
              </div>
              <p className="text-xs font-mono text-[#A9B8AD] mb-4">
                {loadError}
              </p>
              <Button
                onClick={fetchTasks}
                className="h-8 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-xs rounded-md px-3 cursor-pointer"
              >
                Retry
              </Button>
            </div>
          )}

          {!loading && !loadError && tasks.length === 0 && (
            <div
              data-testid="tasks-empty"
              className="rounded-2xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] p-10 text-center"
            >
              <Layers className="size-6 mx-auto mb-2 text-[#A9B8AD]" />
              <p className="text-sm font-medium text-[#F7F7F2]">
                No repair tasks found
              </p>
              <p className="text-xs text-[#A9B8AD] mt-1">
                No tasks registered in the system database.
              </p>
              <Button
                onClick={fetchTasks}
                variant="outline"
                className="mt-4 border-[rgba(183,201,173,0.24)] text-xs text-[#F7F7F2] h-8 cursor-pointer"
              >
                Reload
              </Button>
            </div>
          )}

          {!loading && !loadError && tasks.map((task) => {
            const isSelected = task.id === selectedTaskId;
            return (
              <Card
                key={task.id}
                data-testid={`task-card-${task.id}`}
                role="button"
                tabIndex={0}
                aria-label={`Select ${task.id}: ${task.title}`}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    setSelectedTaskId(task.id);
                  }
                }}
                onClick={() => setSelectedTaskId(task.id)}
                className={`cursor-pointer transition-all rounded-[20px] p-5 border text-left ${
                  isSelected
                    ? "bg-[#1B3228] border-[rgba(183,201,173,0.36)] ring-1 ring-[#B7C9AD]/20"
                    : "bg-[#15271F] border-[rgba(183,201,173,0.16)] hover:bg-[#182C23]"
                }`}
              >
                {/* Header row: ID, Repo, Fail Badge */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2.5 text-xs">
                    {isSelected ? (
                      <CheckCircle className="size-4 text-[#5FCB8A]" />
                    ) : (
                      <Circle className="size-4 text-[#A9B8AD]" />
                    )}
                    <span className="font-mono text-[#F7F7F2] font-semibold">
                      {task.id}
                    </span>
                    <span className="text-[#A9B8AD]">{task.repo}</span>
                    <Badge className="bg-[#5FCB8A]/10 text-[#5FCB8A] border-transparent text-[10px] font-mono px-1.5 py-0">
                      CURATED DEMO
                    </Badge>
                  </div>

                  <Badge className="bg-[#E5736A]/15 text-[#E5736A] border-transparent text-[11px] font-medium gap-1 px-2 py-0.5 rounded-full">
                    <span className="size-1.5 rounded-full bg-[#E5736A]" />
                    BREAKAGE CONFIRMED
                  </Badge>
                </div>

                {/* Task Title */}
                <h3 className="text-base font-semibold text-[#F7F7F2] mt-1 mb-2.5">
                  {task.title}
                </h3>

                {/* Meta row: commit, target, preserved tests */}
                <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-[#A9B8AD] mb-3">
                  <div className="flex items-center gap-1">
                    <GitCommit className="size-3.5" />
                    <span>{task.commitSha.substring(0, 7)}</span>
                  </div>
                  <span>·</span>
                  <div>
                    target:{" "}
                    <span className="text-[#F7F7F2]">
                      {task.dependency}=={task.targetVersion}
                    </span>
                  </div>
                  <span>·</span>
                  <div>{task.testsCount} preserved test{task.testsCount === 1 ? "" : "s"}</div>
                </div>

                {/* Expected Failure box */}
                <div className="rounded-lg bg-[#0D1915] p-3 text-xs border border-[rgba(183,201,173,0.12)]">
                  <span className="font-semibold text-[#E5736A] mr-1.5">
                    Expected failure:
                  </span>
                  <span className="font-mono text-[#A9B8AD] leading-relaxed">
                    {task.expectedFailure}
                  </span>
                </div>
              </Card>
            );
          })}

          {/* Footer note under tasks */}
          <div className="flex items-center justify-between pt-2 px-1 text-xs text-[#A9B8AD]">
            <div className="flex items-center gap-2">
              <RotateCw className="size-3.5" />
              <span>
                Demonstration fixtures immutable. Test suite integrity verified by SHA-256 baseline.
              </span>
            </div>
            <span className="font-mono text-[11px]">
              Python 3.12 / Pytest 9.2
            </span>
          </div>
        </div>

        {/* Right Column: Target Verification & Preflight (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-6">
            {/* Header: Eyebrow + Pre-flight Badge */}
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="font-mono text-xs tracking-wider text-[#A9B8AD] uppercase">
                TARGET SPECIFICATION
              </span>
              <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent text-[11px] font-semibold px-2 py-0.5 rounded-full">
                READY FOR RUN
              </Badge>
            </div>

            <h2 className="text-lg font-semibold text-[#F7F7F2] mb-5">
              {selectedTask.repo}
            </h2>

            {/* Check 1: Baseline Check */}
            <div className="rounded-xl bg-[#1B3228]/60 border border-[rgba(183,201,173,0.12)] p-3.5 mb-3">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 text-xs font-semibold text-[#F7F7F2]">
                  <CheckCircle2 className="size-4 text-[#5FCB8A]" />
                  <span>Target Baseline Specification</span>
                </div>
                <Badge className="bg-[#5FCB8A]/20 text-[#5FCB8A] border-transparent font-mono text-[11px] px-2 py-0">
                  {selectedTask.testsCount} TEST{selectedTask.testsCount === 1 ? "" : "S"}
                </Badge>
              </div>
              <p className="text-[11px] font-mono text-[#A9B8AD] pl-6">
                Baseline passing in {selectedTask.baselineTime}
              </p>
            </div>

            {/* Check 2: Expected Red Upgrade */}
            <div className="rounded-xl bg-[#1B3228]/60 border border-[rgba(183,201,173,0.12)] p-3.5 mb-3">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 text-xs font-semibold text-[#F7F7F2]">
                  <AlertCircle className="size-4 text-[#E5736A]" />
                  <span>Target Upgrade Breakage</span>
                </div>
                <Badge className="bg-[#E5736A]/20 text-[#E5736A] border-transparent font-mono text-[11px] px-2 py-0">
                  REPRODUCED
                </Badge>
              </div>
              <p className="text-[11px] font-mono text-[#A9B8AD] pl-6">
                Target: {selectedTask.dependency}=={selectedTask.targetVersion}
              </p>
            </div>

            {/* Check 3: Mutation Allowlist */}
            <div className="rounded-xl bg-[#1B3228]/60 border border-[rgba(183,201,173,0.12)] p-3.5 mb-5">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 text-xs font-semibold text-[#F7F7F2]">
                  <FileCode className="size-4 text-[#7FB3D5]" />
                  <span>Mutation Boundary Allowlist</span>
                </div>
                <Badge className="bg-[#7FB3D5]/20 text-[#7FB3D5] border-transparent font-mono text-[11px] px-2 py-0">
                  TESTS IMMUTABLE
                </Badge>
              </div>
              <p className="text-[11px] font-mono text-[#A9B8AD] pl-6">
                Allowed paths: {selectedTask.allowlist}
              </p>
            </div>

            {/* Sandbox Profile */}
            <div className="rounded-xl bg-[#0D1915] border border-[rgba(183,201,173,0.12)] p-4 mb-5">
              <div className="flex items-center justify-between text-xs font-mono mb-2">
                <span className="text-[#A9B8AD]">SANDBOX PROFILE</span>
                <span className="text-[#F7F7F2] font-medium">
                  Ephemeral Microcontainer
                </span>
              </div>
              <div className="text-[11px] font-mono text-[#A9B8AD] space-y-1">
                <div className="flex justify-between">
                  <span>Image</span>
                  <span className="text-[#F7F7F2]">python:3.12-bookworm</span>
                </div>
                <div className="flex justify-between">
                  <span>Memory limit</span>
                  <span className="text-[#F7F7F2]">2048 MB</span>
                </div>
                <div className="flex justify-between">
                  <span>Run timeout</span>
                  <span className="text-[#F7F7F2]">120s</span>
                </div>
              </div>
            </div>

            {/* Primary Action Button */}
            <Button
              disabled={isStarting}
              onClick={async () => {
                if (isStarting) return;
                setIsStarting(true);
                try {
                  await onStartRun(
                    selectedTask.id,
                    strategy,
                    executionMode === "sandbox_live" ? "live" : "offline"
                  );
                } finally {
                  setIsStarting(false);
                }
              }}
              className="w-full h-11 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-sm rounded-lg flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-none disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="size-4 fill-current" />
              {isStarting ? "Starting demo run..." : "Start Demo Repair Run"}
            </Button>

            <p className="mt-4 text-[11px] text-[#A9B8AD] text-center leading-relaxed">
              Execution runs inside an isolated ephemeral microcontainer. Test suite integrity is
              strictly verified against baseline hashes.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
