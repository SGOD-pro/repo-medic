import React from "react";

export function Footer() {
  return (
    <footer className="mt-auto w-full border-t border-[rgba(183,201,173,0.16)] bg-[#0D1915] py-4 px-6 text-xs text-[#A9B8AD]">
      <div className="mx-auto flex max-w-[1280px] flex-col sm:flex-row items-center justify-between gap-3 font-mono">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-[#F7F7F2]">RepoMedic</span>
          <span>·</span>
          <span>Automated Dependency Regression Repair</span>
          <span>·</span>
          <span className="text-[#5FCB8A]">Isolated Sandbox Verification</span>
        </div>
        <div className="flex items-center gap-3">
          <a
            href="https://github.com/SGOD-pro/repo-medic"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[#F7F7F2] transition-colors"
          >
            GitHub Repository
          </a>
          <span>·</span>
          <span className="text-[#A9B8AD]">Controlled Demo &amp; Evaluation Mode</span>
        </div>
      </div>
    </footer>
  );
}
