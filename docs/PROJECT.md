# RepoMedic — the project story

## Why RepoMedic exists

Updating a Python dependency can turn a previously passing project into a failing one. The maintainer must identify what changed, understand the failures, alter source code and check that the upgrade really works. A suggested patch is only the start: the maintainer also needs to know which environment ran, whether the original tests remained intact and whether the repaired project actually passed.

RepoMedic exists to make that repair process visible and reproducible. It combines model-generated source changes with execution in isolated environments and produces a proposed patch accompanied by verification evidence. Its goal is to help a developer move from “this upgrade broke my project” to “here is a reviewable repair and the exact checks that passed.”

## What the project solves

The project addresses a specific problem: repairing Python source after a known dependency upgrade causes a preserved pytest suite to fail. The full application takes a user through task selection, execution, candidate repair, verification, result inspection and artifact download. It is not just a UI prototype or a replay viewer.

RepoMedic begins with curated public repository tasks pinned to commits and explicit dependency versions. That makes the task reproducible and allows the application to demonstrate a real before-and-after result. Curated inputs are the supported product boundary for this version, not a claim that arbitrary repositories already work. Supporting every repository, language and build system is a different scope.

## Who uses it

A Python maintainer investigating an upgrade can use RepoMedic to inspect a verified source repair. A developer evaluating coding agents can use its recorded attempts, logs and budgets to compare strategies. A hackathon judge can follow the actual repair process instead of relying on an agent's claim that it fixed something.

The initial application is a shared developer workspace without user accounts, teams, subscriptions or OAuth. Real paid execution is operated in a controlled deployment; public demonstration can use clearly labeled replay mode. The application does not claim private per-user data isolation.

## How a user uses the application

The user opens RepoMedic and sees the available upgrade tasks. Each task identifies its repository, pinned commit, dependency, original version, target version and the expected failure. The user chooses a task and a repair strategy, then starts the run. The interface displays whether the run is live, offline or a saved replay.

For a real run, RepoMedic first checks that the original project passes its preserved tests. It then installs the target dependency version and confirms the expected failure. If either assumption is false, it reports the problem instead of inventing a repair success.

The agent reads a bounded failure context and proposes an allowlisted source patch. RepoMedic executes the candidate against the preserved full suite in a fresh upgraded environment. Branch/refine mode can explore a small number of alternatives and refine failed candidates within fixed limits. The user sees stages, candidate outcomes, cancellation controls and estimated usage throughout this process.

When a candidate passes the verifier, the result screen displays the patch, test results and tested dependency/environment details. The user downloads the patch and evidence package, reviews the source changes and applies them to their own checkout. RepoMedic does not automatically merge a pull request or modify the user's repository.

If no candidate passes, the application shows the failed stage, reason and collected evidence. Cancellation remains cancellation even if a remote operation finishes later. A failed run is useful diagnostic information; it is never relabeled as successful for the demonstration.

## What happens behind the scenes

The browser talks to the application backend, which records runs and events in Cloudflare D1. A repair engine calls a NVIDIA Nemotron model through Nebius Token Factory and uses Nebius/ConTree sandboxes to execute code from controlled checkpoints. Model output is treated as an untrusted proposal; the verifier decides whether the preserved checks actually pass.

The application records the pinned task, model, candidate attempts, patch, logs, versions, hashes and usage estimates. These records explain what was tested and make outcomes reviewable. The complete flow is connected through real application routes and persistence; mocks are development tools for building and testing cheaply before paid integration.

## What makes a result trustworthy

A successful result requires a green original baseline, the expected red upgrade, source-only changes and a fresh verification of the upgraded project. RepoMedic must reject altered tests, removed checks, wrong dependency versions, empty test collection and new skip/xfail behavior. Passing one preserved test suite still does not prove every possible production regression is absent; maintainers retain responsibility for reviewing the patch and broader validation.

Offline fixtures and saved replay are always labeled. Neither counts as a newly solved live task. Cost limits constrain experiments, and unknown provider outcomes are preserved rather than blindly resubmitted.

## Goal and completion

The goal is a complete end-to-end application within the supported Python upgrade workflow: usable screens, real backend, Cloudflare D1 persistence, live model/sandbox execution, sequential and bounded branch/refine strategies, cancellation, reload/history, patch/evidence downloads and honest evaluation. No Redis, enterprise authentication, billing or distributed worker framework is required to complete that flow.

The project is complete when a user can perform this workflow through the app, persisted results survive application restart, offline regressions pass, at least one real repair is verified and recorded, and real failures are presented truthfully. Its value comes from demonstrable verified repairs and useful evidence, not from an unsupported claim of universal autonomy or a guaranteed hackathon win.
