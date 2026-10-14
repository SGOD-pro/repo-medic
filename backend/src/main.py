import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel, ConfigDict

from src.config import settings
from src.contracts import (
    APIErrorEnvelope,
    ErrorDetail,
    RunState,
    RunSummary,
    SearchMode,
    TaskSummary,
)
from src.fixtures import find_task_fixture_dir
from src.storage.repository import D1StorageRepository
from src.worker import QueueWorker

logger = logging.getLogger("repomedic.api")


class CreateRunRequest(BaseModel):
    task_id: str
    search_mode: SearchMode

    model_config = ConfigDict(extra="forbid")


class TasksResponse(BaseModel):
    tasks: list[TaskSummary]


class RunsResponse(BaseModel):
    runs: list[RunSummary]


def sync_task_fixtures(repo: D1StorageRepository) -> None:
    fixture_dir = find_task_fixture_dir()
    if not fixture_dir:
        logger.info("No fixtures/tasks directory found for task synchronization")
        return
    for json_file in fixture_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            if "task_id" in data:
                repo.upsert_task(data)
                logger.info("Synchronized task %s from %s", data["task_id"], json_file.name)
        except Exception as e:
            logger.warning("Failed to synchronize task fixture %s: %s", json_file.name, e)


def get_repository(request: Request) -> D1StorageRepository:
    repo = getattr(request.app.state, "repository", None)
    if repo is not None:
        return repo
    return D1StorageRepository()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    repo = getattr(app.state, "repository", None)
    if repo is None:
        app.state.repository = D1StorageRepository()
        repo = app.state.repository
    try:
        sync_task_fixtures(repo)
    except Exception as e:
        logger.warning("Error during startup task sync: %s", e)

    worker = getattr(app.state, "worker", None)
    if worker is None and getattr(settings, "repomedic_worker_enabled", True):
        poll_interval = getattr(settings, "repomedic_worker_poll_interval_seconds", 1.0)
        worker = QueueWorker(repo=repo, poll_interval_seconds=poll_interval)
        app.state.worker = worker
    if worker is not None and getattr(settings, "repomedic_worker_enabled", True):
        await worker.start()

    try:
        yield
    finally:
        if worker is not None:
            await worker.stop()


def create_app(
    repository: D1StorageRepository | None = None,
    worker: QueueWorker | None = None,
) -> FastAPI:
    app = FastAPI(title="RepoMedic API", lifespan=lifespan)
    if repository is not None:
        app.state.repository = repository
    if worker is not None:
        app.state.worker = worker

    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    app_origin = getattr(settings, "repomedic_app_origin", None)
    if app_origin and app_origin not in origins:
        origins.append(app_origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = exc.errors()
        msg_parts = []
        for err in errors:
            loc = " -> ".join(str(loc_item) for loc_item in err.get("loc", []))
            msg_parts.append(f"{loc}: {err.get('msg', 'invalid value')}")
        message = "; ".join(msg_parts) if msg_parts else "Invalid request body"
        envelope = APIErrorEnvelope(error=ErrorDetail(code="invalid_request", message=message))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=envelope.model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        if exc.status_code == 404:
            code = "not_found"
        elif exc.status_code in (400, 422):
            code = "invalid_request"
        else:
            code = "error"
        envelope = APIErrorEnvelope(error=ErrorDetail(code=code, message=str(exc.detail)))
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope.model_dump(),
        )

    @app.exception_handler(httpx.RequestError)
    async def httpx_request_error_handler(
        request: Request,
        exc: httpx.RequestError,
    ) -> JSONResponse:
        envelope = APIErrorEnvelope(
            error=ErrorDetail(code="unavailable", message="Database bridge unavailable")
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=envelope.model_dump(),
        )

    @app.exception_handler(httpx.HTTPStatusError)
    async def httpx_status_error_handler(
        request: Request,
        exc: httpx.HTTPStatusError,
    ) -> JSONResponse:
        if exc.response.status_code == 404:
            envelope = APIErrorEnvelope(
                error=ErrorDetail(code="not_found", message="Resource not found")
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=envelope.model_dump(),
            )
        if exc.response.status_code in (502, 503, 504):
            envelope = APIErrorEnvelope(
                error=ErrorDetail(code="unavailable", message="Database bridge unavailable")
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=envelope.model_dump(),
            )
        envelope = APIErrorEnvelope(
            error=ErrorDetail(code="internal_error", message="Upstream database error")
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=envelope.model_dump(),
        )

    @app.get("/api/tasks", response_model=TasksResponse)
    def list_tasks(
        repo: D1StorageRepository = Depends(get_repository),
    ) -> TasksResponse:
        tasks = repo.list_tasks()
        return TasksResponse(tasks=tasks)

    @app.post("/api/runs", status_code=status.HTTP_202_ACCEPTED, response_model=RunSummary)
    def create_run(
        payload: CreateRunRequest,
        repo: D1StorageRepository = Depends(get_repository),
    ) -> RunSummary:
        task = repo.get_task(payload.task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task '{payload.task_id}' not found",
            )

        run_id = f"run_{uuid.uuid4().hex}"
        mode = getattr(settings, "repomedic_mode", "offline")
        max_run_usd = getattr(settings, "repomedic_max_run_usd", 2.0)

        run = repo.create_run(
            run_id=run_id,
            task_id=payload.task_id,
            mode=mode,
            search_mode=payload.search_mode,
            max_run_usd=max_run_usd,
        )
        return run

    @app.get("/api/runs/{id}", response_model=RunSummary)
    def get_run(
        id: str,
        repo: D1StorageRepository = Depends(get_repository),
    ) -> RunSummary:
        return repo.get_run(id)

    @app.get("/api/runs", response_model=RunsResponse)
    def list_runs(
        limit: int = Query(default=50, ge=1, le=100),
        task_id: str | None = Query(default=None),
        state: RunState | None = Query(default=None),
        repo: D1StorageRepository = Depends(get_repository),
    ) -> RunsResponse:
        runs = repo.list_runs(limit=limit, task_id=task_id, state=state)
        return RunsResponse(runs=runs)

    return app


app = create_app()
