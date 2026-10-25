# 0007 · remote turso persistence

**Status**: Assumed
**Date**: 2026-10-25
**Authorized by**: user, during /develop

## Owed decision
Storage backend architecture for submission deployment and remote persistence.

## Assumption built on
RepoMedic persistence migrates from Cloudflare D1 Worker bridge to Turso libSQL storage. A Turso client adapter behind existing repository interfaces connects directly to remote Turso libSQL databases using the official libsql Python driver with parameterization, atomic budget reservation, and CAS state transitions, while supporting local file databases for offline development.

## Code area
backend/src/storage/, backend/src/config.py, backend/src/main.py, backend/src/worker.py, frontend/tests/browser_acceptance.mjs, docs/TURSO_SETUP.md

## Requirements
1. Implement Turso storage adapter behind existing repository interfaces.
2. Official libsql Python driver for Python 3.13 and remote libSQL database.
3. Preserve runs, ordered events, artifacts, cancellation, startup recovery, and atomic budget reservations.
4. Repeatable schema initialization and migrations with parameterized queries.
5. Environment variable credentials without secret exposure.
6. Acceptance suite operates without Cloudflare D1 Worker dependency.
7. Retain historical D1 evidence and complete remote K3 acceptance against live Turso database.

## Verification
1. Remote Turso acceptance suite test_k3_remote_turso.py verified all 7 tests passing against live database.
2. Full stack browser acceptance suite verified all 9 integration checks passing with persistent Turso backend.
3. Unit and storage regression suite test_turso_storage.py and test_storage.py verified all 22 tests passing in 0.30 seconds.

## Ratify
This decision was recorded by /develop, not deliberated. Run `/architect remote turso persistence`
to deliberate and ratify it. Until then it stays flagged as an owed decision; it does not block marking the feature `done`.
