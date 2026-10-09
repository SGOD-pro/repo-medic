# Start here

1. Foundation owner: read docs/DECISIONS.md, docs/FOLDER_STRUCTURE.md, docs/FOUNDATION.md and docs/phases.md. Create a new repository from this kit; never initialize separate repos for each package.
2. Complete F0–F6: generate/verify contracts, inspect migration, scaffold actual apps, validate Python/Node/package versions, install team skills, verify the fake thin connection and perform a tiny budgeted provider compatibility check. This kit's Python fake harness is not the frontend/API connection; build that connection during F4.
3. Commit a clean common foundation. Record BASE_SHA and exact install/test commands in docs/FOUNDATION_RECORD.md. Teammates start from that exact commit.
4. Distribute the entire repository. Each teammate gets one work-package entry point; global contracts travel with all packages. A starts docs/work-packages/WORK_PACKAGE_A_FRONTEND.md; B starts B_BACKEND; C starts C_ENGINE; D starts D_EVALUATION.
5. Each teammate uses one feature branch and implements tasks in order. Local package checks and contract checks run before handoff. Small integration checks can happen during development; final assembled acceptance follows package completion.
6. Integrate A+B+C offline; then one live sequential repair. Only then approve bounded live benchmarking. Preserve $8 of the approximate $25 balance provisionally for demo/judge access; revise from actual observed billing.

The screenshot's five previous specs are preserved under docs/reference-v0.4/ for context. New authoritative summaries and operational docs live under docs/. Do not hand out only a work-package file without its linked schemas/specs.

Unknowns deliberately requiring confirmation: actual Nebius model/endpoint/account access, sandbox lifecycle/billing, pinned real upgrade task, host, exact frontend/backend dependency lock. Do not fill these with invented values. No model named “Gemini Flash 8 high” is assumed or required: task size and checks are designed for the team's configured coding agent regardless of label.
