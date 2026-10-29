"use client";

import React from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ArrowRight, CheckCircle2, FileText, Sparkles } from "lucide-react";

export function LandingNavbar() {
  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-[rgba(183,201,173,0.14)] bg-[#060908]/85 backdrop-blur-md px-4 sm:px-6 py-3">
      <div className="mx-auto flex max-w-[1280px] items-center justify-between gap-4">
        {/* Left: Brand Identity */}
        <Link
          href="/home"
          className="flex items-center gap-2.5 cursor-pointer select-none group outline-none focus-visible:ring-2 focus-visible:ring-[#B7C9AD] rounded-md"
          aria-label="RepoMedic Home"
        >
          <div className="flex size-7 items-center justify-center rounded-lg bg-[#15271F] border border-[rgba(183,201,173,0.25)] text-[#5FCB8A] group-hover:border-[#5FCB8A]/40 transition-colors">
            <Sparkles className="size-3.5" />
          </div>
          <span className="font-semibold text-lg tracking-tight text-[#F7F7F2]">
            RepoMedic
          </span>
          <Badge
            variant="outline"
            className="border-[rgba(183,201,173,0.2)] bg-[#15271F]/50 font-mono text-[10px] text-[#A9B8AD] px-1.5 py-0"
          >
            v0.9.4
          </Badge>
        </Link>

        {/* Center: In-page Navigation Links */}
        <nav
          aria-label="Landing page sections"
          className="hidden lg:flex items-center gap-6 text-xs font-medium text-[#A9B8AD]"
        >
          <button
            type="button"
            onClick={() => scrollTo("how-it-works")}
            className="hover:text-[#F7F7F2] transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-[#B7C9AD] rounded"
          >
            How it works
          </button>
          <button
            type="button"
            onClick={() => scrollTo("the-problem")}
            className="hover:text-[#F7F7F2] transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-[#B7C9AD] rounded"
          >
            The Problem
          </button>
          <button
            type="button"
            onClick={() => scrollTo("product-preview")}
            className="hover:text-[#F7F7F2] transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-[#B7C9AD] rounded"
          >
            Preview
          </button>
          <button
            type="button"
            onClick={() => scrollTo("evidence-and-limitations")}
            className="hover:text-[#F7F7F2] transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-[#B7C9AD] rounded"
          >
            Limitations
          </button>
          <a
            href="https://github.com/SGOD-pro/repo-medic"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[#F7F7F2] transition-colors flex items-center gap-1 outline-none focus-visible:ring-1 focus-visible:ring-[#B7C9AD] rounded"
          >
            <span>Docs</span>
            <FileText className="size-3 text-[#A9B8AD]" />
          </a>
        </nav>

        {/* Right: Actions */}
        <div className="flex items-center gap-2.5">
          <Link
            href="/?runId=run-success-1"
            data-testid="landing-nav-view-demo"
            className="hidden sm:inline-flex items-center gap-1.5 h-8 px-3 rounded-lg border border-[rgba(183,201,173,0.25)] bg-[#15271F]/80 hover:bg-[#1B3228] text-[#F7F7F2] text-xs font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-[#B7C9AD]"
          >
            <CheckCircle2 className="size-3.5 text-[#5FCB8A]" />
            <span>Saved Demo</span>
          </Link>

          <Link
            href="/"
            data-testid="landing-nav-launch-app"
            className="inline-flex items-center gap-1.5 h-8 sm:h-9 px-3.5 sm:px-4 rounded-lg bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] text-xs sm:text-sm font-semibold transition-colors shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-[#B7C9AD]"
          >
            <span>Open Workspace</span>
            <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </div>
    </header>
  );
}