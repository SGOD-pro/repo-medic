# Backend (Package B)

## Overview

Package B provides the Python backend service, database storage abstractions, and orchestration logic. It integrates with Cloudflare D1 through the database worker bridge and manages runs, events, artifacts, and budget accounting.

## Key files

| File | Owns |
|---|---|
| `src/contracts.py` | Shared domain models and type contracts |
| `src/config.py` | Environment configuration and service settings |
| `src/storage/db_client.py` | HTTP client for the database worker bridge |
| `src/storage/repository.py` | High level repository mapping D1 responses to domain contracts |
| `src/storage/fake_host.py` | In memory host adapter for tests |
| `src/engine/fake_engine.py` | Stub engine for testing task execution |
| `src/worker.py` | Queue worker claiming loop, repair execution, and host ports |
| `tests/test_storage.py` | Storage, budget, and event integration tests |

## Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Lint code
uv run flake8 src tests

# Static type check
uv run mypy src
```

## Conventions

* Python version 3.13 with strict type annotations
* Costs are tracked in micro USD where 1 USD equals 1,000,000 micro USD
* All database interactions use `D1StorageRepository` or `RepoMedicDB`
* Respect package boundaries, Package B owns backend and storage persistence

## Gotchas

* Runs in terminal states (`succeeded`, `failed`, `cancelled`) reject state updates with 409
* Artifact storage enforces 1 megabyte per artifact and 8 megabytes total per run

## Related specs

* [0001. Local D1 migrations and bridge](../docs/specs/0001-local-d1-migrations-and-bridge/index.md)
* [0002. Task, run, and history API](../docs/specs/0002-task-run-history-api/index.md)
* [0003. FakeEngine queue worker](../docs/specs/0003-fakeengine-queue-worker/index.md)
* [0005. Remote Cloudflare D1 integration](../docs/specs/0005-remote-cloudflare-d1-integration/index.md)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
