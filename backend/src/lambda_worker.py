import asyncio
import json
import logging
from typing import Any

from src.contracts import RepairRequest, RepairResult, TaskRecipe
from src.storage.exceptions import StorageConflictError, StorageError, StorageNotFoundError
from src.storage.repository import D1StorageRepository
from src.worker import _is_409_conflict, execute_claimed_run

logger = logging.getLogger("repomedic.lambda_worker")


def _extract_run_id(body: str) -> str | None:
    body = body.strip()
    if not body:
        return None
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            return data.get("run_id")
        if isinstance(data, str):
            return data
    except json.JSONDecodeError:
        # Fallback if raw run_id string was sent as body
        if body.startswith("run_"):
            return body
    return None


def _is_404_not_found(err: Exception) -> bool:
    if isinstance(err, StorageNotFoundError):
        return True
    if getattr(err, "status_code", None) == 404:
        return True
    if hasattr(err, "response") and getattr(err.response, "status_code", None) == 404:
        return True
    return False


async def process_sqs_records(
    records: list[dict[str, Any]],
    repo: D1StorageRepository | None = None,
    repair_fn: Any | None = None,
    use_real_engine: bool | None = None,
) -> list[dict[str, str]]:
    """Process SQS records with atomic CAS claim and execution.

    Returns a list of batchItemFailures for messages that should be retried.
    """
    if repo is None:
        repo = D1StorageRepository()

    failures: list[dict[str, str]] = []

    for record in records:
        message_id = record.get("messageId", "")
        body = record.get("body", "")
        run_id = _extract_run_id(body)

        if not run_id:
            logger.warning("Record %s contained invalid or missing run_id in body: %r", message_id, body)
            continue

        # 1. Compare And Swap atomic claim
        try:
            repo.update_run_state(run_id, state="running", from_state="queued")
            logger.info("Atomically claimed queued run %s for execution from SQS record %s", run_id, message_id)
        except (StorageConflictError, StorageError, Exception) as e:
            if _is_409_conflict(e) or isinstance(e, StorageConflictError):
                logger.info(
                    "Run %s already claimed, finished, or cancelled (%s); acknowledging SQS message",
                    run_id,
                    e,
                )
                continue
            if _is_404_not_found(e):
                logger.warning("Run %s not found in repository (%s); discarding SQS message", run_id, e)
                continue

            logger.error("Transient error claiming run %s: %s; reporting failure to SQS for redrive", run_id, e)
            if message_id:
                failures.append({"itemIdentifier": message_id})
            continue

        # 2. Execute the claimed repair job
        try:
            await execute_claimed_run(
                run_id=run_id,
                repo=repo,
                repair_fn=repair_fn,
                use_real_engine=use_real_engine,
            )
            logger.info("Finished processing run %s from SQS record %s", run_id, message_id)
        except Exception as e:
            logger.exception("Unexpected exception executing claimed run %s: %s", run_id, e)
            if message_id:
                failures.append({"itemIdentifier": message_id})

    return failures


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """AWS Lambda entrypoint for SQS repair queue events."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    records = event.get("Records", [])
    failures = asyncio.run(process_sqs_records(records))
    return {"batchItemFailures": failures}
