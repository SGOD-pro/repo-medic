"use client";

import React, { useState, useEffect, useMemo } from "react";
import { Navbar, ActiveTab } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { TasksView } from "@/components/tasks-view";
import { RunActiveView } from "@/components/run-active-view";
import { VerificationView } from "@/components/verification-view";
import { HistoryDrawer } from "@/components/history-drawer";
import { createApiClient, CURATED_TASKS } from "@/lib/api";
import { SearchMode, RunSummary } from "@/lib/contracts";
import { useHistoryStore, HistoryRunItem } from "@/lib/history-store";

export default function Home() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("tasks");
  const [selectedTaskId, setSelectedTaskId] = useState<string>("TASK-084");
  const [strategy, setStrategy] = useState<SearchMode>("branch_refine");
  const [activeRun, setActiveRun] = useState<RunSummary | null>(null);
  const [runStartedAt, setRunStartedAt] = useState<number | undefined>();

  const apiClient = useMemo(() => createApiClient(), []);
  const { addRun, updateRun } = useHistoryStore();

  // URL search parameter synchronization & reload on initial boot
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const runIdFromUrl = params.get("runId");

    let isMounted = true;

    if (runIdFromUrl) {
      // 1. Check in active store runs
      const storeRuns = useHistoryStore.getState().runs;
      let existing = storeRuns.find((r) => r.run_id === runIdFromUrl);

      // 2. Check localStorage synchronously if store is still hydrating
      if (!existing && typeof window !== "undefined") {
        try {
          const raw = window.localStorage.getItem("repomedic_run_history");
          if (raw) {
            const parsed = JSON.parse(raw);
            const storedRuns = parsed?.state?.runs;
            if (Array.isArray(storedRuns)) {
              existing = storedRuns.find(
                (r: HistoryRunItem) => r.run_id === runIdFromUrl
              );
            }
          }
        } catch {
          // Ignore JSON parse errors
        }
      }

      if (existing) {
        const item = existing;
        queueMicrotask(() => {
          if (!isMounted) return;
          setSelectedTaskId(item.task_id);
          setStrategy(item.search_mode);
          if (
            item.state === "succeeded" ||
            item.state === "failed" ||
            item.state === "cancelled"
          ) {
            setActiveTab("verification");
          } else {
            setActiveTab("run_active");
          }
        });
      } else {
        // Fallback: hydrate from API client
        apiClient
          .getRun(runIdFromUrl)
          .then((run) => {
            if (!isMounted) return;
            setActiveRun(run);
            setSelectedTaskId(run.task_id);
            if (
              run.state === "succeeded" ||
              run.state === "failed" ||
              run.state === "cancelled"
            ) {
              setActiveTab("verification");
            } else {
              setActiveTab("run_active");
            }
          })
          .catch(() => {
            if (!isMounted) return;
            window.history.replaceState(null, "", window.location.pathname);
          });
      }
    }

    return () => {
      isMounted = false;
    };
  }, [apiClient]);

  const updateUrlParam = (runId: string | null) => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (runId) {
      url.searchParams.set("runId", runId);
    } else {
      url.searchParams.delete("runId");
    }
    window.history.replaceState(null, "", url.toString());
  };

  const handleStartRun = async (taskId: string, chosenStrategy: SearchMode) => {
    try {
      const run = await apiClient.startRun(taskId, chosenStrategy);
      setActiveRun(run);
      setRunStartedAt(Date.now());

      const task =
        CURATED_TASKS.find((t) => t.task_id === taskId) || CURATED_TASKS[0];

      // Add run to persistent history store
      addRun({
        run_id: run.run_id,
        task_id: task.task_id,
        task_title: task.title,
        dependency: task.dependency,
        from_version: task.from_version,
        to_version: task.to_version,
        state: run.state,
        mode: run.mode,
        search_mode: run.search_mode,
        started_at: new Date().toISOString(),
        completed_at: null,
        duration: "00:00s", // Initial placeholder elapsed time, updated upon run completion
        tests_passed: null,
        tests_failed: null,
        cost_usd: run.usage.estimated_usd,
      });

      updateUrlParam(run.run_id);
      setActiveTab("run_active");
    } catch (err) {
      console.error("Failed to start run:", err);
      setRunStartedAt(Date.now());
      setActiveTab("run_active");
    }
  };

  const handleInspectResults = () => {
    if (activeRun) {
      // Mark as completed in history
      updateRun(activeRun.run_id, {
        state: "succeeded",
        completed_at: new Date().toISOString(),
        duration: "24.2s",
        tests_passed: 42,
        tests_failed: 0,
        cost_usd: 0.04,
      });
    }
    setActiveTab("verification");
  };

  const handleCancelRun = async () => {
    if (activeRun) {
      try {
        const cancelled = await apiClient.cancelRun(activeRun.run_id);
        const elapsedSec = runStartedAt
          ? Math.max(0, Math.floor((Date.now() - runStartedAt) / 1000))
          : 105;
        const m = Math.floor(elapsedSec / 60);
        const s = elapsedSec % 60;
        const formattedDuration = `${m}m ${s}s`;

        updateRun(activeRun.run_id, {
          state: "cancelled",
          completed_at: new Date().toISOString(),
          duration: formattedDuration,
          cost_usd: 0.18,
        });
        setActiveRun(cancelled);
      } catch (err) {
        console.error("Failed to cancel run:", err);
      }
    }
  };

  const handleRunAnotherTask = () => {
    setActiveRun(null);
    updateUrlParam(null);
    setActiveTab("tasks");
  };

  const handleSelectRunFromHistory = (runItem: HistoryRunItem) => {
    setSelectedTaskId(runItem.task_id);
    setStrategy(runItem.search_mode);
    updateUrlParam(runItem.run_id);

    // Smart route: terminal runs load verification, active resume in run_active
    if (
      runItem.state === "succeeded" ||
      runItem.state === "failed" ||
      runItem.state === "cancelled"
    ) {
      setActiveTab("verification");
    } else {
      setActiveTab("run_active");
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-[#0D1915] text-[#F7F7F2]">
      {/* Shared Navigation Header */}
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onOpenDocs={() => {
          window.open(
            process.env.NEXT_PUBLIC_DOCS_URL ||
              "https://github.com/SGOD-pro/repo-medic",
            "_blank",
            "noopener,noreferrer"
          );
        }}
      />

      {/* Slide-over Run History Drawer */}
      <HistoryDrawer onSelectRun={handleSelectRunFromHistory} />

      {/* Main View Area */}
      <main className="flex-1 pb-16">
        {activeTab === "tasks" && (
          <TasksView
            onStartRun={handleStartRun}
            selectedTaskId={selectedTaskId}
            setSelectedTaskId={setSelectedTaskId}
            strategy={strategy}
            setStrategy={setStrategy}
          />
        )}

        {activeTab === "run_active" && (
          <RunActiveView
            onInspectResults={handleInspectResults}
            onCancelRun={handleCancelRun}
            startedAt={runStartedAt}
            activeRun={activeRun}
            onReturnToTasks={handleRunAnotherTask}
          />
        )}

        {activeTab === "verification" && (
          <VerificationView onRunAnotherTask={handleRunAnotherTask} />
        )}
      </main>

      {/* Shared Footer */}
      <Footer />
    </div>
  );
}
