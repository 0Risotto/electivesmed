"""DeepSeek LLM accessor via LiteLLM (no AWS anywhere)."""

import os
from typing import Protocol

from ..constants.limits import LLM_MAX_TOKENS, LLM_TEMPERATURE
from ..constants.providers import (
    DEEPSEEK_API_KEY_ENV,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_CHAT_MODEL,
)
from ..errors import LlmError, LlmUnavailable
from ..utils.json import extract_json


class LlmAccessor(Protocol):
    @property
    def available(self) -> bool: ...

    def chat_json(
        self,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict: ...

    def chat_text(
        self,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str: ...


class DeepSeekAccessor:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEEPSEEK_BASE_URL,
        default_model: str = DEEPSEEK_CHAT_MODEL,
        temperature: float = LLM_TEMPERATURE,
    ) -> None:
        self.api_key = api_key or os.environ.get(DEEPSEEK_API_KEY_ENV, "")
        self.base_url = base_url
        self.default_model = default_model
        self.temperature = temperature

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _call(
        self,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        if not self.available:
            raise LlmUnavailable(
                f"{DEEPSEEK_API_KEY_ENV} is not set; add it to your .env to enable LLM calls"
            )
        from litellm import completion  # imported lazily to keep CLI startup snappy

        kwargs: dict = {
            "model": model or self.default_model,
            "api_key": self.api_key,
            "api_base": self.base_url,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or LLM_MAX_TOKENS,
        }
        if json_mode and "reasoner" not in (model or self.default_model):
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = completion(**kwargs)
        except Exception as exc:
            raise LlmError(f"DeepSeek call failed: {type(exc).__name__}: {exc}") from exc
        content = response.choices[0].message.content
        if not content:
            raise LlmError("DeepSeek returned an empty response")
        return content

    def chat_json(
        self,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        return extract_json(self._call(system, user, model, temperature, max_tokens, json_mode=True))

    def chat_text(
        self,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return self._call(system, user, model, temperature, max_tokens, json_mode=False)
