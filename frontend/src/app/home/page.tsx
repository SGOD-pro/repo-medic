import type { Metadata } from "next";
import { LandingNavbar } from "@/components/landing-navbar";
import { HomeView } from "@/components/home-view";
import { Footer } from "@/components/footer";

export const metadata: Metadata = {
  title: "RepoMedic — Automated Dependency Regression Repair",
  description:
    "Reproduce a dependency upgrade failure, inspect a candidate patch, and review the verification evidence.",
};

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-[#060908] text-[#F7F7F2] overflow-x-hidden">
      {/* Clean, dedicated landing header */}
      <LandingNavbar />

      {/* Main landing sections with Starlit Abyss nebula aura background */}
      <main className="flex-1 overflow-x-hidden">
        <HomeView />
      </main>

      {/* Shared footer */}
      <Footer />
    </div>
  );
}