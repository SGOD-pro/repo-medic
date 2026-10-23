from typing import Any, Dict
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from src.config import settings
from src.engine.token_factory_model import TokenFactoryModelAdapter


@pytest.mark.asyncio
async def test_token_factory_missing_api_key_raises():
    """covers: AC-1, AC-7 - Fails immediately when API key is missing."""
    with patch.object(settings, "token_factory_api_key", ""), \
         patch.object(settings, "nebius_api_key", ""):
        adapter = TokenFactoryModelAdapter(api_key="", base_url="http://test", model="test-model")
        with pytest.raises(ValueError, match="NEBIUS_API_KEY is not configured"):
            await adapter.complete("Generate repair diff")


def test_token_factory_repr_masks_api_key():
    """covers: AC-7 - Sensitive API keys are never exposed in string representations."""
    adapter = TokenFactoryModelAdapter(
        api_key="token-secret-very-long-key-12345",
        base_url="https://api.test/v1/",
        model="nvidia/nemotron-3-super-120b-a12b",
    )
    repr_str = repr(adapter)
    assert "token-secret-very-long-key-12345" not in repr_str
    assert "token-...2345" in repr_str

    short_adapter = TokenFactoryModelAdapter(
        api_key="short",
        base_url="https://api.test/v1/",
        model="test-model",
    )
    assert "***" in repr(short_adapter)


@pytest.mark.asyncio
async def test_token_factory_complete_success():
    """covers: AC-7 - Successfully completes chat prompt, extracts diff, and records token usage."""
    adapter = TokenFactoryModelAdapter(
        api_key="test-api-key-123456789",
        base_url="https://api.test/v1/",
        model="nvidia/nemotron-3-super-120b-a12b",
    )

    fake_response = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "```diff\n--- a/src/core.py\n+++ b/src/core.py\n@@ -1 +1 @@\n-old\n+new\n```",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 45,
            "total_tokens": 165,
        },
    }

    mock_resp = httpx.Response(
        status_code=200,
        json=fake_response,
        request=httpx.Request("POST", "https://api.test/v1/chat/completions"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        result = await adapter.complete("Fix sqlalchemy deprecation", max_tokens=1024)

        assert "--- a/src/core.py" in result
        assert adapter.call_count == 1
        assert adapter.total_prompt_tokens == 120
        assert adapter.total_completion_tokens == 45
        assert adapter.last_usage.get("total_tokens") == 165

        # Verify zero retries and payload structure
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs.get("json", {})
        assert payload.get("model") == "nvidia/nemotron-3-super-120b-a12b"
        assert payload.get("max_tokens") == 1024
        assert payload.get("temperature") == 0.0


@pytest.mark.asyncio
async def test_token_factory_complete_reasoning_fallback():
    """covers: AC-7 - Falls back to reasoning_content if content is empty."""
    adapter = TokenFactoryModelAdapter(
        api_key="test-api-key-123456789",
        base_url="https://api.test/v1/",
        model="test-model",
    )

    fake_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "reasoning_content": "Reasoned diff content output",
                }
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    }

    mock_resp = httpx.Response(
        status_code=200,
        json=fake_response,
        request=httpx.Request("POST", "https://api.test/v1/chat/completions"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await adapter.complete("Generate candidate")
        assert result == "Reasoned diff content output"


@pytest.mark.asyncio
async def test_token_factory_complete_http_error():
    """covers: AC-7 - Raises RuntimeError on non-200 HTTP responses without silent retries."""
    adapter = TokenFactoryModelAdapter(
        api_key="test-api-key-123456789",
        base_url="https://api.test/v1/",
        model="test-model",
    )

    mock_resp = httpx.Response(
        status_code=401,
        text="Unauthorized: invalid api key",
        request=httpx.Request("POST", "https://api.test/v1/chat/completions"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(RuntimeError, match="Nebius Token Factory returned error 401"):
            await adapter.complete("Fix bug")


@pytest.mark.asyncio
async def test_token_factory_complete_network_exception():
    """covers: AC-7 - Wraps network communication failures into informative RuntimeError."""
    adapter = TokenFactoryModelAdapter(
        api_key="test-api-key-123456789",
        base_url="https://api.test/v1/",
        model="test-model",
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        with pytest.raises(RuntimeError, match="Nebius Token Factory request failed"):
            await adapter.complete("Fix bug")


@pytest.mark.asyncio
async def test_token_factory_complete_no_choices_error():
    """covers: AC-7 - Raises RuntimeError if API returns response with empty choices."""
    adapter = TokenFactoryModelAdapter(
        api_key="test-api-key-123456789",
        base_url="https://api.test/v1/",
        model="test-model",
    )

    mock_resp = httpx.Response(
        status_code=200,
        json={"choices": []},
        request=httpx.Request("POST", "https://api.test/v1/chat/completions"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(RuntimeError, match="Nebius Token Factory returned no choices"):
            await adapter.complete("Fix bug")
