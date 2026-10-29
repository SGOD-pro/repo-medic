import pytest
from src.auth.tokens import generate_token, decode_token, verify_claims

SECRET = "super-safe-dev-secret-key-12345"


def test_generate_token():
    token = generate_token("user_101", "editor", SECRET)
    assert isinstance(token, str)
    parts = token.split(".")
    assert len(parts) == 3


def test_decode_token():
    token = generate_token("user_102", "admin", SECRET)
    claims = decode_token(token, SECRET)
    assert claims["sub"] == "user_102"
    assert claims["role"] == "admin"


def test_verify_claims():
    token = generate_token("user_103", "analyst", SECRET)
    assert verify_claims(token, SECRET, "analyst") is True
    assert verify_claims(token, SECRET, "admin") is False
