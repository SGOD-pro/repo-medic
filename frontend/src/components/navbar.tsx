"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { User, FileText, History } from "lucide-react";
import { useHistoryStore } from "@/lib/history-store";
import { RunSummary } from "@/lib/contracts";

export type ActiveTab = "tasks" | "run_active" | "verification";

interface NavbarProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  onOpenDocs?: () => void;
  activeRun?: RunSummary | null;
}

export function Navbar({ activeTab, onTabChange, onOpenDocs, activeRun }: NavbarProps) {
  const { runs, setHistoryOpen } = useHistoryStore();
  const isMock = (process.env.NEXT_PUBLIC_API_TRANSPORT || "mock") === "mock";
  const mode = activeRun?.mode;

  let modeBadgeText = "TURSO PERSISTENCE / OFFLINE MODE";
  let modeSubtitle = "Remote Turso · Python Engine";

  if (isMock) {
    modeBadgeText = "MOCK TRANSPORT (SYNTHETIC)";
    modeSubtitle = "Offline Fixtures · Client In Memory";
  } else if (mode === "live") {
    modeBadgeText = "LIVE MODE (TURSO / NEBIUS)";
    modeSubtitle = "Remote Turso · Nebius Token Factory";
  } else if (mode === "replay") {
    modeBadgeText = "REPLAY MODE (TURSO)";
    modeSubtitle = "Remote Turso · Recorded Sandbox Traces";
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[rgba(183,201,173,0.16)] bg-[#0D1915]/95 backdrop-blur-none px-6 py-3">
      <div className="mx-auto flex max-w-[1280px] items-center justify-between gap-4">
        {/* Left: Brand + Demo Status */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-lg tracking-tight text-[#F7F7F2]">
              RepoMedic
            </span>
            <Badge
              variant="outline"
              className="border-[rgba(183,201,173,0.24)] bg-transparent font-mono text-[11px] text-[#A9B8AD] px-1.5 py-0"
            >
              V0.9.4
            </Badge>
          </div>

          <div className="hidden sm:flex items-center gap-2 text-xs">
            {isMock ? (
              <Badge className="bg-[#7FB3D5]/15 text-[#7FB3D5] border-transparent font-medium gap-1.5 px-2.5 py-0.5 rounded-full">
                <span className="size-1.5 rounded-full bg-[#7FB3D5]" />
                {modeBadgeText}
              </Badge>
            ) : (
              <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-medium gap-1.5 px-2.5 py-0.5 rounded-full">
                <span className="size-1.5 rounded-full bg-[#5FCB8A] animate-pulse" />
                {modeBadgeText}
              </Badge>
            )}
            <span className="font-mono text-[#A9B8AD] text-[12px]">
              {modeSubtitle}
            </span>
          </div>
        </div>

        {/* Center: Main View Switcher Tabs */}
        <div className="flex items-center bg-[#15271F] p-1 rounded-lg border border-[rgba(183,201,173,0.16)]">
          <button
            type="button"
            onClick={() => onTabChange("tasks")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              activeTab === "tasks"
                ? "bg-[#1B3228] text-[#F7F7F2] shadow-none"
                : "text-[#A9B8AD] hover:text-[#F7F7F2]"
            }`}
          >
            Tasks
          </button>
          <button
            type="button"
            onClick={() => onTabChange("run_active")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              activeTab === "run_active"
                ? "bg-[#1B3228] text-[#F7F7F2] shadow-none"
                : "text-[#A9B8AD] hover:text-[#F7F7F2]"
            }`}
          >
            Run Active
          </button>
          <button
            type="button"
            onClick={() => onTabChange("verification")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              activeTab === "verification"
                ? "bg-[#1B3228] text-[#F7F7F2] shadow-none"
                : "text-[#A9B8AD] hover:text-[#F7F7F2]"
            }`}
          >
            Verification &amp; Results
          </button>
        </div>

        {/* Right: History, Docs Action & User Avatar */}
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setHistoryOpen(true)}
            className="border-[rgba(183,201,173,0.32)] bg-[#15271F] text-[#F7F7F2] hover:bg-[#1B3228] hover:text-[#F7F7F2] text-xs h-8 px-3 rounded-md gap-1.5"
            title="Open past run history"
          >
            <History className="size-3.5 text-[#5FCB8A]" />
            <span>History</span>
            {runs.length > 0 && (
              <Badge className="bg-[#1B3228] text-[#5FCB8A] border-[rgba(183,201,173,0.2)] font-mono text-[10px] px-1.5 py-0 rounded-full ml-0.5">
                {runs.length}
              </Badge>
            )}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onOpenDocs}
            className="hidden sm:flex border-[rgba(183,201,173,0.32)] bg-transparent text-[#F7F7F2] hover:bg-[#1B3228] hover:text-[#F7F7F2] text-xs h-8 px-3 rounded-md gap-1.5"
          >
            <FileText className="size-3.5 text-[#A9B8AD]" />
            Docs / Specs
          </Button>

          <Avatar className="size-8 border border-[rgba(183,201,173,0.2)] bg-[#15271F] cursor-pointer">
            <AvatarFallback className="bg-[#15271F] text-[#F7F7F2] text-xs">
              <User className="size-4 text-[#A9B8AD]" />
            </AvatarFallback>
          </Avatar>
        </div>
      </div>
    </header>
  );
}
