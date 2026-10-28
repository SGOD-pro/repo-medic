"use client";

import React, { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  FolderGit2,
  GitCommit,
  Package,
  Layers,
  Terminal,
  FileCode,
  AlertCircle,
  ShieldCheck,
  CheckCircle2,
  Lock,
  RotateCw,
  Sparkles,
  ArrowRight,
  Info,
} from "lucide-react";
import {
  CustomRepositoryConfig,
  CustomConfigValidationResponse,
} from "@/lib/contracts";
import { RepoMedicApiClient } from "@/lib/api";

interface CustomRepoFormProps {
  apiClient: RepoMedicApiClient;
  onSelectDemoTask?: (taskId: string) => void;
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

  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [validationResult, setValidationResult] =
    useState<CustomConfigValidationResponse | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleFieldChange = (field: keyof CustomRepositoryConfig, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear validation result on change to encourage re-validation
    if (validationResult) {
      setValidationResult(null);
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
    setValidationResult(null);
    setValidationError(null);
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

  const fieldErrors = validationResult?.field_errors || {};

  return (
    <div
      data-testid="custom-repo-form-view"
      className="mx-auto w-full max-w-[1280px] px-6 py-8"
    >
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 pb-6">
        <div>
          <span className="font-mono text-xs font-medium tracking-[0.06em] uppercase text-[#A9B8AD]">
            CUSTOM REPOSITORY INTAKE / SAFE PRODUCT SLICE
          </span>
          <h1 className="mt-1 text-3xl md:text-4xl font-semibold tracking-tight text-[#F7F7F2]">
            Configure Custom Repository
          </h1>
          <p className="mt-2 text-sm text-[#A9B8AD] max-w-2xl leading-relaxed">
            Specify an open source Python repository, pinned commit SHA, upgrade
            dependency, and test suite arguments. RepoMedic validates repository
            specifications against contract constraints.
          </p>
        </div>

        {/* Quick Demo Pre-fill Action */}
        <div className="flex items-center gap-3">
          <Button
            type="button"
            onClick={handlePrefillDemo}
            variant="outline"
            size="sm"
            className="border-[rgba(183,201,173,0.3)] bg-[#15271F] text-[#F7F7F2] hover:bg-[#1B3228] text-xs h-9 px-3.5 gap-2 rounded-lg cursor-pointer"
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
              className="bg-[#1B3228] border border-[rgba(183,201,173,0.2)] text-[#B7C9AD] hover:bg-[#203c30] text-xs h-9 px-3.5 gap-1.5 rounded-lg cursor-pointer"
            >
              <span>Try a demo</span>
              <ArrowRight className="size-3.5" />
            </Button>
          )}
        </div>
      </div>

      {/* Safety Notice Banner */}
      <div className="mb-8 rounded-2xl border border-[#E0B45A]/30 bg-[#1D1A14] p-4 flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Lock className="size-5 text-[#E0B45A] shrink-0 mt-0.5" />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-[#F7F7F2]">
                Safe Product Slice · Execution Gate Disabled
              </span>
              <Badge className="bg-[#E0B45A]/20 text-[#E0B45A] border-transparent font-mono text-[10px] px-2 py-0">
                GATED OFF
              </Badge>
            </div>
            <p className="mt-1 text-xs text-[#C8BA9D] leading-relaxed">
              Custom repository validation is live and evaluates repository
              syntax, commit SHAs, versions, and paths. Arbitrary remote
              execution, sandbox worker enqueueing, and LLM calls are strictly
              gated off to prevent unauthorized remote execution or cloud spend.
            </p>
            {onSelectDemoTask && (
              <div className="mt-2.5 flex items-center gap-2">
                <span className="text-xs text-[#A9B8AD]">Looking to run a verified repair?</span>
                <button
                  type="button"
                  data-testid="btn-try-a-demo-banner"
                  onClick={() => onSelectDemoTask("TASK-DEMO-SHOP")}
                  className="text-xs font-medium text-[#5FCB8A] hover:underline cursor-pointer inline-flex items-center gap-1"
                >
                  Try a demo scenario <ArrowRight className="size-3" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main 2-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Form Fields (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-5">
          <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-6">
            <h2 className="text-base font-semibold text-[#F7F7F2] mb-4 flex items-center gap-2">
              <FolderGit2 className="size-4 text-[#5FCB8A]" />
              Repository &amp; Commit Specification
            </h2>

            {/* Field: repository_url */}
            <div className="mb-4">
              <label
                htmlFor="repository_url"
                className="block text-xs font-mono font-medium text-[#A9B8AD] mb-1.5"
              >
                Public GitHub HTTPS URL <span className="text-[#E5736A]">*</span>
              </label>
              <Input
                id="repository_url"
                data-testid="input-repository-url"
                type="text"
                value={formData.repository_url}
                onChange={(e) =>
                  handleFieldChange("repository_url", e.target.value)
                }
                placeholder="https://github.com/owner/repository"
                className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-9 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
              />
              <span className="block mt-1 text-[11px] text-[#A9B8AD]">
                Requires a GitHub HTTPS repository URL. Format is checked locally; remote repository reachability is not verified across the network in this slice.
              </span>
              {fieldErrors.repository_url?.map((err, i) => (
                <span
                  key={i}
                  className="block mt-1 text-xs text-[#E5736A] font-mono"
                >
                  {err}
                </span>
              ))}
            </div>

            {/* Field: commit_sha */}
            <div className="mb-6">
              <label
                htmlFor="commit_sha"
                className="block text-xs font-mono font-medium text-[#A9B8AD] mb-1.5"
              >
                Target Commit SHA (40-char Hex) <span className="text-[#E5736A]">*</span>
              </label>
              <Input
                id="commit_sha"
                data-testid="input-commit-sha"
                type="text"
                value={formData.commit_sha}
                onChange={(e) =>
                  handleFieldChange("commit_sha", e.target.value)
                }
                placeholder="e.g. 8c400721558392a23b3af71766f673da02f80040"
                className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-9 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
              />
              <span className="block mt-1 text-[11px] text-[#A9B8AD]">
                Exact 40 character hexadecimal commit hash. Format is checked locally; commit existence on GitHub is not verified across the network.
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

            <h2 className="text-base font-semibold text-[#F7F7F2] mb-4 flex items-center gap-2 pt-2 border-t border-[rgba(183,201,173,0.12)]">
              <Package className="size-4 text-[#7FB3D5]" />
              Dependency Upgrade Configuration
            </h2>

            {/* Field: dependency */}
            <div className="mb-4">
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
                className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-9 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
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

            {/* 2-col: from_version & to_version */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
              <div>
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
                  className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-9 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
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

              <div>
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
                  className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-9 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
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

            <h2 className="text-base font-semibold text-[#F7F7F2] mb-4 flex items-center gap-2 pt-2 border-t border-[rgba(183,201,173,0.12)]">
              <Terminal className="size-4 text-[#5FCB8A]" />
              Test Suite &amp; Source Constraints
            </h2>

            {/* Field: pytest_args */}
            <div className="mb-4">
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
                className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-9 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
              />
              <span className="block mt-1 text-[11px] text-[#A9B8AD]">
                Passed directly to pytest runner inside isolated sandbox container.
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

            {/* Field: allowed_source_paths */}
            <div className="mb-4">
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
                className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-9 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
              />
              <span className="block mt-1 text-[11px] text-[#A9B8AD]">
                Only files under these relative paths may be modified. Tests are always immutable.
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

            {/* Field: expected_failure */}
            <div className="mb-2">
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
                className="bg-[#0D1915] border-[rgba(183,201,173,0.2)] text-xs font-mono text-[#F7F7F2] h-9 focus-visible:ring-1 focus-visible:ring-[#5FCB8A]"
              />
              <span className="block mt-1 text-[11px] text-[#A9B8AD]">
                Substring that must appear in stderr/stdout after upgrading dependency.
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
          </Card>
        </div>

        {/* Right Column: Validation & Gate Status (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <Card className="rounded-[20px] bg-[#15271F] border border-[rgba(183,201,173,0.16)] p-6">
            <span className="font-mono text-xs tracking-wider text-[#A9B8AD] uppercase">
              VALIDATION &amp; GATE ENFORCEMENT
            </span>

            <h3 className="text-lg font-semibold text-[#F7F7F2] mt-1 mb-4">
              Contract Specification Status
            </h3>

            {/* Validation State Box */}
            {validationResult ? (
              validationResult.valid ? (
                <div
                  data-testid="validation-success-box"
                  className="rounded-xl bg-[#1B3228]/80 border border-[#5FCB8A]/40 p-4 mb-4"
                >
                  <div className="flex items-center gap-2.5 mb-1.5">
                    <CheckCircle2 className="size-5 text-[#5FCB8A]" />
                    <span className="text-sm font-semibold text-[#F7F7F2]">
                      Format and Schema Constraints Valid
                    </span>
                  </div>
                  <p className="text-xs text-[#A9B8AD] leading-relaxed">
                    Input format, syntax, and schema constraints passed all local checks.
                    Remote repository reachability and commit existence on GitHub have not been verified across the network.
                  </p>
                </div>
              ) : (
                <div
                  data-testid="validation-error-box"
                  className="rounded-xl bg-[#241414] border border-[#E5736A]/40 p-4 mb-4"
                >
                  <div className="flex items-center gap-2.5 mb-2">
                    <AlertCircle className="size-5 text-[#E5736A]" />
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
              <div className="rounded-xl bg-[#0D1915] border border-[rgba(183,201,173,0.12)] p-4 mb-4 text-xs text-[#A9B8AD]">
                <div className="flex items-center gap-2 mb-1 text-[#F7F7F2] font-medium">
                  <Info className="size-4 text-[#7FB3D5]" />
                  <span>Validation Pending</span>
                </div>
                <span>
                  Click &ldquo;Validate Configuration&rdquo; to verify local syntax and contract constraints.
                  Network accessibility is not checked in this slice.
                </span>
              </div>
            )}

            {validationError && (
              <div className="rounded-xl bg-[#241414] border border-[#E5736A]/40 p-3 mb-4 text-xs font-mono text-[#E5736A]">
                {validationError}
              </div>
            )}

            {/* Gate Status Pill */}
            <div className="rounded-xl bg-[#0D1915] border border-[rgba(183,201,173,0.12)] p-4 mb-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono text-[#A9B8AD]">
                  EXECUTION GATE STATUS
                </span>
                <Badge className="bg-[#E0B45A]/20 text-[#E0B45A] border-transparent font-mono text-[10px] px-2 py-0">
                  DISABLED
                </Badge>
              </div>
              <p className="text-xs text-[#A9B8AD] leading-relaxed">
                {validationResult?.gate_message ||
                  "Custom repository execution is disabled in this safe product slice. Arbitrary remote execution, background worker enqueueing, provider calls, and task execution are strictly gated off."}
              </p>
            </div>

            {/* Primary Action 1: Validate Configuration */}
            <Button
              type="button"
              data-testid="btn-validate-config"
              disabled={isValidating}
              onClick={handleValidate}
              className="w-full h-11 bg-[#B7C9AD] hover:bg-[#C8D8BF] text-[#102D25] font-semibold text-sm rounded-lg flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-none disabled:opacity-50 mb-3"
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

            {/* Primary Action 2: Run Repair (Hard Disabled Gate) */}
            <div className="relative">
              <Button
                type="button"
                data-testid="btn-run-custom-repair"
                disabled
                className="w-full h-11 bg-[#1B3228] text-[#A9B8AD] font-semibold text-sm rounded-lg flex items-center justify-center gap-2 opacity-50 cursor-not-allowed shadow-none"
              >
                <Lock className="size-4" />
                Start Repair Run (Execution Gated)
              </Button>
            </div>

            <p className="mt-3 text-[11px] text-[#A9B8AD] text-center leading-relaxed">
              Execution gate protects system stability. For an active end-to-end
              repair demonstration, please choose a curated demo scenario.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
