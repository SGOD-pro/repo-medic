from pathlib import Path
from typing import Optional


def find_task_fixture_dir() -> Optional[Path]:
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "fixtures" / "tasks",
        Path(__file__).resolve().parent.parent / "fixtures" / "tasks",
        Path(__file__).resolve().parent / "fixtures" / "tasks",
        Path("fixtures/tasks"),
        Path("../fixtures/tasks"),
        Path("/var/task/fixtures/tasks"),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None
