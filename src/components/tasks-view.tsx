"use client";

import React, { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
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
} from "lucide-react";
import { SearchMode } from "@/lib/contracts";

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

const TASKS_DATA: TaskItem[] = [
  {
    id: "TASK-084",
    repo: "tiangolo/fastapi-service",
    title: "pydantic v1.10.8 → v2.0.2 migration in fastapi-service",
    commitSha: "8a4f21d",
    dependency: "pydantic",
    targetVersion: "2.0.2",
    testsCount: 42,
    expectedFailure:
      "ValidationError: 'regex' replaced by 'pattern' in Field(), Config class replaced by ConfigDict",
    baselineTime: "1.48s (Python 3.10.12)",
    allowlist: "src/app/schemas.py, src/app/config.py",
  },
  {
    id: "TASK-091",
    repo: "pallets/backend-core",
    title: "sqlalchemy v1.4.48 → v2.0.19 in backend-core",
    commitSha: "c39b104",
    dependency: "sqlalchemy",
    targetVersion: "2.0.19",
    testsCount: 128,
    expectedFailure:
      "RemovedIn20Warning escalated to error: engine.execute() removed in 2.0",
    baselineTime: "3.12s (Python 3.11.4)",
    allowlist: "src/backend/database.py, src/backend/models.py",
  },
  {
    id: "TASK-097",
    repo: "encode/scraper-bot",
    title: "httpx v0.23.3 → v0.24.1 in scraper-bot",
    commitSha: "f72a110",
    dependency: "httpx",
    targetVersion: "0.24.1",
    testsCount: 34,
    expectedFailure:
      "TypeError: Client.__init__() got unexpected keyword argument 'proxies'",
    baselineTime: "0.95s (Python 3.10.8)",
    allowlist: "scraper/client.py, scraper/session.py",
  },
];

interface TasksViewProps {
  onStartRun: (taskId: string, strategy: SearchMode) => void;
  selectedTaskId: string;
  setSelectedTaskId: (taskId: string) => void;
  strategy: SearchMode;
  setStrategy: (strategy: SearchMode) => void;
}

