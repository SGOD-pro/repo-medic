"use client";

import React, { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  FolderGit2,
  Package,
  Terminal,
  AlertCircle,
  ShieldCheck,
  CheckCircle2,
  RotateCw,
  Sparkles,
  ArrowRight,
  Info,
  CheckCircle,
  ArrowDown,
  GitBranch,
  Play,
} from "lucide-react";
import {
  CustomRepositoryConfig,
  CustomConfigValidationResponse,
  BranchInfo,
} from "@/lib/contracts";
import { RepoMedicApiClient } from "@/lib/api";

interface CustomRepoFormProps {
  apiClient: RepoMedicApiClient;
  onSelectDemoTask?: (taskId: string) => void;
  onViewSavedRun?: (runId: string) => void;
}

const DEMO_PREFILL: CustomRepositoryConfig = {
  repository_url: "https://github.com/SGOD-pro/repo-medic.git",
  commit_sha: "8c400721558392a23b3af71766f673da02f80040",
  dependency: "sqlalchemy",
  from_version: "1.4.48",
  to_version: "2.0.19",
  pytest_args: ["tests/"],
  allowed_source_paths: ["src/shop/"],
  expected_failure: "AttributeError: 'Engine' object has no attribute 'execute'",
};

export function CustomRepoForm({
  apiClient,
  onSelectDemoTask,
  onViewSavedRun,
}: CustomRepoFormProps) {
  const [formData, setFormData] = useState<CustomRepositoryConfig>({
    repository_url: "",
    commit_sha: "",
    dependency: "",
    from_version: "",
    to_version: "",
    pytest_args: ["tests/"],
    allowed_source_paths: ["src/"],
    expected_failure: "",
  });

  const [pytestArgsRaw, setPytestArgsRaw] = useState<string>("tests/");
  const [allowedPathsRaw, setAllowedPathsRaw] = useState<string>("src/");

  const [branches, setBranches] = useState<BranchInfo[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>("");
  const [isLoadingBranches, setIsLoadingBranches] = useState<boolean>(false);
  const [branchError, setBranchError] = useState<string | null>(null);

  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [validationResult, setValidationResult] =
    useState<CustomConfigValidationResponse | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const [isStartingRun, setIsStartingRun] = useState<boolean>(false);
  const [runError, setRunError] = useState<string | null>(null);

  const handleFieldChange = (field: keyof CustomRepositoryConfig, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (validationResult) {
      setValidationResult(null);
    }
    if (runError) {
      setRunError(null);
    }
  };

  const handleFetchBranches = async (overrideUrl?: string) => {
    const targetUrl = (overrideUrl || formData.repository_url || "").trim();
    if (!targetUrl) {
      setBranchError("Please enter a repository URL first");
      return;
    }
    setIsLoadingBranches(true);
    setBranchError(null);
    try {
      const res = await apiClient.resolveBranches(targetUrl);
      setBranches(res.branches || []);
      const def = res.default_branch || (res.branches.length > 0 ? res.branches[0].name : "");
      setSelectedBranch(def);
      const matched = res.branches.find((b) => b.name === def);
      if (matched) {
        setFormData((prev) => ({ ...prev, commit_sha: matched.commit_sha }));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load branches";
      setBranchError(msg);
    } finally {
      setIsLoadingBranches(false);
    }
  };

  const handleSelectBranch = (branchName: string) => {
    setSelectedBranch(branchName);
    const matched = branches.find((b) => b.name === branchName);
    if (matched) {
      setFormData((prev) => ({ ...prev, commit_sha: matched.commit_sha }));
    }
    if (validationResult) {
      setValidationResult(null);
    }
    if (runError) {
      setRunError(null);
    }
  };

  const handlePytestArgsChange = (val: string) => {
    setPytestArgsRaw(val);
    const split = val
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    setFormData((prev) => ({
      ...prev,
      pytest_args: split.length > 0 ? split : [val.trim()],
    }));
    if (validationResult) setValidationResult(null);
  };

  const handleAllowedPathsChange = (val: string) => {
    setAllowedPathsRaw(val);
    const split = val
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    setFormData((prev) => ({
      ...prev,
      allowed_source_paths: split.length > 0 ? split : [val.trim()],
    }));
    if (validationResult) setValidationResult(null);
  };

  const handlePrefillDemo = () => {
    setFormData(DEMO_PREFILL);
    setPytestArgsRaw(DEMO_PREFILL.pytest_args.join(" "));
    setAllowedPathsRaw(DEMO_PREFILL.allowed_source_paths.join(" "));
    setBranches([
      { name: "fixture/repomedic-demo-shop", commit_sha: "8c400721558392a23b3af71766f673da02f80040" },
      { name: "main", commit_sha: "49e2c4f3277e763906105470ed7e003cbd5a1872" },
    ]);
    setSelectedBranch("fixture/repomedic-demo-shop");
    setValidationResult(null);
    setValidationError(null);
    setBranchError(null);
    setRunError(null);
  };

  const handleValidate = async () => {
    setIsValidating(true);
    setValidationError(null);
    try {
      const resp = await apiClient.validateCustomConfig(formData);
      setValidationResult(resp);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Validation request failed";
      setValidationError(msg);
    } finally {
      setIsValidating(false);
    }
  };

  const handleStartCustomRun = async () => {
    setIsStartingRun(true);
    setRunError(null);
    try {
      const resp = await apiClient.startCustomRun({
        config: formData,
        branch: selectedBranch || "main",
        search_mode: "sequential",
      });
      if (onViewSavedRun && resp.run_id) {
        onViewSavedRun(resp.run_id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Custom repair request failed";
      setRunError(msg);
    } finally {
      setIsStartingRun(false);
    }
  };

  const handleScrollToForm = () => {
    const el = document.getElementById("configure-form-section");
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  const handleOpenSavedDemo = () => {
    if (onViewSavedRun) {
      onViewSavedRun("run_a72af9a70dbc47ee9ba7c7b8b6ff1226");
    } else if (onSelectDemoTask) {
      onSelectDemoTask("TASK-DEMO-SHOP");
    }
  };

  const fieldErrors = validationResult?.field_errors || {};

  return (
    <div
      data-testid="custom-repo-form-view"
      className="mx-auto w-full max-w-[1280px] px-4 sm:px-6 py-6 sm:py-8 space-y-8"
    >
      {/* ------------------------------------------------------------- */}
      {/* SECTION 1: HOME INTRODUCTION & WORKFLOW SEQUENCE              */}
      {/* ------------------------------------------------------------- */}
      <section
        aria-label="Product introduction"
        className="rounded-xl border border-[rgba(183,201,173,0.16)] bg-[#15271F] p-5 sm:p-7"
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-[rgba(183,201,173,0.12)]">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-mono text-[11px] font-semibold tracking-wider uppercase text-[#A9B8AD]">
                AUTOMATED DEPENDENCY REPAIR
              </span>
              <Badge className="bg-[#5FCB8A]/15 text-[#5FCB8A] border-transparent font-mono text-[10px] px-2 py-0">
                CONTROLLED DEMO &amp; SPEC
              </Badge>
            </div>
            <h2 className="text-xl sm:text-2xl lg:text-3xl font-semibold tracking-tight text-[#F7F7F2]">
              Automated Python Dependency Regression Repair
            </h2>
            <p className="mt-2 text-sm sm:text-base text-[#A9B8AD] leading-relaxed">
              RepoMedic reproduces dependency upgrade failures in an isolated environment,
              synthesizes candidate patches, and verifies that existing tests continue to pass.
            </p>
          </div>

          {/* Two Clear Primary Actions: Configure vs View Saved Demo */}
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <Button
              type="button"
              onClick={handleScrollToForm}
              className="h-10 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-xs sm:text-sm px-4 rounded-lg flex items-center gap-2 transition-colors cursor-pointer"
            >
              <FolderGit2 className="size-4" />
              Configure a repository
              <ArrowDown className="size-3.5" />
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handleOpenSavedDemo}
              className="h-10 border-[rgba(183,201,173,0.3)] bg-[#1B3228] text-[#F7F7F2] hover:bg-[#223e32] text-xs sm:text-sm px-4 rounded-lg flex items-center gap-2 transition-colors cursor-pointer"
            >
              <CheckCircle className="size-4 text-[#5FCB8A]" />
              View a saved demo
            </Button>
          </div>
        </div>

        {/* 4-Step Sequence Grid */}
        <div className="mt-6">
          <span className="text-xs font-mono font-medium text-[#A9B8AD] uppercase tracking-wider block mb-3">
            REPAIR WORKFLOW SEQUENCE
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="rounded-lg bg-[#0D1915] p-3.5 border border-[rgba(183,201,173,0.12)]">
              <div className="flex items-center gap-2 mb-1">
                <span className="size-5 rounded-full bg-[#1B3228] border border-[rgba(183,201,173,0.2)] text-[11px] font-mono font-bold flex items-center justify-center text-[#B7C9AD]">
                  1
                </span>
                <span className="text-xs font-semibold text-[#F7F7F2]">Baseline Check</span>
              </div>
              <p className="text-[12px] text-[#A9B8AD] leading-relaxed">
                Confirm pinned commit passes all test suites before bumping dependency versions.
              </p>
            </div>

            <div className="rounded-lg bg-[#0D1915] p-3.5 border border-[rgba(183,201,173,0.12)]">
              <div className="flex items-center gap-2 mb-1">
                <span className="size-5 rounded-full bg-[#1B3228] border border-[rgba(183,201,173,0.2)] text-[11px] font-mono font-bold flex items-center justify-center text-[#B7C9AD]">
                  2
                </span>
                <span className="text-xs font-semibold text-[#F7F7F2]">Upgrade Failure</span>
              </div>
              <p className="text-[12px] text-[#A9B8AD] leading-relaxed">
                Install target dependency version and record exact stack breakage in clean container.
              </p>
            </div>

            <div className="rounded-lg bg-[#0D1915] p-3.5 border border-[rgba(183,201,173,0.12)]">
              <div className="flex items-center gap-2 mb-1">
                <span className="size-5 rounded-full bg-[#1B3228] border border-[rgba(183,201,173,0.2)] text-[11px] font-mono font-bold flex items-center justify-center text-[#B7C9AD]">
                  3
                </span>
                <span className="text-xs font-semibold text-[#F7F7F2]">Candidate Patch</span>
              </div>
              <p className="text-[12px] text-[#A9B8AD] leading-relaxed">
                Synthesize and rank source modifications while keeping test files strictly immutable.
              </p>
            </div>

            <div className="rounded-lg bg-[#0D1915] p-3.5 border border-[rgba(183,201,173,0.12)]">
              <div className="flex items-center gap-2 mb-1">
                <span className="size-5 rounded-full bg-[#1B3228] border border-[rgba(183,201,173,0.2)] text-[11px] font-mono font-bold flex items-center justify-center text-[#5FCB8A]">
                  4
                </span>
                <span className="text-xs font-semibold text-[#F7F7F2]">Verification</span>
              </div>
              <p className="text-[12px] text-[#A9B8AD] leading-relaxed">
                Run tests against candidate patch, collect output log, and produce verified diff.
              </p>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[rgba(183,201,173,0.08)] flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-[#A9B8AD]">
            <p>
              Controlled examples: <span className="font-mono text-[#F7F7F2]">repomedic-demo-shop</span> has one collected test;
              success demonstrates the repair workflow, not general multi-test reliability. Patches are reviewed and applied by the developer.
            </p>
            <span className="font-mono text-[11px] shrink-0 text-[#A9B8AD]">
              Python 3.12 · Pytest
            </span>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* SECTION 2: CONFIGURE REPOSITORY (FORM & IMMEDIATE VALIDATION) */}
      {/* ------------------------------------------------------------- */}
      <section
        id="configure-form-section"
        aria-label="Repository configuration form"
        className="space-y-6"
      >
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <span className="font-mono text-xs font-medium tracking-[0.06em] uppercase text-[#A9B8AD]">
              CUSTOM REPOSITORY INTAKE / SAFE PRODUCT SLICE
            </span>
            <h1 className="mt-1 text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight text-[#F7F7F2]">
              Configure Custom Repository
            </h1>
            <p className="mt-1.5 text-xs sm:text-sm text-[#A9B8AD] max-w-2xl leading-relaxed">
              Specify a public Python repository, pinned commit SHA, upgrade dependency,
              and test suite arguments. RepoMedic validates repository specifications
              against contract constraints.
            </p>
          </div>

          {/* Quick Demo Pre-fill Action */}
          <div className="flex items-center gap-2.5 shrink-0">
            <Button
              type="button"
              onClick={handlePrefillDemo}
              variant="outline"
              size="sm"
              className="border-[rgba(183,201,173,0.3)] bg-[#15271F] text-[#F7F7F2] hover:bg-[#1B3228] text-xs h-9 px-3 gap-1.5 rounded-lg cursor-pointer"
            >
              <Sparkles className="size-3.5 text-[#5FCB8A]" />
              Pre-fill with Demo Values
            </Button>
            {onSelectDemoTask && (
              <Button
                type="button"
                data-testid="btn-try-a-demo"
                onClick={() => onSelectDemoTask("TASK-DEMO-SHOP")}
                size="sm"
                className="bg-[#1B3228] border border-[rgba(183,201,173,0.2)] text-[#B7C9AD] hover:bg-[#203c30] text-xs h-9 px-3 gap-1 rounded-lg cursor-pointer"
              >
                <span>Try a demo</span>
                <ArrowRight className="size-3.5" />
              </Button>
            )}
          </div>
        </div>

        {/* Supported Scope Banner */}
        <div className="rounded-xl border border-[#5FCB8A]/30 bg-[#15271F] p-3.5 sm:p-4 flex flex-col sm:flex-row sm:items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="size-4 sm:size-5 text-[#5FCB8A] shrink-0 mt-0.5" />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-xs sm:text-sm text-[#F7F7F2]">
                  Custom Python repository repair execution is active.
                </span>
                <Badge className="bg-[#5FCB8A]/20 text-[#5FCB8A] border-transparent font-mono text-[10px] px-1.5 py-0">
                  EXECUTION ACTIVE
                </Badge>
              </div>
              <p className="mt-1 text-xs text-[#A9B8AD] leading-relaxed">
                Configure your public GitHub repository, select a branch to pin the commit SHA, and define dependency targets. RepoMedic validates configuration constraints and runs repairs in isolated environments.
              </p>
            </div>
          </div>
          {onSelectDemoTask && (
            <button
              type="button"
              data-testid="btn-try-a-demo-banner"
              onClick={() => onSelectDemoTask("TASK-DEMO-SHOP")}
              className="text-xs font-medium text-[#5FCB8A] hover:underline cursor-pointer inline-flex items-center gap-1 shrink-0 self-end sm:self-auto"
            >
              View supported demo <ArrowRight className="size-3" />
            </button>
          )}
        </div>

        {/* Balanced 2-Column Form Card */}
        <Card className="rounded-xl bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-5 sm:p-7 shadow-none">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void handleValidate();
            }}
            className="space-y-6"
          >
            {/* Group 1: Repository and Revision */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <FolderGit2 className="size-4 text-[#5FCB8A]" />
                <h2 className="text-sm font-semibold text-[#F7F7F2]">
                  Repository &amp; Commit Specification
                </h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                <div className="md:col-span-5">
                  <label
                    htmlFor="repository_url"
                    className="block text-xs font-mono font-medium text-[#A9B8AD] mb-1.5"
                  >
                    Public GitHub HTTPS URL <span className="text-[#E5736A]">*</span>
                  </label>
                  <div className="flex gap-2">
                    <Input
                      id="repository_url"
                      data-testid="input-repository-url"
                      type="text"
                      value={formData.repository_url}
                      onChange={(e) =>
                        handleFieldChange("repository_url", e.target.value)
                      }
                      placeholder="https://github.com/owner/repository"
                      aria-invalid={Boolean(fieldErrors.repository_url)}
                      aria-describedby="repository_url_help"
                      className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-10 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
                    />
                    <Button
                      type="button"
                      data-testid="btn-fetch-branches"
                      onClick={() => void handleFetchBranches()}
                      disabled={isLoadingBranches || !formData.repository_url.trim()}
                      className="h-10 px-3 bg-[#1B3228] hover:bg-[#234235] text-[#5FCB8A] border border-[rgba(183,201,173,0.2)] text-xs font-mono rounded-lg shrink-0 cursor-pointer disabled:opacity-40"
                    >
                      {isLoadingBranches ? (
                        <RotateCw className="size-3.5 animate-spin" />
                      ) : (
                        <GitBranch className="size-3.5" />
                      )}
                      <span className="hidden sm:inline ml-1.5">Load</span>
                    </Button>
                  </div>
                  <span id="repository_url_help" className="block mt-1 text-[11px] text-[#A9B8AD]">
                    Public GitHub repository. Remote refs are queried via read only git ls remote.
                  </span>
                  {branchError && (
                    <span className="block mt-1 text-xs text-[#E5736A] font-mono">
                      {branchError}
                    </span>
                  )}
                  {fieldErrors.repository_url?.map((err, i) => (
                    <span
                      key={i}
                      className="block mt-1 text-xs text-[#E5736A] font-mono"
                    >
                      {err}
                    </span>
                  ))}
                </div>

                <div className="md:col-span-3">
                  <label
                    htmlFor="branch_select"
                    className="block text-xs font-mono font-medium text-[#A9B8AD] mb-1.5"
                  >
                    Select Git Branch
                  </label>
                  <select
                    id="branch_select"
                    data-testid="select-branch"
                    value={selectedBranch}
                    onChange={(e) => handleSelectBranch(e.target.value)}
                    disabled={branches.length === 0}
                    className="w-full bg-[#0D1915] border border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-10 rounded-md px-3 focus:outline-none focus:ring-1 focus:ring-[#5FCB8A] disabled:opacity-50"
                  >
                    {branches.length === 0 ? (
                      <option value="">No branches loaded</option>
                    ) : (
                      branches.map((b) => (
                        <option key={b.name} value={b.name}>
                          {b.name}
                        </option>
                      ))
                    )}
                  </select>
                  <span className="block mt-1 text-[11px] text-[#A9B8AD]">
                    {branches.length > 0
                      ? `${branches.length} branches discovered`
                      : "Click Load to fetch branches"}
                  </span>
                </div>

                <div className="md:col-span-4">
                  <div className="flex items-center justify-between mb-1.5">
                    <label
                      htmlFor="commit_sha"
                      className="block text-xs font-mono font-medium text-[#A9B8AD]"
                    >
                      Pinned Commit SHA <span className="text-[#E5736A]">*</span>
                    </label>
                    {selectedBranch && (
                      <span className="text-[10px] font-mono text-[#5FCB8A] uppercase tracking-wide">
                        Pinned from {selectedBranch}
                      </span>
                    )}
                  </div>
                  <Input
                    id="commit_sha"
                    data-testid="input-commit-sha"
                    type="text"
                    value={formData.commit_sha}
                    onChange={(e) =>
                      handleFieldChange("commit_sha", e.target.value)
                    }
                    placeholder="e.g. 8c400721558392a23b3af71766f673da02f80040"
                    aria-invalid={Boolean(fieldErrors.commit_sha)}
                    aria-describedby="commit_sha_help"
                    className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-10 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
                  />
                  <span id="commit_sha_help" className="block mt-1 text-[11px] text-[#A9B8AD]">
                    Exact 40 character commit hash pinned for immutable execution.
                  </span>
                  {fieldErrors.commit_sha?.map((err, i) => (
                    <span
                      key={i}
                      className="block mt-1 text-xs text-[#E5736A] font-mono"
                    >
                      {err}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Group 2: Dependency and Versions */}
            <div className="pt-4 border-t border-[rgba(183,201,173,0.12)]">
              <div className="flex items-center gap-2 mb-3">
                <Package className="size-4 text-[#7FB3D5]" />
                <h2 className="text-sm font-semibold text-[#F7F7F2]">
                  Dependency Upgrade Configuration
                </h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                <div className="md:col-span-4">
                  <label
                    htmlFor="dependency"
                    className="block text-xs font-mono font-medium text-[#A9B8AD] mb-1.5"
                  >
                    Python Package Name <span className="text-[#E5736A]">*</span>
                  </label>
                  <Input
                    id="dependency"
                    data-testid="input-dependency"
                    type="text"
                    value={formData.dependency}
                    onChange={(e) =>
                      handleFieldChange("dependency", e.target.value)
                    }
                    placeholder="e.g. sqlalchemy, pydantic, httpx"
                    aria-invalid={Boolean(fieldErrors.dependency)}
                    className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-10 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
                  />
                  {fieldErrors.dependency?.map((err, i) => (
                    <span
                      key={i}
                      className="block mt-1 text-xs text-[#E5736A] font-mono"
                    >
                      {err}
                    </span>
                  ))}
                </div>

                <div className="md:col-span-4">
                  <label
                    htmlFor="from_version"
                    className="block text-xs font-mono font-medium text-[#A9B8AD] mb-1.5"
                  >
                    Baseline Version <span className="text-[#E5736A]">*</span>
                  </label>
                  <Input
                    id="from_version"
                    data-testid="input-from-version"
                    type="text"
                    value={formData.from_version}
                    onChange={(e) =>
                      handleFieldChange("from_version", e.target.value)
                    }
                    placeholder="e.g. 1.4.48"
                    aria-invalid={Boolean(fieldErrors.from_version)}
                    className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-10 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
                  />
                  {fieldErrors.from_version?.map((err, i) => (
                    <span
                      key={i}
                      className="block mt-1 text-xs text-[#E5736A] font-mono"
                    >
                      {err}
                    </span>
                  ))}
                </div>

                <div className="md:col-span-4">
                  <label
                    htmlFor="to_version"
                    className="block text-xs font-mono font-medium text-[#A9B8AD] mb-1.5"
                  >
                    Target Version <span className="text-[#E5736A]">*</span>
                  </label>
                  <Input
                    id="to_version"
                    data-testid="input-to-version"
                    type="text"
                    value={formData.to_version}
                    onChange={(e) =>
                      handleFieldChange("to_version", e.target.value)
                    }
                    placeholder="e.g. 2.0.19"
                    aria-invalid={Boolean(fieldErrors.to_version)}
                    className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-10 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
                  />
                  {fieldErrors.to_version?.map((err, i) => (
                    <span
                      key={i}
                      className="block mt-1 text-xs text-[#E5736A] font-mono"
                    >
                      {err}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Group 3: Test Command, Allowed Paths, and Expected Failure */}
            <div className="pt-4 border-t border-[rgba(183,201,173,0.12)]">
              <div className="flex items-center gap-2 mb-3">
                <Terminal className="size-4 text-[#5FCB8A]" />
                <h2 className="text-sm font-semibold text-[#F7F7F2]">
                  Test Command &amp; Source Constraints
                </h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                <div className="md:col-span-6">
                  <label
                    htmlFor="pytest_args"
                    className="block text-xs font-mono font-medium text-[#A9B8AD] mb-1.5"
                  >
                    Pytest Arguments <span className="text-[#E5736A]">*</span>
                  </label>
                  <Input
                    id="pytest_args"
                    data-testid="input-pytest-args"
                    type="text"
                    value={pytestArgsRaw}
                    onChange={(e) => handlePytestArgsChange(e.target.value)}
                    placeholder="tests/"
                    aria-invalid={Boolean(fieldErrors.pytest_args)}
                    aria-describedby="pytest_args_help"
                    className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-10 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
                  />
                  <span id="pytest_args_help" className="block mt-1 text-[11px] text-[#A9B8AD]">
                    Arguments passed to pytest runner. Shell metacharacters are rejected.
                  </span>
                  {fieldErrors.pytest_args?.map((err, i) => (
                    <span
                      key={i}
                      className="block mt-1 text-xs text-[#E5736A] font-mono"
                    >
                      {err}
                    </span>
                  ))}
                </div>

                <div className="md:col-span-6">
                  <label
                    htmlFor="allowed_source_paths"
                    className="block text-xs font-mono font-medium text-[#A9B8AD] mb-1.5"
                  >
                    Allowed Source Paths (Allowlist) <span className="text-[#E5736A]">*</span>
                  </label>
                  <Input
                    id="allowed_source_paths"
                    data-testid="input-allowed-paths"
                    type="text"
                    value={allowedPathsRaw}
                    onChange={(e) => handleAllowedPathsChange(e.target.value)}
                    placeholder="src/ or src/shop/"
                    aria-invalid={Boolean(fieldErrors.allowed_source_paths)}
                    aria-describedby="allowed_paths_help"
                    className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-10 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
                  />
                  <span id="allowed_paths_help" className="block mt-1 text-[11px] text-[#A9B8AD]">
                    Relative paths allowed for candidate patches. Tests are always immutable.
                  </span>
                  {fieldErrors.allowed_source_paths?.map((err, i) => (
                    <span
                      key={i}
                      className="block mt-1 text-xs text-[#E5736A] font-mono"
                    >
                      {err}
                    </span>
                  ))}
                </div>

                <div className="md:col-span-12">
                  <label
                    htmlFor="expected_failure"
                    className="block text-xs font-mono font-medium text-[#A9B8AD] mb-1.5"
                  >
                    Expected Failure Substring <span className="text-[#E5736A]">*</span>
                  </label>
                  <Input
                    id="expected_failure"
                    data-testid="input-expected-failure"
                    type="text"
                    value={formData.expected_failure}
                    onChange={(e) =>
                      handleFieldChange("expected_failure", e.target.value)
                    }
                    placeholder="e.g. AttributeError: 'Engine' object has no attribute 'execute'"
                    aria-invalid={Boolean(fieldErrors.expected_failure)}
                    aria-describedby="expected_failure_help"
                    className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-10 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
                  />
                  <span id="expected_failure_help" className="block mt-1 text-[11px] text-[#A9B8AD]">
                    Substring that must appear in test failure output after upgrading dependency.
                  </span>
                  {fieldErrors.expected_failure?.map((err, i) => (
                    <span
                      key={i}
                      className="block mt-1 text-xs text-[#E5736A] font-mono"
                    >
                      {err}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* ------------------------------------------------------------- */}
            {/* ACTIONS IMMEDIATELY FOLLOWING FORM (NO DETACHED RIGHT PANEL)  */}
            {/* ------------------------------------------------------------- */}
            <div className="pt-4 border-t border-[rgba(183,201,173,0.12)] flex flex-wrap items-center gap-3">
              <Button
                type="submit"
                data-testid="btn-validate-config"
                disabled={isValidating}
                className="h-11 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-xs sm:text-sm px-5 rounded-lg flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-none disabled:opacity-50"
              >
                {isValidating ? (
                  <>
                    <RotateCw className="size-4 animate-spin" />
                    Validating Configuration...
                  </>
                ) : (
                  <>
                    <ShieldCheck className="size-4" />
                    Validate Configuration
                  </>
                )}
              </Button>

              <Button
                type="button"
                onClick={handlePrefillDemo}
                variant="outline"
                className="h-11 border-[rgba(183,201,173,0.3)] bg-[#0D1915] text-[#F7F7F2] hover:bg-[#1B3228] text-xs sm:text-sm px-4 rounded-lg flex items-center gap-2 cursor-pointer"
              >
                <Sparkles className="size-4 text-[#5FCB8A]" />
                Use demo values
              </Button>

              {onSelectDemoTask && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => onSelectDemoTask("TASK-DEMO-SHOP")}
                  className="h-11 text-[#A9B8AD] hover:text-[#F7F7F2] hover:bg-[#1B3228] text-xs sm:text-sm px-4 rounded-lg flex items-center gap-1.5 cursor-pointer"
                >
                  View demo <ArrowRight className="size-3.5" />
                </Button>
              )}

              {/* Custom execution action */}
              <div className="ml-auto w-full sm:w-auto">
                <Button
                  type="button"
                  data-testid="btn-run-custom-repair"
                  onClick={() => void handleStartCustomRun()}
                  disabled={
                    isStartingRun ||
                    !formData.repository_url.trim() ||
                    !formData.dependency.trim()
                  }
                  className="w-full sm:w-auto h-11 bg-[#1B3228] hover:bg-[#234235] text-[#5FCB8A] border border-[#5FCB8A]/40 font-semibold text-xs sm:text-sm px-4 rounded-lg flex items-center justify-center gap-2 cursor-pointer shadow-none disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Submit custom repository repair run"
                >
                  {isStartingRun ? (
                    <>
                      <RotateCw className="size-4 animate-spin" />
                      Starting Repair Run...
                    </>
                  ) : (
                    <>
                      <Play className="size-4 fill-current text-[#5FCB8A]" />
                      <span>Start Custom Repair Run</span>
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* ------------------------------------------------------------- */}
            {/* VALIDATION RESULTS SECTION (IMMEDIATELY AFTER ACTIONS)        */}
            {/* ------------------------------------------------------------- */}
            <div className="pt-2">
              {validationResult ? (
                validationResult.valid ? (
                  <div
                    data-testid="validation-success-box"
                    className="rounded-xl bg-[#1B3228]/80 border border-[#5FCB8A]/40 p-4"
                  >
                    <div className="flex items-center gap-2.5 mb-1.5">
                      <CheckCircle2 className="size-5 text-[#5FCB8A] shrink-0" />
                      <span className="text-sm font-semibold text-[#F7F7F2]">
                        Repository Specification Valid · Format and Contract Rules Passed
                      </span>
                    </div>
                    <p className="text-xs text-[#A9B8AD] leading-relaxed">
                      Input format, syntax, and schema constraints passed all local checks. Pinned branch resolution succeeded. You can now start the custom repair run to execute the automated repair workflow.
                    </p>
                  </div>
                ) : (
                  <div
                    data-testid="validation-error-box"
                    className="rounded-xl bg-[#241414] border border-[#E5736A]/40 p-4"
                  >
                    <div className="flex items-center gap-2.5 mb-2">
                      <AlertCircle className="size-5 text-[#E5736A] shrink-0" />
                      <span className="text-sm font-semibold text-[#F7F7F2]">
                        Validation Issues ({validationResult.errors.length})
                      </span>
                    </div>
                    <ul className="text-xs font-mono text-[#E5736A] space-y-1 list-disc pl-5">
                      {validationResult.errors.map((err, idx) => (
                        <li key={idx}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )
              ) : (
                <div className="rounded-xl bg-[#0D1915] border border-[rgba(183,201,173,0.12)] p-3.5 text-xs text-[#A9B8AD] flex items-center gap-2.5">
                  <Info className="size-4 text-[#7FB3D5] shrink-0" />
                  <span>
                    Validation checks format and contract rules locally. It does not establish repository reachability, commit existence, or sandbox safety.
                  </span>
                </div>
              )}

              {validationError && (
                <div className="mt-3 rounded-xl bg-[#241414] border border-[#E5736A]/40 p-3 text-xs font-mono text-[#E5736A]">
                  {validationError}
                </div>
              )}

              {runError && (
                <div
                  data-testid="custom-run-error-box"
                  className="mt-3 rounded-xl bg-[#241414] border border-[#E5736A]/40 p-4 space-y-2"
                >
                  <div className="flex items-center gap-2 text-sm font-semibold text-[#E5736A]">
                    <AlertCircle className="size-4 shrink-0" />
                    <span>Execution Gated by Security Policy</span>
                  </div>
                  <p className="text-xs text-[#E5736A] font-mono leading-relaxed">
                    {runError}
                  </p>
                </div>
              )}
            </div>
          </form>
        </Card>
      </section>
    </div>
  );
}
