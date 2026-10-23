import pytest
from src.backend.database import init_db, get_user_count

def test_database_operations():
    init_db()
    count = get_user_count()
    assert count == 1
