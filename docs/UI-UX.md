# RepoMedic — UI and user flow

Owner A. A compact developer tool, using the existing Next.js/React/Tailwind setup. No new design system dependency is necessary. Desktop-first, usable on a narrow screen. Layout: short top bar, task/workspace main area, visible run mode and final status.

## Visual direction

Use a calm dark developer workspace: background #0B1020, surfaces #131B2E, text #F1F5F9, secondary #A8B4CA, blue accent #60A5FA. Green indicates verified success, amber uncertain/in progress, red failure. Always pair color with text/icon. Use system sans for UI and monospace for code/logs. 8px spacing steps, readable 16px body text, clear keyboard focus. Subtle CSS transitions only; no magnetic buttons, heavy animation or unrelated landing page.

## Screens and interactions

| View | Contents and user action |
| --- | --- |
| Tasks | Curated title, repository link, commit, dependency before/after, expected failure; choose task and sequential/branch-refine if enabled |
| Run | Mode badge, cost estimate/cap, stage list, candidate cards, concise logs, cancel; disable duplicate start while submitting |
| Result | Outcome/reason, patch preview, verifier summary, evidence/log downloads and start another task |

One workspace can switch views; do not introduce extra routes as architecture requirements. Model/provider selection and budget overrides are operator settings, not user forms. No user accounts, login or access codes.

## How users use it

User selects a known dependency upgrade and clicks Start repair. The server chooses offline/replay/live mode, displayed before and during the run. User watches baseline→upgrade→repair→verification. When complete, they inspect the source diff and download patch/evidence. They apply the patch in their own checkout after review; this app does not merge it or claim broad production safety.

A can preview a small patch bundled with a fixture. Real patch/evidence downloads use the owned artifact route; if an inline preview is needed, fetch that same artifact, validate text size/type and render escaped text. Do not invent an undocumented preview endpoint. Logs truncate visibly with full-download access. Never render repository/model text as raw HTML.

## Truthful states

Succeeded requires verified evidence, not model confidence. Failed shows which stage failed and retains logs. Cancelled remains cancelled even if a remote response arrives late. Queued/running show progress without fake percentage or invented time remaining. Offline and replay are labeled prominently; replay also displays that it is saved evidence. No success banner while still running.

Handle no tasks, API unavailable, budget denied, SSE disconnect and artifact download failure. Reconnect deduplicates event sequences; summary polling recovers final state. An uncertain start request must not silently retry and create another paid run. Explain uncertainty and direct operator review.

## Acceptance and demonstration

Use shared success/failure/cancel fixtures; API-defined fields only. Check tab/Enter navigation, focus after errors, screen-reader status, contrast and mobile stacking. Skeletons respect reduced motion. Tests verify start/cancel/error/result behavior; manual screenshots verify layout.

Suggested video follows actual user flow: show green baseline and red upgrade, start the bounded repair, show fresh verification, inspect/download patch and evidence, finish with actual spend. Label speedups and replay footage. Final duration is governed by organizer rules; D's work package provides a suggested timeline, not an official submission limit.
