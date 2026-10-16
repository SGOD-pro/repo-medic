import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { Mode, SearchMode, RunState } from "./contracts";

export interface HistoryRunItem {
  run_id: string;
  task_id: string;
  task_title: string;
  dependency: string;
  from_version: string;
  to_version: string;
  state: RunState;
  mode: Mode;
  search_mode: SearchMode;
  started_at: string;
  completed_at?: string | null;
  duration?: string | null;
  tests_passed?: number | null;
  tests_failed?: number | null;
  cost_usd?: number | null;
  reason?: string | null;
}

export const INITIAL_SEEDED_RUNS: HistoryRunItem[] = [
  {
    run_id: "run-success-1",
    task_id: "TASK-084",
    task_title: "pydantic v1.10.8 → v2.0.2 migration in fastapi-service",
    dependency: "pydantic",
    from_version: "1.10.8",
    to_version: "2.0.2",
    state: "succeeded",
    mode: "live",
    search_mode: "branch_refine",
    started_at: "2026-10-10T02:15:00Z",
    completed_at: "2026-10-10T02:15:24Z",
    duration: "24.2s",
    tests_passed: 42,
    tests_failed: 0,
    cost_usd: 0.04,
  },
  {
    run_id: "run-fail-1",
    task_id: "TASK-091",
    task_title: "sqlalchemy v1.4.48 → v2.0.19 in backend-core",
    dependency: "sqlalchemy",
    from_version: "1.4.48",
    to_version: "2.0.19",
    state: "failed",
    mode: "offline",
    search_mode: "sequential",
    started_at: "2026-10-10T01:45:00Z",
    completed_at: "2026-10-10T01:45:20Z",
    duration: "19.8s",
    tests_passed: 38,
    tests_failed: 4,
    cost_usd: 0.12,
  },
  {
    run_id: "run-cancel-1",
    task_id: "TASK-097",
    task_title: "httpx v0.23.3 → v0.24.1 in scraper-bot",
    dependency: "httpx",
    from_version: "0.23.3",
    to_version: "0.24.1",
    state: "cancelled",
    mode: "live",
    search_mode: "branch_refine",
    started_at: "2026-10-10T01:10:00Z",
    completed_at: "2026-10-10T01:10:08Z",
    duration: "8.4s",
    tests_passed: 0,
    tests_failed: 0,
    cost_usd: 0.02,
  },
];

interface HistoryState {
  runs: HistoryRunItem[];
  isHistoryOpen: boolean;
  hasHydrated: boolean;
  addRun: (item: HistoryRunItem) => void;
  updateRun: (runId: string, partial: Partial<HistoryRunItem>) => void;
  clearHistory: () => void;
  setHistoryOpen: (open: boolean) => void;
  setHasHydrated: (hydrated: boolean) => void;
}

export const useHistoryStore = create<HistoryState>()(
  persist(
    (set) => ({
      runs: INITIAL_SEEDED_RUNS,
      isHistoryOpen: false,
      hasHydrated: false,
      addRun: (item) =>
        set((state) => {
          // Prepend new run and avoid duplicates
          const filtered = state.runs.filter((r) => r.run_id !== item.run_id);
          return { runs: [item, ...filtered] };
        }),
      updateRun: (runId, partial) =>
        set((state) => ({
          runs: state.runs.map((r) =>
            r.run_id === runId ? { ...r, ...partial } : r
          ),
        })),
      clearHistory: () => set({ runs: [] }),
      setHistoryOpen: (open) => set({ isHistoryOpen: open }),
      setHasHydrated: (hydrated) => set({ hasHydrated: hydrated }),
    }),
    {
      name: "repomedic_run_history",
      storage: createJSONStorage(() => {
        if (typeof window !== "undefined") {
          return window.localStorage;
        }
        return {
          getItem: () => null,
          setItem: () => {},
          removeItem: () => {},
        };
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);
