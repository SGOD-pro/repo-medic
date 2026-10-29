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
  AlertCircle,
  GitCommit,
  RotateCw,
  Play,
  Layers,
  Circle,
  CheckCircle,
  PlusCircle,
} from "lucide-react";
import { SearchMode, TaskSummary, Mode, APPROVED_DEMO_TASK_IDS } from "@/lib/contracts";
import { RepoMedicApiClient, createApiClient } from "@/lib/api";

interface TaskItem {
  id: string;
  repo: string;
  title: string;
  commitSha: string;
  dependency: string;
  targetVersion: string;
  testsCount: number | null;
  expectedFailure: string;
  baselineTime: string;
  allowlist: string;
}

function mapSummaryToTaskItem(s: TaskSummary): TaskItem {
  const repoName = s.repository_url
    ? s.repository_url.replace(/^https?:\/\/github\.com\//, "").replace(/\.git$/, "")
    : "Unavailable";
  const expectedFailure =
    typeof s.expected_failure === "string" && s.expected_failure.trim()
      ? s.expected_failure.trim()
      : "Unavailable";
  const allowlist =
    Array.isArray(s.allowed_source_paths) && s.allowed_source_paths.length > 0
      ? s.allowed_source_paths.join(", ")
      : "Unavailable";
  const testsCount =
    typeof s.tests_count === "number" && !isNaN(s.tests_count)
      ? s.tests_count
      : null;
  const baselineTime =
    typeof s.baseline_time === "string" && s.baseline_time.trim()
      ? s.baseline_time.trim()
      : "Unavailable";

  return {
    id: s.task_id,
    repo: repoName,
    title: s.title,
    commitSha: s.commit_sha || "Unavailable",
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
  onViewSavedRun?: (runId: string) => void;
}

export function TasksView({
  onStartRun,
  selectedTaskId,
  setSelectedTaskId,
  strategy,
  setStrategy,
  apiClient,
  onSwitchToCustom,
  onViewSavedRun,
}: TasksViewProps) {
  const [executionMode, setExecutionMode] = useState<string>("dry_run");
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
        const id = (t.task_id || "");
        return (
          !repo.includes("example") &&
          !id.includes("example-task") &&
          !id.startsWith("task_live_") &&
          !id.startsWith("test_") &&
          APPROVED_DEMO_TASK_IDS.includes(id)
        );
      });

      const items = filtered.map(mapSummaryToTaskItem);
      // Ensure TASK-DEMO-SHOP is at top
      items.sort((a, b) => (a.id === "TASK-DEMO-SHOP" ? -1 : b.id === "TASK-DEMO-SHOP" ? 1 : 0));

      setTasks(items);
      if (items.length > 0) {
        const currentSelected = selectedTaskIdRef.current;
        if (!currentSelected || !items.some((t) => t.id === currentSelected)) {
          setSelectedTaskId(items[0].id);
        }
      } else {
        setSelectedTaskId("");
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

  const selectedTask: TaskItem | null =
    tasks.find((t) => t.id === selectedTaskId) || tasks[0] || null;

  const handleOpenSaved = (runId: string) => {
    if (onViewSavedRun) {
      onViewSavedRun(runId);
    } else {
      window.location.search = `?runId=${runId}`;
    }
  };

  const handleStart = async () => {
    if (isStarting || !selectedTask) return;
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
  };

  return (
    <div data-testid="tasks-view" className="mx-auto w-full max-w-[1280px] px-4 sm:px-6 py-6 sm:py-8 space-y-6">
      {/* Top Header & Navigation */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <span className="font-mono text-xs font-medium tracking-[0.06em] uppercase text-[#A9B8AD]">
            CURATED DEMO SCENARIOS / PRE-VALIDATED FIXTURES
          </span>
          <h1 className="mt-1 text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight text-[#F7F7F2]">
            Curated Demo Tasks
          </h1>
          <p className="mt-1.5 text-xs sm:text-sm text-[#A9B8AD] max-w-2xl leading-relaxed">
            Choose a verified demonstration task pinned to explicit commits and dependency versions.
            Each task reproduces a confirmed upgrade failure ready for automated repair.
          </p>
        </div>

        {/* Right Info Badges */}
        <div className="flex items-center gap-3 shrink-0">
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
          <div className="rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] px-3.5 py-1.5 text-left">
            <div className="text-[10px] font-mono text-[#A9B8AD] uppercase tracking-wider">
              Available Scenarios
            </div>
            <div className="text-xs sm:text-sm font-semibold text-[#F7F7F2]">
              {tasks.length} Curated Demos
            </div>
          </div>
        </div>
      </div>

      {/* Verified Run Showcase Banner (Saved Results Separate from Live Runs) */}
      <div className="rounded-xl border border-[#5FCB8A]/30 bg-[#15271F] p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="size-2 rounded-full bg-[#5FCB8A]" />
            <span className="font-semibold text-xs sm:text-sm text-[#F7F7F2]">
              Past Verified Production Runs (Instant Results)
            </span>
            <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-mono text-[10px] px-2 py-0">
              SAVED VERIFICATION
            </Badge>
          </div>
          <p className="mt-1 text-xs text-[#A9B8AD] leading-relaxed">
            Inspect verified live repair results, candidate patches, Pytest verification logs, and evidence JSON from recent production runs without triggering a new repair job.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Button
            size="sm"
            onClick={() => handleOpenSaved("run_a72af9a70dbc47ee9ba7c7b8b6ff1226")}
            className="bg-[#5FCB8A] text-[#0D1915] hover:bg-[#5FCB8A]/90 font-medium text-xs h-8 cursor-pointer"
          >
            Demo Shop (run_a72af9a)
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleOpenSaved("run_4c8b02996ca547a4a134e5ccaf682681")}
            className="border-[rgba(183,201,173,0.3)] bg-[#1B3228] text-[#F7F7F2] hover:bg-[#203c30] text-xs h-8 cursor-pointer"
          >
            Demo Auth JWT (run_4c8b029)
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleOpenSaved("run_f80b7c8b136f4e37ac27841d3067bc4b")}
            className="border-[rgba(183,201,173,0.3)] bg-[#1B3228] text-[#F7F7F2] hover:bg-[#203c30] text-xs h-8 cursor-pointer"
          >
            Demo Click (run_f80b7c8)
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleOpenSaved("run_3b3ffafecdac4813a0f6120d6040d7eb")}
            className="border-[rgba(183,201,173,0.3)] bg-[#1B3228] text-[#F7F7F2] hover:bg-[#203c30] text-xs h-8 cursor-pointer"
          >
            Demo Pydantic (run_3b3ffaf)
          </Button>
        </div>
      </div>

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Task Cards (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-3.5">
          {loading && (
            <div
              data-testid="tasks-loading"
              className="rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] p-8 text-center"
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
              className="rounded-xl border border-[#E5736A]/30 bg-[#241414] p-5 text-left"
            >
              <div className="flex items-center gap-2.5 mb-2">
                <AlertCircle className="size-5 text-[#E5736A]" />
                <h4 className="text-sm font-semibold text-[#F7F7F2]">
                  Failed to load tasks
                </h4>
              </div>
              <p className="text-xs font-mono text-[#A9B8AD] mb-3">
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
              className="rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] p-8 text-center"
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
                className="mt-3 border-[rgba(183,201,173,0.24)] text-xs text-[#F7F7F2] h-8 cursor-pointer"
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
                role="radio"
                aria-checked={isSelected}
                tabIndex={0}
                aria-label={`Select demo ${task.id}: ${task.title}`}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelectedTaskId(task.id);
                  }
                }}
                onClick={() => setSelectedTaskId(task.id)}
                className={`cursor-pointer transition-all rounded-xl p-4 sm:p-5 border text-left shadow-none focus-visible:ring-1 focus-visible:ring-[#5FCB8A] outline-none ${
                  isSelected
                    ? "bg-[#1B3228] border-[rgba(183,201,173,0.36)]"
                    : "bg-[#15271F] border-[rgba(183,201,173,0.16)] hover:bg-[#182C23]"
                }`}
              >
                {/* Header row: radio indicator, ID, Repo, Breakage Badge */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 text-xs">
                    {isSelected ? (
                      <CheckCircle className="size-4 text-[#5FCB8A] shrink-0" />
                    ) : (
                      <Circle className="size-4 text-[#A9B8AD] shrink-0" />
                    )}
                    <span className="font-mono text-[#F7F7F2] font-semibold">
                      {task.id}
                    </span>
                    <span className="text-[#A9B8AD] font-mono">{task.repo}</span>
                    <Badge className="bg-[#5FCB8A]/10 text-[#5FCB8A] border-transparent text-[10px] font-mono px-1.5 py-0 hidden xs:inline">
                      CURATED
                    </Badge>
                  </div>

                  <Badge className="bg-[#E5736A]/15 text-[#E5736A] border-transparent text-[10px] font-medium gap-1 px-2 py-0.5 rounded-full shrink-0">
                    <span className="size-1.5 rounded-full bg-[#E5736A]" />
                    BREAKAGE CONFIRMED
                  </Badge>
                </div>

                {/* Task Title */}
                <h3 className="text-sm sm:text-base font-semibold text-[#F7F7F2] mt-0.5 mb-2 leading-snug">
                  {task.title}
                </h3>

                {/* Metadata row: commit, target, preserved tests */}
                <div className="flex flex-wrap items-center gap-2.5 text-xs font-mono text-[#A9B8AD] mb-2.5">
                  <div className="flex items-center gap-1">
                    <GitCommit className="size-3.5" />
                    <span>
                      {task.commitSha !== "Unavailable"
                        ? task.commitSha.substring(0, 7)
                        : "Unavailable"}
                    </span>
                  </div>
                  <span>·</span>
                  <div>
                    target:{" "}
                    <span className="text-[#F7F7F2]">
                      {task.dependency}=={task.targetVersion}
                    </span>
                  </div>
                  <span>·</span>
                  <div>
                    {task.testsCount !== null
                      ? `${task.testsCount} declared test${task.testsCount === 1 ? "" : "s"}`
                      : "Declared tests: Unavailable"}
                  </div>
                </div>

                {/* Expected Failure Substring Inset */}
                <div className="rounded-md bg-[#0D1915] p-2.5 text-xs border border-[rgba(183,201,173,0.12)]">
                  <span className="font-semibold text-[#E5736A] mr-1.5">
                    Expected failure:
                  </span>
                  <span className="font-mono text-[#A9B8AD] leading-relaxed break-all">
                    {task.expectedFailure}
                  </span>
                </div>
              </Card>
            );
          })}
        </div>

        {/* Right Column: Selected Summary, Settings & Persistent Start Action (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-4 lg:sticky lg:top-20">
          {!selectedTask ? (
            <Card className="rounded-xl bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-5 sm:p-6 shadow-none text-center">
              <div className="py-12">
                <Layers className="size-8 mx-auto mb-3 text-[#A9B8AD]" />
                <p className="text-sm font-medium text-[#F7F7F2]">No Task Selected</p>
                <p className="text-xs text-[#A9B8AD] mt-1">
                  No repair task is currently selected or available.
                </p>
              </div>
            </Card>
          ) : (
            <Card className="rounded-xl bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-5 sm:p-6 shadow-none">
              {/* Header: Eyebrow + Target Repository */}
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="font-mono text-xs tracking-wider text-[#A9B8AD] uppercase">
                  SELECTED TARGET SPECIFICATION
                </span>
                <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent text-[10px] font-semibold px-2 py-0.5 rounded-full">
                  READY
                </Badge>
              </div>

              <h2 className="text-base sm:text-lg font-semibold text-[#F7F7F2] mb-4 break-words">
                {selectedTask.repo}
              </h2>

              {/* Target Spec Bento Summary */}
              <div className="space-y-2.5 mb-5 text-xs">
                <div className="rounded-lg bg-[#0D1915] border border-[rgba(183,201,173,0.12)] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[#A9B8AD] font-mono">Task ID &amp; Target</span>
                    <span className="font-mono text-[#F7F7F2] font-medium">
                      {selectedTask.id}
                    </span>
                  </div>
                  <div className="text-[12px] font-mono text-[#F7F7F2]">
                    {selectedTask.dependency}=={selectedTask.targetVersion}
                  </div>
                </div>

                <div className="rounded-lg bg-[#0D1915] border border-[rgba(183,201,173,0.12)] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[#A9B8AD] font-mono">Baseline Pinned Commit</span>
                    <span className="font-mono text-[#F7F7F2]">
                      {selectedTask.commitSha !== "Unavailable"
                        ? `${selectedTask.commitSha.substring(0, 10)}...`
                        : "Unavailable"}
                    </span>
                  </div>
                  <div className="text-[11px] font-mono text-[#A9B8AD]">
                    {selectedTask.testsCount !== null
                      ? `${selectedTask.testsCount} declared test${selectedTask.testsCount === 1 ? "" : "s"} (fixture metadata)`
                      : "Declared tests: Unavailable"}
                    {" · "}
                    {selectedTask.baselineTime !== "Unavailable"
                      ? `declared baseline timing: ${selectedTask.baselineTime}`
                      : "Baseline timing: Unavailable"}
                  </div>
                </div>

                <div className="rounded-lg bg-[#0D1915] border border-[rgba(183,201,173,0.12)] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[#A9B8AD] font-mono">Mutation Allowlist</span>
                    <span className="font-mono text-[#5FCB8A] text-[11px]">TESTS IMMUTABLE</span>
                  </div>
                  <div className="text-[11px] font-mono text-[#A9B8AD]">
                    Allowed: {selectedTask.allowlist}
                  </div>
                </div>
              </div>

              {/* Controls: Strategy and Mode */}
              <div className="space-y-3 pt-3 border-t border-[rgba(183,201,173,0.12)] mb-5">
                <div>
                  <label className="block text-xs font-mono text-[#A9B8AD] mb-1.5">
                    Repair Search Strategy
                  </label>
                  <Select
                    value={strategy}
                    onValueChange={(val: string | null) => {
                      if (val) setStrategy(val as SearchMode);
                    }}
                  >
                    <SelectTrigger className="w-full h-10 border-[rgba(183,201,173,0.2)] bg-[#0D1915] text-xs text-[#F7F7F2] rounded-lg px-3 font-medium">
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

                <div>
                  <label className="block text-xs font-mono text-[#A9B8AD] mb-1.5">
                    Execution Mode
                  </label>
                  <Select
                    value={executionMode}
                    onValueChange={(val: string | null) => {
                      if (val) setExecutionMode(val);
                    }}
                  >
                    <SelectTrigger className="w-full h-10 border-[rgba(183,201,173,0.2)] bg-[#0D1915] text-xs text-[#F7F7F2] rounded-lg px-3 font-medium">
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
                  <span className="block mt-1 text-[11px] text-[#A9B8AD]">
                    {executionMode === "sandbox_live"
                      ? "Live demo uses provider resources and remote container sandboxes."
                      : "Dry-run emulation uses local fixtures without remote spend."}
                  </span>
                </div>
              </div>

              {/* Primary Action Button: Start repair run */}
              <Button
                type="button"
                disabled={isStarting || !selectedTask}
                onClick={handleStart}
                className="w-full h-11 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-xs sm:text-sm rounded-lg flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isStarting ? (
                  <>
                    <RotateCw className="size-4 animate-spin" />
                    Starting repair run...
                  </>
                ) : (
                  <>
                    <Play className="size-4 fill-current" />
                    Start repair run
                  </>
                )}
              </Button>

              <p className="mt-3 text-[11px] text-[#A9B8AD] text-center leading-relaxed">
                Executes in an isolated sandbox. Test suite integrity is verified against baseline hashes.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
