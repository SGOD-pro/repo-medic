import asyncio
import datetime
import faulthandler
import hashlib
import json
import logging
import os
import signal
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
import httpx
from pydantic import BaseModel, ConfigDict

from src.config import settings
from src.contracts import (
    APIErrorEnvelope,
    BranchInfo,
    CustomConfigValidationResponse,
    CustomRepositoryConfig,
    CustomRunRequest,
    ErrorDetail,
    Mode,
    ResolveBranchesRequest,
    ResolveBranchesResponse,
    RunState,
    RunSummary,
    SearchMode,
    SUPPORTED_DEMO_TASK_IDS,
    TaskSummary,
)
from src.custom_validation import (
    resolve_repository_branches,
    validate_custom_config,
    verify_branch_pinned_sha,
)
from src.fixtures import find_task_fixture_dir
from src.storage.exceptions import StorageError
from src.storage.repository import D1StorageRepository
from src.worker import QueueWorker

faulthandler.register(signal.SIGUSR1, all_threads=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("repomedic.api")


class CreateRunRequest(BaseModel):
    task_id: str
    search_mode: SearchMode
    mode: Mode | None = None
    idempotency_key: str | None = None

    model_config = ConfigDict(extra="forbid")


class TasksResponse(BaseModel):
    tasks: list[TaskSummary]


class RunsResponse(BaseModel):
    runs: list[RunSummary]


def sync_task_fixtures(
    repo: D1StorageRepository,
    sync_enabled: bool | None = None,
    acceptance_prefix: str | None = None,
) -> None:
    if sync_enabled is None:
        sync_enabled = getattr(settings, "repomedic_sync_fixtures", True)
    if not sync_enabled:
        logger.info("Task fixture sync skipped because repomedic_sync_fixtures is disabled")
        return

    if acceptance_prefix is None:
        acceptance_prefix = getattr(settings, "repomedic_acceptance_prefix", "")

    fixture_dir = find_task_fixture_dir()
    if not fixture_dir:
        logger.info("No fixtures/tasks directory found for task synchronization")
        return
    for json_file in fixture_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            if "task_id" in data:
                if acceptance_prefix and not data["task_id"].startswith(acceptance_prefix):
                    logger.debug(
                        "Skipping task fixture %s not matching acceptance prefix %s",
                        data["task_id"],
                        acceptance_prefix,
                    )
                    continue
                repo.upsert_task(data)
                logger.info("Synchronized task %s from %s", data["task_id"], json_file.name)
        except Exception as e:
            logger.warning("Failed to synchronize task fixture %s: %s", json_file.name, e)


def recover_interrupted_runs(
    repo: D1StorageRepository,
    acceptance_prefix: str | None = None,
    stale_queued_seconds: float | None = None,
) -> None:
    """Transition runs left in 'running' state, or stale 'queued' runs whose dispatch crashed, to 'failed'."""
    if acceptance_prefix is None:
        acceptance_prefix = getattr(settings, "repomedic_acceptance_prefix", "")
    if stale_queued_seconds is None:
        stale_queued_seconds = getattr(settings, "repomedic_stale_queued_timeout_seconds", 300.0)
    try:
        while True:
            interrupted = repo.list_runs(
                limit=100,
                state="running",
                run_prefix=acceptance_prefix or None,
            )
            if not interrupted:
                break
            marked_any = False
            for r in interrupted:
                if acceptance_prefix and not r.run_id.startswith(acceptance_prefix):
                    logger.debug(
                        "Skipping interrupted run %s not matching acceptance prefix %s",
                        r.run_id,
                        acceptance_prefix,
                    )
                    continue
                try:
                    repo.finish_run(
                        r.run_id,
                        state="failed",
                        reason="Backend process restarted while run was in progress",
                    )
                    marked_any = True
                    logger.info("Marked interrupted run %s as failed", r.run_id)
                except Exception as e:
                    logger.warning("Failed to mark interrupted run %s: %s", r.run_id, e)
            if not marked_any:
                break
    except Exception as e:
        logger.warning("Could not query interrupted runs during startup recovery: %s", e)

    # Recover stale queued runs whose dispatch process died
    try:
        queued_runs = repo.list_runs(
            limit=100,
            state="queued",
            run_prefix=acceptance_prefix or None,
        )
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        for r in queued_runs:
            if acceptance_prefix and not r.run_id.startswith(acceptance_prefix):
                continue
            if r.created_at:
                try:
                    created_dt = datetime.datetime.fromisoformat(r.created_at.replace("Z", "+00:00"))
                    age = (now_dt - created_dt).total_seconds()
                    if age > stale_queued_seconds:
                        repo.finish_run(
                            r.run_id,
                            state="failed",
                            reason="Run timed out in queue without dispatch or worker claim",
                        )
                        logger.warning("Marked stale queued run %s (age %.1fs) as failed", r.run_id, age)
                except Exception as parse_err:
                    logger.debug("Could not parse created_at for run %s: %s", r.run_id, parse_err)
    except Exception as e:
        logger.warning("Could not query stale queued runs during recovery: %s", e)


def get_repository(request: Request) -> D1StorageRepository:
    repo = getattr(request.app.state, "repository", None)
    if repo is not None:
        return repo
    return D1StorageRepository()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from concurrent.futures import ThreadPoolExecutor
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=64))

    repo = getattr(app.state, "repository", None)
    if repo is None:
        app.state.repository = D1StorageRepository()
        repo = app.state.repository

    sync_enabled = getattr(settings, "repomedic_sync_fixtures", True)
    acceptance_prefix = getattr(settings, "repomedic_acceptance_prefix", "")

    try:
        sync_task_fixtures(repo, sync_enabled=sync_enabled, acceptance_prefix=acceptance_prefix)
    except Exception as e:
        logger.warning("Error during startup task sync: %s", e)

    recovery_enabled = getattr(settings, "repomedic_startup_recovery_enabled", True)
    if recovery_enabled:
        try:
            recover_interrupted_runs(repo, acceptance_prefix=acceptance_prefix)
        except Exception as e:
            logger.warning("Error during startup run recovery: %s", e)
    else:
        logger.info("Startup run recovery skipped because repomedic_startup_recovery_enabled is false")

    worker = getattr(app.state, "worker", None)
    if worker is None and getattr(settings, "repomedic_worker_enabled", True):
        poll_interval = getattr(settings, "repomedic_worker_poll_interval_seconds", 1.0)
        use_real = getattr(settings, "repomedic_use_real_engine", False)
        worker = QueueWorker(
            repo=repo,
            poll_interval_seconds=poll_interval,
            acceptance_prefix=acceptance_prefix,
            use_real_engine=use_real,
        )
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
    if app_origin:
        for orig in app_origin.split(","):
            cleaned = orig.strip()
            if cleaned and cleaned not in origins:
                origins.append(cleaned)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
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
        elif exc.status_code == 403:
            code = "forbidden"
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

    @app.exception_handler(StorageError)
    async def storage_error_handler(
        request: Request,
        exc: StorageError,
    ) -> JSONResponse:
        envelope = APIErrorEnvelope(
            error=ErrorDetail(code=exc.code, message=exc.message)
        )
        return JSONResponse(
            status_code=exc.status_code,
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

    @app.get("/health")
    @app.get("/api/health")
    def health_check(
        repo: D1StorageRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        storage_status = repo.health()
        return {
            "status": "healthy",
            "storage": storage_status,
        }

    @app.get("/api/tasks", response_model=TasksResponse)
    def list_tasks(
        include_acceptance: bool = Query(default=True),
        policy: str | None = Query(default=None),
        repo: D1StorageRepository = Depends(get_repository),
    ) -> TasksResponse:
        tasks = repo.list_tasks()
        if policy == "supported_demo" or (not include_acceptance and policy != "all"):
            tasks = [
                t for t in tasks
                if t.task_id in SUPPORTED_DEMO_TASK_IDS
                and "example" not in (t.repository_url or "").lower()
            ]
        return TasksResponse(tasks=tasks)

    def extract_client_ip(req: Request) -> str:
        cf_ip = req.headers.get("cf-connecting-ip")
        if cf_ip and cf_ip.strip():
            return cf_ip.strip().split(",")[0].strip()
        xff = req.headers.get("x-forwarded-for")
        if xff and xff.strip():
            return xff.split(",")[0].strip()
        if req.client and req.client.host:
            return req.client.host.strip()
        return "127.0.0.1"

    @app.post("/api/custom/resolve-branches", response_model=ResolveBranchesResponse)
    def resolve_custom_branches(
        request: Request,
        payload: ResolveBranchesRequest,
        repo: D1StorageRepository = Depends(get_repository),
    ) -> ResolveBranchesResponse:
        client_ip = extract_client_ip(request)
        ip_limit = getattr(settings, "repomedic_custom_ip_rate_limit_per_min", 10)
        allowed, _, retry_after = repo.check_and_increment_rate_limit(
            f"ip:resolve:{client_ip}",
            limit=ip_limit,
            window_seconds=60,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many branch resolution requests. Please retry in {retry_after} seconds.",
            )

        try:
            return resolve_repository_branches(payload.repository_url)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    @app.post("/api/custom/validate", response_model=CustomConfigValidationResponse)
    def validate_custom_repository(
        payload: CustomRepositoryConfig,
    ) -> CustomConfigValidationResponse:
        return validate_custom_config(payload)

    @app.post("/api/custom/execute")
    @app.post("/api/custom/run")
    def handle_custom_execution(
        request: Request,
        payload: CustomRunRequest | None = None,
        repo: D1StorageRepository = Depends(get_repository),
    ) -> Response:
        enabled = getattr(settings, "repomedic_custom_execution_enabled", False)
        if not enabled:
            envelope = APIErrorEnvelope(
                error=ErrorDetail(
                    code="custom_execution_disabled",
                    message=(
                        "Custom repository execution is disabled in this safe product slice. "
                        "ConTree does not provide container level network egress isolation or cgroup memory limits. "
                        "Package installation and pytest execution execute untrusted code with open outbound network access. "
                        "Arbitrary remote execution and worker enqueueing are strictly gated off."
                    ),
                )
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content=envelope.model_dump(),
            )

        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body with custom configuration is required",
            )

        client_ip = extract_client_ip(request)

        # 1. IP rate limit check
        allowed_ip, _, retry_after_ip = repo.check_and_increment_rate_limit(
            f"ip:custom_run:{client_ip}",
            limit=5,
            window_seconds=3600,
        )
        if not allowed_ip:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Custom run submission limit reached for your IP address. Please retry in {retry_after_ip} seconds.",
            )

        # 2. Repo rate limit check
        repo_url_key = payload.config.repository_url.strip().lower().rstrip("/")
        repo_limit = getattr(settings, "repomedic_custom_repo_rate_limit_per_10min", 3)
        allowed_repo, _, retry_after_repo = repo.check_and_increment_rate_limit(
            f"repo:{repo_url_key}",
            limit=repo_limit,
            window_seconds=600,
        )
        if not allowed_repo:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many repair runs requested for this repository. Please retry in {retry_after_repo} seconds.",
            )

        # 3. Global concurrent limit check
        max_concurrent = getattr(settings, "repomedic_max_custom_runs_concurrent", 2)
        if repo.count_active_runs() >= max_concurrent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Server capacity reached for concurrent repair executions. Please try again shortly.",
            )

        # 4. Strict config validation
        val_res = validate_custom_config(payload.config)
        if not val_res.valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(val_res.errors),
            )

        # 5. Branch to SHA pinning verification
        sha_valid = verify_branch_pinned_sha(
            payload.config.repository_url,
            payload.branch,
            payload.config.commit_sha,
        )
        if not sha_valid:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Branch '{payload.branch}' does not point to commit SHA '{payload.config.commit_sha}'. "
                    f"The remote branch may have moved or the commit hash is invalid."
                ),
            )

        # 6. Budget checks
        mode = getattr(settings, "repomedic_mode", "offline")
        max_run_usd = 0.50
        total_budget = getattr(settings, "repomedic_total_budget_usd", 25.0)
        committed_usage = repo.get_total_committed_usd()
        if (committed_usage + max_run_usd) > total_budget:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Budget unavailable",
            )

        # 7. Generate full strength deterministic task ID and upsert task recipe
        task_seed = (
            f"{payload.config.repository_url.strip().lower()}:"
            f"{payload.config.commit_sha.strip().lower()}:"
            f"{payload.config.dependency.strip().lower()}:"
            f"{payload.config.from_version.strip()}:"
            f"{payload.config.to_version.strip()}"
        )
        task_hash = hashlib.sha256(task_seed.encode("utf-8")).hexdigest()[:32]
        task_id = f"TASK-CUSTOM-{task_hash}"

        test_cmd = [arg.strip() for arg in payload.config.pytest_args if arg and arg.strip()]
        if not test_cmd or test_cmd[0] != "pytest":
            test_cmd = ["pytest"] + [arg for arg in test_cmd if arg != "pytest"]

        task_data = {
            "task_id": task_id,
            "title": f"Custom repair: {payload.config.dependency} {payload.config.from_version} to {payload.config.to_version}",
            "repository_url": payload.config.repository_url,
            "commit_sha": payload.config.commit_sha,
            "dependency": payload.config.dependency,
            "from_version": payload.config.from_version,
            "to_version": payload.config.to_version,
            "recipe_json": {
                "test_command": test_cmd,
                "allowed_source_paths": payload.config.allowed_source_paths,
                "expected_failure": payload.config.expected_failure,
                "timeout_seconds": 300,
                "max_candidates": 3,
                "max_refinements": 1,
            },
        }
        repo.upsert_task(task_data)

        # 8. Create run with idempotency handling
        raw_idemp = (
            request.headers.get("Idempotency-Key")
            or request.headers.get("idempotency-key")
            or payload.idempotency_key
        )
        idempotency_key = raw_idemp.strip() if raw_idemp and raw_idemp.strip() else None
        prefix = getattr(settings, "repomedic_acceptance_prefix", "")
        run_id = f"{prefix}{uuid.uuid4().hex}" if prefix else f"run_{uuid.uuid4().hex}"

        run = repo.create_run(
            run_id=run_id,
            task_id=task_id,
            mode=mode,
            search_mode=payload.search_mode,
            max_run_usd=max_run_usd,
            idempotency_key=idempotency_key,
        )

        if run.run_id != run_id:
            logger.info("Idempotent replay for custom key %s returning existing run %s", idempotency_key, run.run_id)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=run.model_dump(),
            )

        # 9. Enqueue to SQS if configured
        queue_url = (
            getattr(settings, "repair_queue_url", "")
            or getattr(settings, "repomedic_repair_queue_url", "")
        ).strip()
        if queue_url:
            try:
                import boto3

                sqs = getattr(request.app.state, "sqs_client", None)
                if sqs is None:
                    sqs = boto3.client("sqs")
                sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps({"run_id": run_id}),
                )
                logger.info("Enqueued custom run %s to SQS queue %s", run_id, queue_url)
            except Exception as e:
                logger.exception("Failed to enqueue custom run %s to SQS %s: %s", run_id, queue_url, e)
                try:
                    repo.finish_run(
                        run_id,
                        state="failed",
                        reason="Failed to enqueue task to SQS",
                    )
                except Exception as cleanup_err:
                    logger.warning("Failed to mark run %s as failed after SQS error: %s", run_id, cleanup_err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to enqueue repair task to background queue",
                )

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=run.model_dump(),
        )

    @app.post("/api/runs", status_code=status.HTTP_202_ACCEPTED, response_model=RunSummary)
    def create_run(
        request: Request,
        payload: CreateRunRequest,
        repo: D1StorageRepository = Depends(get_repository),
    ) -> RunSummary:
        if (
            payload.task_id.lower().startswith("custom")
            or payload.task_id.lower().startswith("task-custom")
            or payload.task_id.lower() == "custom"
        ):
            if not (
                getattr(settings, "repomedic_custom_execution_enabled", False)
                and payload.task_id.startswith("TASK-CUSTOM-")
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Custom repository execution is disabled. Custom inputs cannot be enqueued or executed.",
                )

        task = repo.get_task(payload.task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task '{payload.task_id}' not found",
            )

        # Enforce server side supported demo execution policy
        policy = getattr(settings, "repomedic_task_execution_policy", "supported_demo")
        is_custom_allowed = (
            getattr(settings, "repomedic_custom_execution_enabled", False)
            and payload.task_id.startswith("TASK-CUSTOM-")
        )
        if policy == "supported_demo" and payload.task_id not in SUPPORTED_DEMO_TASK_IDS and not is_custom_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Execution policy violation: task '{payload.task_id}' is not an approved demo task. "
                    f"Only supported demo tasks ({', '.join(SUPPORTED_DEMO_TASK_IDS)}) can be executed in this safe product slice."
                ),
            )

        mode = payload.mode or getattr(settings, "repomedic_mode", "offline")
        max_run_usd = getattr(settings, "repomedic_max_run_usd", 2.0)
        total_budget = getattr(settings, "repomedic_total_budget_usd", 25.0)

        if mode == "disabled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mode disabled",
            )
        committed_usage = repo.get_total_committed_usd()
        if (committed_usage + max_run_usd) > total_budget:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Budget unavailable",
            )

        stale_timeout = getattr(settings, "repomedic_stale_queued_timeout_seconds", 300.0)
        existing_queued = [
            r for r in repo.list_runs(task_id=payload.task_id, limit=5)
            if r.state == "queued" and r.created_at
        ]
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for qr in existing_queued:
            try:
                c_dt = datetime.datetime.fromisoformat(qr.created_at.replace("Z", "+00:00"))
                if (now_utc - c_dt).total_seconds() > stale_timeout:
                    repo.finish_run(
                        qr.run_id,
                        state="failed",
                        reason="Run timed out in queue without dispatch or worker claim",
                    )
            except Exception:
                pass

        raw_idemp = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key") or payload.idempotency_key
        idempotency_key = raw_idemp.strip() if raw_idemp and raw_idemp.strip() else None

        prefix = getattr(settings, "repomedic_acceptance_prefix", "")
        run_id = f"{prefix}{uuid.uuid4().hex}" if prefix else f"run_{uuid.uuid4().hex}"
        run = repo.create_run(
            run_id=run_id,
            task_id=payload.task_id,
            mode=mode,
            search_mode=payload.search_mode,
            max_run_usd=max_run_usd,
            idempotency_key=idempotency_key,
        )

        if run.run_id != run_id:
            logger.info("Idempotent replay for key %s returning existing run %s", idempotency_key, run.run_id)
            return run

        queue_url = (
            getattr(settings, "repair_queue_url", "")
            or getattr(settings, "repomedic_repair_queue_url", "")
        ).strip()
        if queue_url:
            try:
                import boto3

                sqs = getattr(request.app.state, "sqs_client", None)
                if sqs is None:
                    sqs = boto3.client("sqs")
                sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps({"run_id": run_id}),
                )
                logger.info("Enqueued run %s to SQS queue %s", run_id, queue_url)
            except Exception as e:
                logger.exception("Failed to enqueue run %s to SQS %s: %s", run_id, queue_url, e)
                try:
                    repo.finish_run(
                        run_id,
                        state="failed",
                        reason="Failed to enqueue task to SQS",
                    )
                except Exception as cleanup_err:
                    logger.warning("Failed to mark run %s as failed after SQS error: %s", run_id, cleanup_err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to enqueue repair task to background queue",
                )

        return run

    @app.get("/api/runs/{id}", response_model=RunSummary)
    def get_run(
        id: str,
        repo: D1StorageRepository = Depends(get_repository),
    ) -> RunSummary:
        return repo.get_run(id)

    @app.get("/api/runs/{id}/events")
    async def stream_run_events(
        id: str,
        request: Request,
        after: int = Query(default=0, ge=0),
        repo: D1StorageRepository = Depends(get_repository),
    ) -> StreamingResponse:
        run = await asyncio.to_thread(repo.get_run, id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{id}' not found",
            )

        last_event_id_header = request.headers.get("last-event-id")
        start_cursor = after
        if last_event_id_header and last_event_id_header.isdigit():
            start_cursor = max(start_cursor, int(last_event_id_header))

        async def event_generator() -> AsyncIterator[str]:
            cursor = start_cursor
            loop = asyncio.get_running_loop()
            last_heartbeat = loop.time()
            cycle_count = 0

            while True:
                if await request.is_disconnected():
                    break

                events = await asyncio.to_thread(repo.list_events, id, after=cursor)
                for ev in events:
                    yield f"id: {ev.seq}\nevent: {ev.type}\ndata: {ev.model_dump_json()}\n\n"
                    if ev.seq > cursor:
                        cursor = ev.seq

                terminal_event = any(ev.type in ("run.finished", "run.failed", "run.cancelled") for ev in events)
                if terminal_event:
                    is_terminal = True
                elif cycle_count % 3 == 0:
                    run_state = await asyncio.to_thread(repo.get_run_state, id)
                    is_terminal = run_state in ("succeeded", "failed", "cancelled")
                else:
                    is_terminal = False

                if is_terminal:
                    trailing = await asyncio.to_thread(repo.list_events, id, after=cursor)
                    for ev in trailing:
                        yield f"id: {ev.seq}\nevent: {ev.type}\ndata: {ev.model_dump_json()}\n\n"
                        if ev.seq > cursor:
                            cursor = ev.seq
                    break

                now = loop.time()
                if now - last_heartbeat >= 15.0:
                    yield ": heartbeat\n\n"
                    last_heartbeat = now

                cycle_count += 1
                await asyncio.sleep(1.5)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/runs/{id}/cancel", response_model=RunSummary)
    def cancel_run(
        id: str,
        repo: D1StorageRepository = Depends(get_repository),
    ) -> RunSummary:
        run = repo.get_run(id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{id}' not found",
            )

        # Idempotent: terminal runs return unchanged summary
        if run.state in ("succeeded", "failed", "cancelled"):
            return run

        try:
            repo.finish_run(id, state="cancelled", reason="user cancelled")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                pass
            else:
                raise

        updated = repo.get_run(id)
        return updated or run

    @app.get("/api/runs/{id}/artifacts/{artifact_id}")
    def get_artifact(
        id: str,
        artifact_id: str,
        repo: D1StorageRepository = Depends(get_repository),
    ) -> Response:
        run = repo.get_run(id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{id}' not found",
            )

        matching = next(
            (
                a
                for a in run.artifacts
                if a.artifact_id == artifact_id or a.kind == artifact_id or a.filename == artifact_id
            ),
            None,
        )
        if matching is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{artifact_id}' not found for run '{id}'",
            )

        try:
            content = repo.get_artifact_content(id, matching.artifact_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Artifact '{artifact_id}' not found",
                )
            raise

        if matching.kind == "patch":
            media_type = "text/x-diff; charset=utf-8"
        elif matching.kind == "evidence":
            media_type = "application/json"
        elif matching.kind == "log":
            media_type = "text/plain; charset=utf-8"
        else:
            media_type = "application/octet-stream"

        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{matching.filename}"',
            },
        )

    @app.get("/api/runs", response_model=RunsResponse)
    def list_runs(
        limit: int = Query(default=50, ge=1, le=100),
        task_id: str | None = Query(default=None),
        state: RunState | None = Query(default=None),
        repo: D1StorageRepository = Depends(get_repository),
    ) -> RunsResponse:
        runs = repo.list_runs(limit=limit, task_id=task_id, state=state)
        return RunsResponse(runs=runs)

    @app.get("/api/budget/usage")
    def get_budget_usage(
        repo: D1StorageRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return repo.client.get_budget_usage()

    @app.post("/api/runs/{id}/operations", status_code=status.HTTP_201_CREATED)
    async def create_operation(
        id: str,
        request: Request,
        repo: D1StorageRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        env_name = (
            os.getenv("REPOMEDIC_ENV")
            or os.getenv("ENVIRONMENT")
            or getattr(settings, "repomedic_env", "")
            or getattr(settings, "environment", "")
            or ""
        ).strip().lower()
        if env_name in ("production", "prod"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Internal operation reservation endpoint is disabled in production",
            )

        body = await request.json()
        op_id = body.get("operation_id")
        kind = body.get("kind", "model")
        reserved_micro_usd = body.get("reserved_micro_usd", 0)
        estimated_usd = float(reserved_micro_usd) / 1_000_000.0

        # Global spending limits must strictly come from server configuration
        global_budget_usd = getattr(settings, "repomedic_total_budget_usd", 25.0)

        return await asyncio.to_thread(
            repo.client.reserve_budget,
            run_id=id,
            operation_id=op_id,
            kind=kind,
            estimated_usd=estimated_usd,
            global_budget_usd=global_budget_usd,
        )

    return app


app = create_app()
