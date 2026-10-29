# RepoMedic — frontend UX specification

Status: proposed refactor brief · 29 October 2026  
Baseline: repository `SGOD-pro/repo-medic`, `main` at `2946510cc710e6a1071612773de90cc8663fa7f0`, plus the user-provided screenshots. The workspace also contains an uncommitted, partially verified frontend pass; inspect its diff before reuse. This document specifies desired behavior, not completed functionality. `DESIGN.md` defines visual tokens and component rules.

## Product and scope

RepoMedic helps a developer reproduce a dependency upgrade failure, generate a candidate patch and verify the original tests in an isolated environment, then review and download evidence. Today, controlled demo tasks and saved results are the supported experience. The custom repository form validates a configuration; custom execution remains disabled. The API currently accepts a task ID for a run. Do not imply arbitrary GitHub repair is available.

The UI should help a first-time user answer: What can I do? What information is required? What is happening? Did it work, and what evidence supports the result? Use plain developer language; avoid infrastructure labels and celebratory claims where they do not help an action.

## Information architecture

| Destination | Primary purpose | Primary action |
| --- | --- | --- |
| Home | Explain product and current scope | Configure a repository; secondary: view saved demo |
| Configure | Collect and validate repository recipe | Validate configuration; execution remains unavailable |
| Demo tasks | Select a supported task and mode | Start selected demo; saved results are separate |
| Run | Follow a specific run and recover from errors | Cancel while cancellable; view results when terminal |
| Results | Understand outcome, inspect patch and evidence | Download patch or evidence when available |
| History | Reopen a specific run | Open run, with status and mode visible |

A shared shell can preserve the existing tab implementation or use routes when justified. Saved `?runId=` links must still hydrate the right run. Current `docs/UI-UX.md` predates the green theme; this spec and `DESIGN.md` are the proposed replacement for a refactor, subject to existing API and engine contracts.

## Home

Create a concise introduction with a headline, one sentence explaining the workflow, and two clear actions: **Configure a repository** and **View a saved demo**. Follow with a compact sequence: baseline → upgrade failure → candidate patch → verification. Describe controlled examples honestly: demo-shop has one collected test; success is not general reliability. Explain that patches are reviewed and applied by the developer. Avoid fictional success metrics, animated dashboards, testimonials and provider pricing.

## Configure repository

- Lead with a compact notice: “Custom repository runs are not yet available. You can validate the configuration or view a demo.” Keep it visible without repeating the same explanation in multiple panels.
- Group fields in reading order: repository and revision; dependency and versions; test command, allowed paths and expected failure. Use a two-column desktop form where fields remain comfortably readable; stack on mobile. Place **Validate configuration** immediately after the form. Secondary: **Use demo values** and **View demo**. No detached action panel that disappears as the form scrolls.
- Required inputs in the current contract: public GitHub HTTPS URL, full 40-character commit SHA, Python package, exact current and target versions, pytest arguments, allowed relative source paths and expected failure text. Mark required fields, include one short example where useful, and associate inline errors with each control.
- Validation checks format and contract rules; it does not establish repository reachability, commit existence, baseline success or sandbox safety. Describe those limitations next to the result. A valid format does not enable execution.
- **Future, separately implemented:** branch lookup after a valid public repository URL. Show loading, empty, inaccessible/private, rate-limit and network-error states. Selecting a branch resolves it to a full immutable SHA; show both branch and resolved SHA and run against that exact SHA. A changed branch must be explicitly re-resolved. Until the API exists, do not show a functional-looking branch selector or invent values.
- Direct API calls must remain gated as well as the UI. Do not use this refactor to enable custom execution or send secrets.

## Demo tasks

Show a short explanation and supported curated tasks with repository, dependency versions and commit from task data. Make selection obvious with a labeled radio-like control and keyboard access. Provide the selected task's summary, strategy and execution mode close to the primary **Start demo repair** action. A desktop summary may be sticky beneath the header only if it fits the viewport; on small screens place the action in normal flow or a non-obscuring sticky bottom bar. Test the longest card and short viewports. Do not show invented test counts, preflight readiness, sandbox resources, limits or baseline duration when unavailable.

Saved results should be a distinct, clearly labeled action and must not trigger a paid run. Warn that a live demo uses provider resources, and distinguish offline/mock from live before submission. Disable repeated submission while in flight. On an uncertain response, show the ambiguity and allow recovery by checking existing runs; never silently launch another job.

## Run

