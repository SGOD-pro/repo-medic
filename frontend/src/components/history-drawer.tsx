"use client";

import React from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useHistoryStore, HistoryRunItem } from "@/lib/history-store";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCw,
  Clock,
  Trash2,
  History,
  ArrowRight,
} from "lucide-react";

interface HistoryDrawerProps {
  onSelectRun: (run: HistoryRunItem) => void;
}

export function HistoryDrawer({ onSelectRun }: HistoryDrawerProps) {
  const { runs, isHistoryOpen, setHistoryOpen, clearHistory } =
    useHistoryStore();

  const handleSelectRun = (run: HistoryRunItem) => {
    onSelectRun(run);
    setHistoryOpen(false);
  };

  const getStatusBadge = (state: HistoryRunItem["state"]) => {
    switch (state) {
      case "succeeded":
        return (
          <Badge className="bg-[#5FCB8A]/20 text-[#5FCB8A] border-transparent font-mono text-[11px] gap-1 px-2 py-0.5">
            <CheckCircle2 className="size-3" />
            PASSED
          </Badge>
        );
      case "running":
        return (
          <Badge className="bg-[#7FB3D5]/20 text-[#7FB3D5] border-transparent font-mono text-[11px] gap-1 px-2 py-0.5">
            <RotateCw className="size-3 animate-spin" />
            RUNNING
          </Badge>
        );
      case "failed":
        return (
          <Badge className="bg-[#E5736A]/20 text-[#E5736A] border-transparent font-mono text-[11px] gap-1 px-2 py-0.5">
            <XCircle className="size-3" />
            FAILED
          </Badge>
        );
      case "cancelled":
        return (
          <Badge className="bg-[#E0B45A]/20 text-[#E0B45A] border-transparent font-mono text-[11px] gap-1 px-2 py-0.5">
            <AlertTriangle className="size-3" />
            CANCELLED
          </Badge>
        );
      case "queued":
      default:
        return (
          <Badge className="bg-[#15271F] text-[#A9B8AD] border-[rgba(183,201,173,0.16)] font-mono text-[11px] gap-1 px-2 py-0.5">
            <Clock className="size-3" />
            QUEUED
          </Badge>
        );
    }
  };

  const formatTimestamp = (isoString?: string | null) => {
    if (!isoString) return "Unavailable";
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return "Unavailable";
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "Unavailable";
    }
  };

  return (
    <Sheet open={isHistoryOpen} onOpenChange={setHistoryOpen}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-md bg-[#0D1915] border-l border-[rgba(183,201,173,0.16)] text-[#F7F7F2] p-0 flex flex-col z-50"
      >
        {/* Drawer Header */}
        <SheetHeader className="p-5 sm:p-6 border-b border-[rgba(183,201,173,0.16)] bg-[#11221B]/60">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <History className="size-5 text-[#5FCB8A]" />
              <SheetTitle className="text-base font-semibold text-[#F7F7F2]">
                Run History
              </SheetTitle>
              <Badge className="bg-[#1B3228] text-[#B7C9AD] border-[rgba(183,201,173,0.2)] font-mono text-xs px-2 py-0.5">
                {runs.length} runs
              </Badge>
            </div>
            {runs.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearHistory}
                className="text-xs text-[#A9B8AD] hover:text-[#E5736A] hover:bg-[#E5736A]/10 h-8 px-2.5 gap-1.5 cursor-pointer"
                title="Clear local run records"
              >
                <Trash2 className="size-3.5" />
                Clear
              </Button>
            )}
          </div>
          <SheetDescription className="text-xs text-[#A9B8AD] mt-1">
            Persisted repair runs across tasks and evaluation sandboxes. Click any
            run to reload its state and evidence.
          </SheetDescription>
        </SheetHeader>

        {/* Runs List */}
        <ScrollArea className="flex-1 p-4 sm:p-6">
          {runs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center px-4">
              <div className="size-12 rounded-full bg-[#15271F] border border-[rgba(183,201,173,0.16)] flex items-center justify-center mb-3">
                <History className="size-6 text-[#A9B8AD]" />
              </div>
              <h3 className="text-sm font-semibold text-[#F7F7F2] mb-1">
                No past runs recorded
              </h3>
              <p className="text-xs text-[#A9B8AD] max-w-xs leading-relaxed">
                When you initiate repair tasks or view demo scenarios, completed runs will
                be recorded here for inspection and verification.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {runs.map((run: HistoryRunItem) => (
                <div
                  key={run.run_id}
                  onClick={() => handleSelectRun(run)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      handleSelectRun(run);
                    }
                  }}
                  className="rounded-xl bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-3.5 sm:p-4 cursor-pointer hover:border-[#5FCB8A]/40 hover:bg-[#182C23] transition-all group focus:outline-none focus:ring-1 focus:ring-[#5FCB8A]"
                >
                  {/* Top row: task id, status badge, timestamp */}
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-mono text-xs font-semibold text-[#5FCB8A]">
                      {run.task_id}
                    </span>
                    <div className="flex items-center gap-2">
                      {getStatusBadge(run.state)}
                      <span className="font-mono text-[11px] text-[#A9B8AD]">
                        {formatTimestamp(run.started_at)}
                      </span>
                    </div>
                  </div>

                  {/* Title & Dependency Bump */}
                  <h4 className="text-xs sm:text-sm font-medium text-[#F7F7F2] line-clamp-1 mb-1">
                    {run.task_title}
                  </h4>
                  <div className="font-mono text-[11px] text-[#A9B8AD] mb-2.5">
                    {run.dependency} {run.from_version} → {run.to_version}
                  </div>

                  {/* Bottom row: run_id, mode, metrics */}
                  <div className="flex items-center justify-between pt-2 border-t border-[rgba(183,201,173,0.1)] text-[11px] font-mono text-[#A9B8AD]">
                    <div className="flex items-center gap-2">
                      <span className="truncate max-w-[120px]">{run.run_id}</span>
                      <Badge className="bg-[#0D1915] text-[#A9B8AD] border-[rgba(183,201,173,0.16)] text-[9px] px-1.5 py-0 uppercase">
                        {run.mode}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-2 text-[#F7F7F2]">
                      {run.duration && <span>{run.duration}</span>}
                      {run.cost_usd !== null && run.cost_usd !== undefined && (
                        <span className="text-[#5FCB8A]">${run.cost_usd.toFixed(2)}</span>
                      )}
                      <ArrowRight className="size-3 text-[#A9B8AD] group-hover:text-[#5FCB8A] transition-colors" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
