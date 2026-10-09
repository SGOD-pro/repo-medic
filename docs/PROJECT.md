# RepoMedic — Project plan

Version 0.4 · 2026-10-09 · Status: specification only; implementation and results unverified.

## 1. Product and submission thesis

RepoMedic repairs Python dependency upgrades that break an existing pytest suite. It explores isolated candidate patches, uses failures to refine them, and exports a patch verified against preserved tests with the requested dependency installed.

Track: **Coding and Agentic Engineering**. This deliberately supersedes the earlier Apps/Personal AI direction.

Pitch: **“Upgrade the dependency, repair the breakage, inspect the evidence.”**

The contribution is dependency-specific repair and evaluation of when branching helps. Forkable sandboxes, coding agents, and dependency remediation already exist. Do not claim first-of-kind technology, tamper-proof execution, or guaranteed behavioral equivalence.

The winning case must be earned through working software, a coherent developer workflow, real upgrade examples, and fair comparisons. These documents do not estimate winning probability.

## 2. Canonical decisions

| Decision | MVP choice |
|---|---|
| Inference | NVIDIA Nemotron through Nebius Token Factory only for live runs and headline evaluation |
| Execution | Token Factory Sandboxes through a pinned ConTree client/SDK integration |
| Models | One confirmed Nemotron model for diagnosis/generation initially; Nano/Ultra optional after measurement |
| App | Static Next.js frontend plus FastAPI modular monolith |
| Hosting | One persistent-disk host using existing credits; frontend served by the same HTTPS origin where possible |
| Database | SQLite in WAL mode; authoritative run state, events, ownership and budgets |
| Artifacts | Private filesystem directory on persistent disk; checksummed paths referenced by SQLite |
| S3 | Not required for MVP; optional backup/export later |
| Auth | No account signup or OAuth; lightweight access-code exchange for live sessions and run ownership |
| Public inputs | Curated task IDs mapped to pinned public repositories; no arbitrary URL/command execution |
| Developer use | Local CLI may accept additional public repositories with explicit recipe configuration |
| Runtime | Durable jobs executed by one bounded worker loop; no Redis/Celery/microservices |
| Demo | Live curated repair plus clearly labeled real replay; replay is not a replacement for a working test build |

Auth to Nebius is separate from app auth. Server-only model and sandbox credentials never enter the browser, repository checkout, or sandbox environment. Sandbox authentication/project setup may differ from inference; verify both.

## 3. Scope

P0: authenticated live session, curated tasks, baseline/bump checks, sequential repair, branch-and-refine, fresh verification, patch/evidence downloads, restart handling, cancellation, budgets, branch UI, replay, matched-budget evaluation, reproducible installation.

P1: independent-candidate arm, richer diff viewer, maintainer feedback, optional model routing, grounded migration-note retrieval with saved URLs and excerpts.

Out: private repositories, GitHub App/OAuth, automated PRs or merging, arbitrary public sandbox jobs, other languages, billing, team workspaces, vector databases, enterprise authentication.

Local Docker remains an optional offline development adapter, not a qualifying public execution path or a headline benchmark mixed with Sandboxes. Do not build two complete executor integrations before the Token Factory path works.

## 4. Platform validation — first implementation gate

Account access is user-reported, not tool-tested here. Before building around it:

1. Confirm inference credentials, endpoint, exact available model ID, output limits, reasoning settings and prices in the account.
2. Confirm Sandboxes credentials/project, quota, pricing, resource limits, network policy, image lifecycle and operation status/cancellation behavior.
3. Pin client/SDK versions. Run one Python command, fork the same checkpoint into two independent operations, inspect outputs, cancel a long operation and export a file.
4. Run a trusted prepared pytest task end to end and persist its evidence locally.
5. Record actual response schemas and operation IDs in `docs/PLATFORM_VALIDATION.md`.

Do not carry forward the unverified NVIDIA Catalog 16k limit, 40 RPM assumption, free-call allowance, or cross-provider failover. Token Factory is the chosen provider. Initial per-request context limits are engineering settings measured against this account, not statements about provider maximums.

## 5. Schedule

