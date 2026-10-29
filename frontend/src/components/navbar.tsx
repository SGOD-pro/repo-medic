"use client";

import React from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { User, FileText, History } from "lucide-react";
import { useHistoryStore } from "@/lib/history-store";
import { RunSummary } from "@/lib/contracts";

export type ActiveTab = "custom_repo" | "tasks" | "run_active" | "verification";

interface NavbarProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  onOpenDocs?: () => void;
  activeRun?: RunSummary | null;
}

export function Navbar({
  activeTab,
  onTabChange,
  onOpenDocs,
  activeRun,
}: NavbarProps) {
  const { runs, setHistoryOpen } = useHistoryStore();
  const defaultTransport = process.env.NODE_ENV === "production" ? "http" : "mock";
  const isMock = (process.env.NEXT_PUBLIC_API_TRANSPORT || defaultTransport) === "mock";
  const mode = activeRun?.mode;

  let modeBadgeText = "OFFLINE MODE (TURSO)";
  let modeSubtitle = "Remote Turso · Python Engine";

  if (isMock) {
    modeBadgeText = "MOCK TRANSPORT (OFFLINE DEMO)";
    modeSubtitle = "Offline Fixtures · Client In Memory";
  } else if (mode === "live") {
    modeBadgeText = "LIVE MODE (TURSO / NEBIUS)";
    modeSubtitle = "Remote Turso · Nebius Token Factory";
  } else if (mode === "replay") {
    modeBadgeText = "REPLAY MODE (TURSO)";
    modeSubtitle = "Remote Turso · Recorded Traces";
  } else {
    modeBadgeText = "OFFLINE MODE (TURSO)";
    modeSubtitle = "Remote API Gateway · Turso Persistence";
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[rgba(183,201,173,0.16)] bg-[#0D1915]/95 backdrop-blur-sm px-4 sm:px-6 py-2.5">
      <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-3">
        {/* Left: Brand + Mode Status */}
        <div className="flex items-center gap-3">
          <Link
            href="/home"
            className="flex items-center gap-2 cursor-pointer select-none group outline-none focus-visible:ring-1 focus-visible:ring-[#B7C9AD] rounded"
            aria-label="RepoMedic Home"
            title="Go to RepoMedic Landing Page"
          >
            <span className="font-semibold text-base sm:text-lg tracking-tight text-[#F7F7F2] group-hover:text-[#B7C9AD] transition-colors">
              RepoMedic
            </span>
            <Badge
              variant="outline"
              className="border-[rgba(183,201,173,0.24)] bg-transparent font-mono text-[11px] text-[#A9B8AD] px-1.5 py-0"
            >
              v0.9.4
            </Badge>
          </Link>

          <div className="hidden md:flex items-center gap-2 text-xs">
            {isMock ? (
              <Badge className="bg-[#7FB3D5]/15 text-[#7FB3D5] border-transparent font-medium gap-1.5 px-2.5 py-0.5 rounded-full">
                <span className="size-1.5 rounded-full bg-[#7FB3D5]" />
                {modeBadgeText}
              </Badge>
            ) : (
              <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-medium gap-1.5 px-2.5 py-0.5 rounded-full">
                <span className="size-1.5 rounded-full bg-[#5FCB8A]" />
                {modeBadgeText}
              </Badge>
            )}
            <span className="font-mono text-[#A9B8AD] text-[11px] hidden lg:inline">
              {modeSubtitle}
            </span>
          </div>
        </div>

        {/* Center: Clean 4 Workspace Tabs (No cluttered tabs!) */}
        <nav
          aria-label="Workspace Destinations"
          className="order-3 sm:order-2 flex w-full sm:w-auto items-center overflow-x-auto bg-[#15271F] p-1 rounded-lg border border-[rgba(183,201,173,0.16)]"
        >
          <button
            type="button"
            data-testid="nav-tab-custom-repo"
            onClick={() => onTabChange("custom_repo")}
            className={`min-h-[32px] px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap focus-visible:ring-1 focus-visible:ring-[#B7C9AD] outline-none cursor-pointer ${
              activeTab === "custom_repo"
                ? "bg-[#1B3228] text-[#F7F7F2] shadow-sm"
                : "text-[#A9B8AD] hover:text-[#F7F7F2]"
            }`}
          >
            Configure Repo
          </button>
          <button
            type="button"
            data-testid="nav-tab-tasks"
            onClick={() => onTabChange("tasks")}
            className={`min-h-[32px] px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap focus-visible:ring-1 focus-visible:ring-[#B7C9AD] outline-none cursor-pointer ${
              activeTab === "tasks"
                ? "bg-[#1B3228] text-[#F7F7F2] shadow-sm"
                : "text-[#A9B8AD] hover:text-[#F7F7F2]"
            }`}
          >
            Demo Tasks
          </button>
          <button
            type="button"
            data-testid="nav-tab-run-active"
            onClick={() => onTabChange("run_active")}
            className={`min-h-[32px] px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap focus-visible:ring-1 focus-visible:ring-[#B7C9AD] outline-none cursor-pointer ${
              activeTab === "run_active"
                ? "bg-[#1B3228] text-[#F7F7F2] shadow-sm"
                : "text-[#A9B8AD] hover:text-[#F7F7F2]"
            }`}
          >
            Run Active
          </button>
          <button
            type="button"
            data-testid="nav-tab-verification"
            onClick={() => onTabChange("verification")}
            className={`min-h-[32px] px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap focus-visible:ring-1 focus-visible:ring-[#B7C9AD] outline-none cursor-pointer ${
              activeTab === "verification"
                ? "bg-[#1B3228] text-[#F7F7F2] shadow-sm"
                : "text-[#A9B8AD] hover:text-[#F7F7F2]"
            }`}
          >
            Verification &amp; Results
          </button>
        </nav>

        {/* Right: Landing link, History, Docs & User Avatar */}
        <div className="order-2 sm:order-3 flex items-center gap-2">
          <Link
            href="/home"
            className="hidden sm:inline-flex items-center text-xs text-[#A9B8AD] hover:text-[#B7C9AD] transition-colors px-2.5 py-1 rounded-md border border-transparent hover:border-[rgba(183,201,173,0.2)]"
            title="View product landing page"
          >
            Landing
          </Link>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setHistoryOpen(true)}
            className="border-[rgba(183,201,173,0.32)] bg-[#15271F] text-[#F7F7F2] hover:bg-[#1B3228] hover:text-[#F7F7F2] text-xs h-8 px-2.5 sm:px-3 rounded-md gap-1.5 focus-visible:ring-1 focus-visible:ring-[#B7C9AD]"
            title="Open past run history"
            aria-label="Open past run history"
          >
            <History className="size-3.5 text-[#5FCB8A]" />
            <span className="hidden xs:inline">History</span>
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
            className="hidden sm:flex border-[rgba(183,201,173,0.32)] bg-transparent text-[#F7F7F2] hover:bg-[#1B3228] hover:text-[#F7F7F2] text-xs h-8 px-3 rounded-md gap-1.5 focus-visible:ring-1 focus-visible:ring-[#B7C9AD]"
            aria-label="Documentation and Specs"
          >
            <FileText className="size-3.5 text-[#A9B8AD]" />
            <span>Docs</span>
          </Button>

          <Avatar className="size-8 border border-[rgba(183,201,173,0.2)] bg-[#15271F]">
            <AvatarFallback className="bg-[#15271F] text-[#F7F7F2] text-xs font-mono">
              <User className="size-4 text-[#A9B8AD]" />
            </AvatarFallback>
          </Avatar>
        </div>
      </div>
    </header>
  );
}