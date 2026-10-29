import pytest
from src.users.schemas import create_user_profile, UserProfile


def test_valid_user_profile():
    profile = create_user_profile("dev_medic", "Repo Developer", 28)
    assert profile["username"] == "dev_medic"
    assert profile["display_name"] == "Repo Developer"
    assert profile["age"] == 28


def test_invalid_username_format():
    with pytest.raises(Exception):
        create_user_profile("bad username with spaces!", "Bad User", 25)
