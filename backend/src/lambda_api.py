import asyncio
import logging
from typing import Any
from mangum import Mangum
from src.main import create_app, sync_task_fixtures
from src.storage.repository import D1StorageRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("repomedic.lambda_api")

app = create_app()

# Synchronize task fixtures once during container cold start
try:
    repo = D1StorageRepository()
    sync_task_fixtures(repo)
except Exception as e:
    logger.warning("Cold start task fixture sync skipped: %s", e)

_mangum = Mangum(app, lifespan="off")


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Lambda entrypoint ensuring an event loop exists for Python 3.13 compatibility."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return _mangum(event, context)
