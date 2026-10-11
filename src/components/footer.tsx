import React from "react";

export function Footer() {
  return (
    <footer className="mt-auto w-full border-t border-[rgba(183,201,173,0.16)] bg-[#0D1915] py-4 px-6 text-xs text-[#A9B8AD]">
      <div className="mx-auto flex max-w-[1280px] flex-col sm:flex-row items-center justify-between gap-2 font-mono">
        <div className="flex items-center gap-2">
          <span>RepoMedic Runtime Engine</span>
          <span>·</span>
          <span>Isolated Sandboxes Enabled</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="hover:text-[#F7F7F2] transition-colors cursor-pointer">
            API Specs
          </span>
          <span>·</span>
          <span>Telemetry: Synced</span>
        </div>
      </div>
    </footer>
  );
}