| Dates | Deliverable and gate |
|---|---|
| Oct 9–11 | Platform spike, pinned task recipe, SQLite schema, one end-to-end sequential repair and fresh verification |
| Oct 12–15 | Two or three strategies, constrained patch handling, guard fixtures, cancellation/restart recovery; small development task set |
| Oct 16–19 | Branch-and-refine; compare with sequential and independent candidates under matched budgets; freeze prompts and task eligibility rules |
| Oct 20–23 | Held-out evaluation on as many reproducible tasks as resources permit; paired results; frontend, artifacts and real replays |
| Oct 24–26 | Clean-machine setup test, live judging path, video, user feedback, README, costs and limitations |
| Oct 27 | Feature/code freeze; fixes only |
| Oct 28 | Submit and verify every link |
| Oct 29–30 | Buffer; no new architecture or features |
| Through Dec 15 | Maintain functioning judging access and reserved credits |

Official submission deadline: Oct 30, 2026, 10:00 AM PDT (10:30 PM IST). Judging: Dec 1–15. Recheck official rules before submission.

## 6. Evidence gates

- If the platform spike fails, fix access or simplify execution; do not build a simulated backend and present it as live.
- If branching adds no solve-rate benefit, compare latency and cost. Reduce branch count or ship adaptive sequential-first repair; report negative results honestly.
- Five development tasks are sufficient to debug the loop, not to establish statistical lift or justify switching to an unrelated project late in the schedule.
- If task environments cannot be reproduced, stop adding UI features and fix recipes.
- If the public service cannot run, provide a genuinely functioning test build and clear credentials/setup. Do not declare a replay player sufficient for eligibility without organizer confirmation.

## 7. Resource and cost controls

Zero out-of-pocket is a constraint, not a guarantee. Verify credit balances and expiry; inference, Sandboxes and app hosting all consume resources. Budget alarms are notifications, not spending caps.

Configure ceilings for aggregate model input/output tokens, estimated model spend, sandbox operations/seconds, wall time, active runs and artifact bytes. Count diagnosis, failed/retried requests, refinement and optional review. Enforce conservative local admission using known prices; when prices are unknown, enforce usage ceilings and inspect console billing.

Start with one active repair run and at most three concurrent sandbox candidates; these are app defaults, not provider limits. Stop admitting public work before the judge reserve is consumed. Judge credentials must permit the advertised workflow; avoid requiring judges to request access or purchase credits.

## 8. Repository shape

```text
repomedic/
  docs/PROJECT.md
  docs/PRD.md
  docs/ARCHITECTURE.md
  docs/EVALUATION.md
  docs/USER_FLOW_AND_DEMO.md
  backend/app/api/
  backend/app/auth/
  backend/app/store/
  backend/app/worker/
  backend/app/repair/
  backend/app/verification/
  backend/app/providers/token_factory.py
  backend/app/executors/contree.py
  backend/app/artifacts/
  backend/tests/
  backend/eval/
  frontend/
  demo/tasks.json
  demo/replays/
  LICENSE
  README.md
  .env.example
```

Task recipes and evaluation outcomes use the same schema. API/events in ARCHITECTURE.md are canonical. EVALUATION.md owns experiment definitions. USER_FLOW_AND_DEMO.md owns user onboarding and video.

## 9. Submission checklist

- [ ] Working live repair or functioning test build accessible through judging.
- [ ] Public repository, OSS license, authorized third-party code/assets and clean setup instructions.
- [ ] Public YouTube video under three minutes; English narration or translation.
- [ ] Token Factory inference and Sandboxes use demonstrated honestly.
- [ ] Results agree with immutable raw artifacts; no invented statistics.
- [ ] Every replay labeled, with timestamps, model ID, repo SHA and application version.
- [ ] Access instructions and judge credentials supplied upfront.
- [ ] Feedback on actual NVIDIA/Nebius integration recorded.
- [ ] Known limitations: curated repos, preserved-suite coverage, nondeterministic inference, credits and supported recipes.
- [ ] Eligibility and all submission requirements rechecked against official rules.

## 10. Sources and certainty

Checked 2026-10-09: [official rules](https://nebiusglobalaihackathon.devpost.com/rules), [judging guidance](https://nebiusglobalaihackathon.devpost.com/updates/46204-here-s-how-judging-works), [Token Factory cookbook](https://github.com/nebius/token-factory-cookbook), [ConTree SDK](https://github.com/nebius/contree-sdk), [ConTree CLI](https://github.com/nebius/contree-cli).

Public documentation supports the intended integration; account access, prices, exact limits and behavior remain runtime validation items. No credentials were accessed and no platform calls or repairs were executed while writing these specifications.
