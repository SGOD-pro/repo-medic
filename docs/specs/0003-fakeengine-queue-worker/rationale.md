# 0003. FakeEngine queue and worker (Rationale)

**Date**: 2026-10-11
**Status**: Proposed

## Context

Package B currently provides HTTP endpoints for registering tasks and enqueueing repair runs into Cloudflare D1 storage. When a user triggers `POST /api/runs`, a run is created in `queued` state. However, there is no active worker process to claim queued runs, pass them to `FakeEngine.repair`, and transition them to a terminal state (`succeeded`, `failed`, or `cancelled`).

Without a queue worker, repair runs remain stuck in `queued` state indefinitely. Package C has delivered `FakeEngine` which expects a `RepairRequest`, a `TaskRecipe`, and a `HostPorts` interface to emit events and track budget reservations. Package B must now provide the orchestration layer that bridges stored queued runs with engine execution, driving runs to completion and updating storage accordingly.

Key forces at play:
1. Operational simplicity: the project is operating in local development mode without external message queues or brokers such as Celery, RabbitMQ, or Redis.
2. Crash resilience: unhandled engine errors must not take down the worker loop or leave runs in zombie running states forever.
3. Separation of concerns: the worker should handle orchestration and lifecycle, while FakeEngine focuses on the repair logic.

## Options considered

### Option 1: In process background worker task with D1 polling

The worker runs as an asynchronous task inside the FastAPI server lifespan. It polls D1 periodically (every 1 second) for runs with `state = queued`. Upon finding work, it transitions the run to `running`, invokes `FakeEngine.repair`, and marks it `succeeded` or `failed` when finished.

**Pros**:
* Zero new infrastructure or process management overhead during local development.
* Starts and stops automatically with the web server lifecycle.
* Directly uses the existing `D1StorageRepository` and configuration settings.

**Cons**:
* Shares memory and event loop with the FastAPI web server.
* Adds periodic lightweight read queries against local D1 when idle.

### Option 2: Standalone CLI daemon process

Run the worker as a separate standalone Python process (for example `python -m src.worker`) executed independently from the web server.

**Pros**:
* Complete process and memory isolation between web request handling and task execution.
* Can be scaled or restarted independently of the web application.

**Cons**:
* Developers must manage two separate running processes during local development.
* Requires coordinating startup and shutdown scripts across packages.

### Option 3: Synchronous execution on run creation

Execute `FakeEngine.repair` inline inside the `POST /api/runs` endpoint handler, waiting for engine completion before returning the HTTP response.

**Pros**:
* Eliminates the need for any polling loop or background task orchestration.

**Cons**:
* Violates asynchronous run requirements and acceptance criteria where `POST /api/runs` returns HTTP 202 Accepted immediately.
* Client requests will hang and time out for long running repair workflows.

## Rationale

Option 1 is selected because it directly satisfies the asynchronous execution contract of `POST /api/runs` while keeping the local development environment straightforward. Developers can run `uvicorn` and have both the API and worker active with no extra terminal windows or process supervisors.

By using D1 polling for `state = queued`, pending runs survive server restarts and can be resumed cleanly. Running 1 task at a time prevents CPU contention while matching the single worker scope of Feature 3. A standalone entrypoint will also be preserved so the worker can be run independently in future production container deployments.
