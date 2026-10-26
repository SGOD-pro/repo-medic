import sys
from pathlib import Path
import pytest

# Add backend directory to sys.path so 'src' can be imported in all test runs
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


@pytest.fixture(autouse=True)
def _isolate_test_settings(monkeypatch):
    """Isolate unit tests from production environment overrides."""
    from src.config import settings
    monkeypatch.setattr(settings, "repomedic_mode", "offline")
    monkeypatch.setattr(settings, "repomedic_use_real_engine", False)