export function TasksView({
  onStartRun,
  selectedTaskId,
  setSelectedTaskId,
  strategy,
  setStrategy,
}: TasksViewProps) {
  const [executionMode, setExecutionMode] = useState<string>("sandbox_live");

  const selectedTask =
    TASKS_DATA.find((t) => t.id === selectedTaskId) || TASKS_DATA[0];

  return (
    <div className="mx-auto w-full max-w-[1280px] px-6 py-8">
      {/* Top Header & Stats */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 pb-6">
        <div>
          <span className="font-mono text-xs font-medium tracking-[0.06em] uppercase text-[#A9B8AD]">
            TARGET DISCOVERY / REPRODUCIBLE BENCHMARKS
          </span>
          <h1 className="mt-1 text-3xl md:text-4xl font-semibold tracking-tight text-[#F7F7F2]">
            Upgrade &amp; Repair Tasks
          </h1>
          <p className="mt-2 text-sm text-[#A9B8AD] max-w-2xl leading-relaxed">
            Select a curated Python repository task pinned to explicit commits
            and dependency versions. Each reproduces a confirmed upgrade failure.
          </p>
        </div>

        {/* Right Info Badges */}
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] px-4 py-2 text-left">
            <div className="text-[11px] font-mono text-[#A9B8AD] uppercase tracking-wider">
              Total Fixtures
            </div>
            <div className="text-sm font-semibold text-[#F7F7F2]">
              18 Validated
            </div>
          </div>
          <div className="rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] px-4 py-2 text-left">
            <div className="text-[11px] font-mono text-[#A9B8AD] uppercase tracking-wider">
              Sandbox Node
            </div>
            <div className="flex items-center gap-1.5 text-sm font-semibold text-[#F7F7F2]">
              <span className="size-2 rounded-full bg-[#5FCB8A]" />
              Nebius D1-a
            </div>
          </div>
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
                <SelectItem value="branch_refine">
                  Branch &amp; Refine (max 3 candidates)
                </SelectItem>
                <SelectItem value="sequential">
                  Sequential Direct (single pass)
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

        {/* Determinism Token */}
        <div className="flex items-center gap-2 text-xs font-mono text-[#A9B8AD]">
          <ShieldCheck className="size-4 text-[#5FCB8A]" />
          <span>Determinism Token:</span>
          <span className="text-[#F7F7F2] font-semibold">#0x7F2B</span>
        </div>
      </div>

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Task Cards (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          {TASKS_DATA.map((task) => {
            const isSelected = task.id === selectedTaskId;
            return (
              <Card
                key={task.id}
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
                  </div>

                  <Badge className="bg-[#E5736A]/15 text-[#E5736A] border-transparent text-[11px] font-medium gap-1 px-2 py-0.5 rounded-full">
                    <span className="size-1.5 rounded-full bg-[#E5736A]" />
                    FAIL ON UPGRADE CONFIRMED
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
                    <span>{task.commitSha}</span>
                  </div>
                  <span>·</span>
                  <div>
                    target:{" "}
                    <span className="text-[#F7F7F2]">
                      {task.dependency}=={task.targetVersion}
                    </span>
                  </div>
                  <span>·</span>
                  <div>{task.testsCount} preserved tests</div>
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
                All fixtures immutable. Hash verification SHA-256 enabled.
              </span>
            </div>
            <span className="font-mono text-[11px]">
              Filter: Python 3.10+ / Pytest 7.x
            </span>
          </div>
        </div>

        {/* Right Column: Target Verification & Preflight (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-6">
            {/* Header: Eyebrow + Pre-flight Badge */}
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="font-mono text-xs tracking-wider text-[#A9B8AD] uppercase">
                TARGET VERIFICATION
              </span>
              <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent text-[11px] font-semibold px-2 py-0.5 rounded-full">
                PRE-FLIGHT READY
              </Badge>
            </div>

            <h2 className="text-lg font-semibold text-[#F7F7F2] mb-5">
              {selectedTask.repo}
            </h2>

            {/* Check 1: Green Baseline */}
            <div className="rounded-xl bg-[#1B3228]/60 border border-[rgba(183,201,173,0.12)] p-3.5 mb-3">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 text-xs font-semibold text-[#F7F7F2]">
                  <CheckCircle2 className="size-4 text-[#5FCB8A]" />
                  <span>Green Baseline Verified</span>
                </div>
                <Badge className="bg-[#5FCB8A]/20 text-[#5FCB8A] border-transparent font-mono text-[11px] px-2 py-0">
                  {selectedTask.testsCount}/{selectedTask.testsCount} PASS
                </Badge>
              </div>
              <p className="text-[11px] font-mono text-[#A9B8AD] pl-6">
                pytest 7.4.0 passed in {selectedTask.baselineTime}
              </p>
            </div>

            {/* Check 2: Expected Red Upgrade */}
            <div className="rounded-xl bg-[#1B3228]/60 border border-[rgba(183,201,173,0.12)] p-3.5 mb-3">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 text-xs font-semibold text-[#F7F7F2]">
                  <AlertCircle className="size-4 text-[#E5736A]" />
                  <span>Expected Red Upgrade</span>
                </div>
                <Badge className="bg-[#E5736A]/20 text-[#E5736A] border-transparent font-mono text-[11px] px-2 py-0">
                  CONFIRMED
                </Badge>
              </div>
              <p className="text-[11px] font-mono text-[#A9B8AD] pl-6">
                Target pinned to {selectedTask.dependency}==
                {selectedTask.targetVersion}
              </p>
            </div>

            {/* Check 3: Mutation Allowlist */}
            <div className="rounded-xl bg-[#1B3228]/60 border border-[rgba(183,201,173,0.12)] p-3.5 mb-5">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 text-xs font-semibold text-[#F7F7F2]">
                  <FileCode className="size-4 text-[#7FB3D5]" />
                  <span>Mutation Allowlist</span>
                </div>
                <Badge className="bg-[#7FB3D5]/20 text-[#7FB3D5] border-transparent font-mono text-[11px] px-2 py-0">
                  TESTS UNTOUCHED
                </Badge>
              </div>
              <p className="text-[11px] font-mono text-[#A9B8AD] pl-6">
                {selectedTask.allowlist}
              </p>
            </div>

            {/* Sandbox Isolation Profile */}
            <div className="rounded-xl bg-[#0D1915] border border-[rgba(183,201,173,0.12)] p-4 mb-5">
              <div className="flex items-center justify-between text-xs font-mono mb-2">
                <span className="text-[#A9B8AD]">SANDBOX ISOLATION PROFILE</span>
                <span className="text-[#F7F7F2] font-medium">
                  Ephemeral vCPU x4
                </span>
              </div>

              {/* Segmented Bar */}
              <div className="h-1.5 w-full rounded-full bg-[#1B3228] flex overflow-hidden mb-2">
                <div className="w-[65%] bg-[#5FCB8A]" />
                <div className="w-[20%] bg-[#E5736A]" />
                <div className="w-[15%] bg-[#7FB3D5]" />
              </div>

              <div className="flex items-center justify-between text-[11px] font-mono text-[#A9B8AD]">
                <span>Allocated timeout: 120s</span>
                <span>Memory limit: 2048 MB</span>
              </div>
            </div>

            {/* Primary Action Button (The single sage primary button per DESIGN.md) */}
            <Button
              onClick={() => onStartRun(selectedTask.id, strategy)}
              className="w-full h-11 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-sm rounded-lg flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-none"
            >
              <Play className="size-4 fill-current" />
              Start repair run
            </Button>

            {/* Inspect Links below button */}
            <div className="flex items-center justify-center gap-6 mt-4 text-xs font-mono text-[#A9B8AD]">
              <button
                type="button"
                className="flex items-center gap-1.5 hover:text-[#F7F7F2] transition-colors"
              >
                <FolderGit2 className="size-3.5" />
                <span>Inspect commit</span>
              </button>
              <button
                type="button"
                className="flex items-center gap-1.5 hover:text-[#F7F7F2] transition-colors"
              >
                <FileText className="size-3.5" />
                <span>Pytest logs</span>
              </button>
            </div>

            <p className="mt-4 text-[11px] text-[#A9B8AD] text-center leading-relaxed">
              Run will fork an isolated micro-VM. Preserved test suite is evaluated
              automatically after AST transformations.
            </p>
          </Card>

          {/* Runner Pool Card */}
          <div className="flex items-center justify-between rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] px-4 py-3 text-xs">
            <div className="flex items-center gap-2 text-[#F7F7F2]">
              <span className="size-2 rounded-full bg-[#5FCB8A]" />
              <span>Runner Pool: 8 warm containers</span>
            </div>
            <span className="font-mono text-[#A9B8AD] text-[11px]">
              Auto-cleanup enabled
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
