# 0009 · first safe product slice

**Status**: Assumed
**Date**: 2026-10-28
**Authorized by**: engineer, during /develop

## Owed decision
Safe boundary for custom repository configuration and presentation truthfulness without arbitrary code execution.

## Assumption built on
RepoMedic collects and validates repository specifications through shared contracts while enforcing a hard server side execution gate that prevents running, enqueuing, or billing untrusted repositories. Demo selection defaults to supported demo tasks and preserved saved runs.

## Code area
frontend/src/app/
frontend/src/components/
frontend/src/lib/
backend/src/
backend/tests/
frontend/tests/

## Requirements
1. Home page provides clear navigation to saved demo runs and custom repository configuration.
2. Custom repository inputs collect public GitHub HTTPS URL, full 40 character commit SHA, dependency, baseline and target versions, pytest argument list, allowed relative source paths, and expected failure substring.
3. Client and server validate custom inputs with explicit errors, while custom execution remains disabled both in UI and server side.
4. Presentation removes fabricated preflight, sandbox, AST, and cost claims, displaying actual values or Unavailable with clear offline mock labels.
5. Acceptance and example tasks are hidden from the normal task chooser using an explicit supported demo policy while preserving all existing data and runs.
6. Focused local tests and Playwright browser tests verify navigation, form validation, terminal presentation, missing data fallbacks, and server side gate enforcement.

## Ratify
This decision was recorded by /develop, not deliberated. Run `/architect first safe product slice`
to deliberate and ratify it. Until then it stays flagged as an owed decision; it does not block marking the feature done.