Empty state: “No run selected,” with a route to demo tasks/history. When a run exists, show repository/task, run ID, mode and authoritative status. Design a compact grid with a stage timeline, candidate area and bounded event log; use cards only when they organize distinct information. Stage progress comes from events and/or server state, never fabricated percentage, elapsed completion time or guessed candidate outcomes.

- Queued/running: show current known stage, cancel when available, stream connection/reconnection only while relevant, and an explicit estimated usage label if returned.
- Succeeded/failed/cancelled: show the terminal outcome and reason; remove active/cancel affordances and offer results. Stream closure after terminal state is normal, not “disconnected.” Preserve terminal state against late events.
- Event stream interruption: keep last known status; show reconnecting or disconnected and an actionable recovery path. Poll/hydrate authoritative summary when supported. Avoid implying that a disconnected stream stopped the worker.
- No live candidates/events: show “Waiting for events” or “No candidate data available.” Never substitute mock logs or sandbox telemetry in HTTP/live mode. Simulation controls belong only to explicitly labeled mock/development mode.
- A cancel request has pending, confirmed, failed and too-late states. A request does not guarantee an in-flight provider call has stopped; show server-confirmed outcome.

## Results

Empty state explains how to select a run. For a selected run, prioritize outcome and reason, then a compact evidence grid: actual test totals, verified version, test integrity and duration only where evidence supports them. Provide a readable patch preview, changed file names, and separate patch, verification log and evidence download actions when artifact IDs exist. Missing or malformed evidence shows “Unavailable” and never implies success. Do not label hash checks “AST proof.” Escape untrusted model/repository text; bound preview sizes and provide download errors and retries. Show estimated usage separately from billed cost.

For failed and cancelled runs, show useful available logs and partial artifacts without a success badge. Handle a missing, deleted or inaccessible artifact as a recoverable error. Preserve direct saved-run URLs and evidence.

## History and visibility

Separate the normal chooser from evaluation records. Filter curated tasks using explicit provenance/visibility, not broad deletion. History should show actual run ID, task, state, mode, and timestamp only when provided; unknown timestamps are “Unavailable.” Distinguish saved demo and mock where known. Do not infer ownership from a browser session or claim private per-user history without authorization. Preserve failures, run records, events and artifacts; do not perform bulk cleanup as part of a visual refactor.

## Accessibility and responsive behavior

Use semantic headings, forms, buttons and navigation; maintain logical keyboard order and visible focus. Associate errors with controls; announce asynchronous state changes politely and move focus to error summary on failed submit. Support 200% zoom and reduced motion. Color never carries status alone. Verify contrast, 44px touch targets where practicable, long URLs and unbroken SHAs, keyboard access to dropdowns, no clipped menus, and horizontal containment for logs and diffs.

At 320–767px stack form fields and task summary, keep actions reachable without obscuring content and ensure navigation can be reached by keyboard. At 768–1023px use a flexible intermediate layout. At 1024px and above use a bounded content width and a sticky summary only when it fits. Breakpoints are design targets; test actual content rather than assuming a device size guarantees fit.

## Data, cost and security rules

Use server state and evidence as the source of truth. Show missing fields as unavailable. Estimated allocation/reservation is not provider billing or a guaranteed spend cap. Never show fake sandbox isolation details, proof, telemetry or test counts in live mode. Keep custom execution disabled until independently verified isolation, restricted egress, secret separation, resource and spend limits, idempotency, cancellation, concurrency and abuse controls exist. UI validation is not a security boundary. Do not expose internal secrets or log credentials.

## Refactor order and acceptance

1. Shared shell, tokens and navigation → desktop/mobile, keyboard and direct saved-link checks.
2. Home and configuration → valid, invalid and unavailable API; no custom start through UI or API; validation result clears when inputs change.
3. Demo selection and history → empty/loading/error, long task names, persistent start action; no records deleted and saved results still open.
4. Run → queued, running, stream interruption, cancel pending/confirmed, success/failure/cancel and reload. Only server-supported values shown.
5. Results → successful, failed, cancelled, absent/malformed evidence, long diff, download success/failure.

Use fixtures and mock transport explicitly labeled for local tests. Run unit/type/build checks, keyboard and Playwright browser tests at desktop and mobile; capture and inspect real rendered screens for every major state. Test the deployed application only through authorized read-only checks and approved controlled runs; report simulated vs real checks and actual spend separately. No deployment, paid repair or data deletion is implied by this document.
