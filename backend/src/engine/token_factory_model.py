import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from src.config import settings
from src.engine.adapters import ModelAdapter

logger = logging.getLogger("repomedic.token_factory_model")


class TokenFactoryModelAdapter(ModelAdapter):
    """
    Live model adapter connecting to Nebius Token Factory inference endpoint.
    Implements OpenAI-compatible chat completions over async HTTP without automatic SDK retries.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 60.0,
        enable_thinking: Optional[bool] = None,
    ):
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = (
                os.getenv("TOKEN_FACTORY_API_KEY")
                or settings.token_factory_api_key
                or os.getenv("NEBIUS_API_KEY")
                or settings.nebius_api_key
            ).strip()
        raw_base_url = (base_url or settings.token_factory_base_url).strip()
        if not raw_base_url.endswith("/"):
            raw_base_url += "/"
        self.base_url = raw_base_url
        self.model = (model or settings.token_factory_model).strip()
        self.timeout_seconds = timeout_seconds
        if enable_thinking is not None:
            self.enable_thinking = enable_thinking
        else:
            self.enable_thinking = getattr(settings, "token_factory_enable_thinking", False)

        self.call_count: int = 0
        self.prompts: List[str] = []
        self.last_usage: Dict[str, Any] = {}
        self.last_finish_reason: Optional[str] = None
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0

    def __repr__(self) -> str:
        # Sanitize key from any string representation or log inspection
        masked_key = f"{self.api_key[:6]}...{self.api_key[-4:]}" if len(self.api_key) > 10 else "***"
        return (
            f"TokenFactoryModelAdapter(model='{self.model}', base_url='{self.base_url}', "
            f"api_key='{masked_key}')"
        )

    async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        """
        Executes a single model completion against Nebius Token Factory.
        Zero SDK automatic retries to ensure strict budget compliance.
        """
        if not self.api_key:
            raise ValueError(
                "NEBIUS_API_KEY is not configured. Provide it in .env or constructor."
            )

        self.call_count += 1
        self.prompts.append(prompt)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an automated code repair system. "
                        "Your response MUST begin immediately on line 1 with the diff header (e.g. '--- a/path'). "
                        "Do not include any conversational preamble, reasoning, explanations, or markdown outside the diff. "
                        "Output strictly valid unified diff syntax."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
        if not self.enable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        # Zero retries to guarantee budget compliance per operation
        transport = httpx.AsyncHTTPTransport(retries=0)
        async with httpx.AsyncClient(transport=transport, timeout=self.timeout_seconds) as client:
            endpoint = f"{self.base_url}chat/completions"
            try:
                response = await client.post(endpoint, headers=headers, json=payload)
            except Exception as exc:
                raise RuntimeError(
                    f"Nebius Token Factory request failed for model '{self.model}': {exc}"
                ) from exc

        if response.status_code != 200:
            raise RuntimeError(
                f"Nebius Token Factory returned error {response.status_code}: {response.text}"
            )

        data = response.json()
        self.last_usage = data.get("usage", {})
        self.total_prompt_tokens += self.last_usage.get("prompt_tokens", 0)
        self.total_completion_tokens += self.last_usage.get("completion_tokens", 0)

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"Nebius Token Factory returned no choices: {data}")

        first_choice = choices[0]
        finish_reason = first_choice.get("finish_reason")
        self.last_finish_reason = finish_reason
        if finish_reason == "length":
            logger.warning(
                "Nebius Token Factory completion truncated at token limit (finish_reason='length', model='%s', completion_tokens=%s)",
                self.model,
                self.last_usage.get("completion_tokens"),
            )
            raise RuntimeError(
                f"Model completion truncated at token limit (finish_reason='length', model='{self.model}')"
            )
        else:
            logger.info(
                "Nebius Token Factory completion finished (finish_reason='%s', completion_tokens=%s)",
                finish_reason,
                self.last_usage.get("completion_tokens"),
            )

        message = first_choice.get("message", {})
        content = message.get("content")

        if content:
            return content.strip()

        # If model used all tokens on reasoning without content output
        reasoning = message.get("reasoning_content") or message.get("reasoning")
        if reasoning:
            return reasoning.strip()

        return ""
