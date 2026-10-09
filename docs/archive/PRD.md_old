# RepoMedic — product base

## What we build

RepoMedic helps maintainers repair Python code when a pinned dependency upgrade breaks an existing pytest suite. A user chooses a curated public example, starts a repair, sees diagnosis and candidate verification, then downloads the proposed source patch and evidence. The maintainer reviews and applies the patch; passing this suite does not prove every possible regression is fixed.

The hackathon pitch is a coding agent that produces a verified repair with a visible cost limit. The distinguishing demo is reproducible evidence: original code passes, the upgraded environment fails, and the repaired code passes the preserved suite in a fresh upgraded environment.

## MVP user flow

1. Enter a shared demo access code.
2. Choose a curated upgrade task and view its repository, commit, dependency versions and expected failure.
3. Start a repair; see run mode, stages, candidates and budget usage.
4. Inspect the winning patch, verification logs and exact tested versions.
5. Download patch and evidence, or see an honest failure/cancellation reason.

Modes: **offline** exercises deterministic fakes; **replay** displays saved evidence; **live** uses actual providers. Always show the mode. Replay is never described as a fresh live solve.

## Scope and order

Must ship: one curated task end to end; session ownership; persistent runs/events; sequential repair; fresh-environment verifier; cancellation; bounded paid calls; artifact download; clearly labeled mock/replay; one real recorded run.

Next, only after this works: up to three candidate branches, with at most one refinement for each. Show measured benefit only if evaluation supports it.

Defer: arbitrary repositories, GitHub account connection, automatic PRs/merges, private repositories, billing, personal memory, multi-language repair, model routing and distributed workers. This is primarily the Coding and Agentic Engineering track; do not claim Personal AI track eligibility without the organizers' requirements being met.

## Modules, libraries and platforms

| Module | Technology/service | How and why |
| --- | --- | --- |
| User workspace | Existing Next.js/React/TypeScript/Tailwind | Screens and typed HTTP client; retain repository versions until clean installation/build passes |
| API/session | FastAPI, Pydantic, Uvicorn | Validate frozen API, access-code sessions and run lifecycle |
| Persistence | Python sqlite3, private filesystem | Small single-host durable queue/events/artifacts; no ORM or cloud DB needed |
| Engine | Plain Python async orchestration | Explicit repair stages, bounded branching and hard verification; no LangGraph dependency |
| Model adapter | OpenAI-compatible async Python client (`openai`) | Calls NVIDIA model on Nebius; explicitly disable SDK automatic retries for paid submission |
| Execution adapter | ConTree Python SDK/client (`contree_sdk`, `contree_client`) | Separate runtime executes code from image checkpoints; package names/versions installed from current official instructions and locked after spike |
| Backend checks | pytest, httpx | Offline engine/route/contract regressions; httpx also underlies async transport |
| Frontend checks | Existing ESLint/TypeScript + Vitest/Testing Library | Focused UI/contract checks; foundation adds only necessary testing dependencies |
| Development workflow | Antigravity, JS Mastery; optional targeted Superpowers | Human-owned packages with agents implementing small verified slices |

No OAuth, S3, Redis, Celery, PostgreSQL, payment system or GitHub write integration in MVP. Retain Python 3.13 baseline until clean compatibility checks; foundation records the final version before parallel work.

## External APIs and model choice

Start with one proposed repair model: `nvidia/nemotron-3-super-120b-a12b`, documented in Nebius's official [Super cookbook](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-super-120B.md). It performs failure diagnosis and patch generation. This is a proposed tradeoff for a small-budget reasoning task, not a measured winner. No separate summarizer model and no automatic Ultra escalation. Account availability, cost and one tiny real call must confirm the selection.

The cookbook uses `https://api.tokenfactory.us-central1.nebius.com/v1/` with the OpenAI-compatible chat-completions client. It is a documented starting point; verify it with your project credentials. The Token Factory console is not the API base.

Execution uses [Nebius Sandboxes](https://docs.tokenfactory.nebius.com/sandboxes/overview), currently documented as beta. The [ConTree command reference](https://docs.tokenfactory.nebius.com/sandboxes/cli/commands) documents `https://api.tokenfactory.nebius.com/sandboxes/` and bearer authentication plus project context. SDK configuration and credential lifetime must be tested independently of inference; do not assume the inference API key is interchangeable with a sandbox IAM token. Use official SDK/client operations for images, execution, results and files; do not guess REST payloads.

Curated public Git repositories supply pinned source; only C's configured recipes are fetched. No arbitrary browser-supplied repository/shell execution. One host serves backend with persistent disk and frontend through a same-origin proxy; exact hosting provider is deferred to foundation.

## Foundation verification checklist

- [ ] Final Python/Node/dependency versions install and offline tests/build pass.
- [ ] Curated repository/commit, upgrade and expected failure reproduced.
- [ ] Model ID/region/account access and actual prices verified.
- [ ] Sandbox beta access, IAM/project credentials and SDK installation verified.
- [ ] Image checkpoint, fresh execution, upload/download, cancellation/cleanup and network limits tested.
- [ ] Per-operation cost bounds and sandbox billing accounted for.
- [ ] Deployment host/persistent disk, origin, cookie and proxy configured.

Record actual resolved values here. These are not completed checks. Offline work starts without provider keys; live mode remains disabled until prerequisites pass.

## Success criteria

All offline acceptance checks pass. A real run demonstrates the upgrade failure, safe source repair and fresh verification. Evidence contains actual logs, patch, tested versions and provider usage. Total provider/sandbox spend stays within the team's approximately $25 allocation, with money reserved for recording and judging.

No invented benchmark scores, winning probability, pricing or model capabilities. Check current organizer submission/video rules before recording. See [architecture](ARCHITECTURE.md) for boundaries and [phases](phases.md) for delivery.
