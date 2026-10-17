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
      }

      // Hydrate activeRun from getRun() on reload
      apiClient
        .getRun(runIdFromUrl)
        .then((run) => {
          if (!isMounted) return;
          setActiveRun(run);
          setSelectedTaskId(run.task_id);
          setStrategy(run.search_mode);
          updateRun(run.run_id, {
            state: run.state,
            reason: run.reason,
            cost_usd: run.usage?.estimated_usd,
          });
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
          if (!existing) {
            window.history.replaceState(null, "", window.location.pathname);
          }
        });
    }

    return () => {
      isMounted = false;
    };
  }, [apiClient, updateRun]);

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

  const handleInspectResults = async () => {
    if (activeRun) {
      try {
        const fresh = await apiClient.getRun(activeRun.run_id);
        setActiveRun(fresh);
        updateRun(fresh.run_id, {
          state: fresh.state,
          reason: fresh.reason,
          cost_usd: fresh.usage?.estimated_usd,
        });
      } catch {
        updateRun(activeRun.run_id, {
          state: activeRun.state,
          reason: activeRun.reason,
          cost_usd: activeRun.usage?.estimated_usd,
        });
      }
    }
    setActiveTab("verification");
  };

  const handleCancelRun = async () => {
    if (activeRun) {
      try {
        const cancelled = await apiClient.cancelRun(activeRun.run_id);
        const elapsedSec = runStartedAt
          ? Math.max(0, Math.floor((Date.now() - runStartedAt) / 1000))
          : 0;
        const m = Math.floor(elapsedSec / 60);
        const s = elapsedSec % 60;
        const formattedDuration = `${m}m ${s}s`;

        updateRun(activeRun.run_id, {
          state: cancelled.state,
          reason: cancelled.reason,
          completed_at: new Date().toISOString(),
          duration: formattedDuration,
          cost_usd: cancelled.usage?.estimated_usd ?? 0,
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

    apiClient
      .getRun(runItem.run_id)
      .then((run) => {
        setActiveRun(run);
      })
      .catch(() => {
        setActiveRun({
          run_id: runItem.run_id,
          task_id: runItem.task_id,
          mode: runItem.mode,
          search_mode: runItem.search_mode,
          state: runItem.state,
          reason: runItem.reason || null,
          usage: {
            model_calls: 0,
            input_tokens: 0,
            output_tokens: 0,
            estimated_usd: runItem.cost_usd || 0,
          },
          artifacts: [],
        });
      });

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
            apiClient={apiClient}
          />
        )}

        {activeTab === "run_active" && (
          <RunActiveView
            onInspectResults={handleInspectResults}
            onCancelRun={handleCancelRun}
            startedAt={runStartedAt}
            activeRun={activeRun}
            onReturnToTasks={handleRunAnotherTask}
            apiClient={apiClient}
            onUpdateRun={(updated) => {
              setActiveRun(updated);
              updateRun(updated.run_id, {
                state: updated.state,
                reason: updated.reason,
                cost_usd: updated.usage?.estimated_usd,
              });
            }}
          />
        )}

        {activeTab === "verification" && (
          <VerificationView
            activeRun={activeRun}
            apiClient={apiClient}
            onRunAnotherTask={handleRunAnotherTask}
          />
        )}
      </main>

      {/* Shared Footer */}
      <Footer />
    </div>
  );
}
