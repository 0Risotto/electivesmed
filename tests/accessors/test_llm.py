import sys
import types

import pytest

from electivesmed.accessors.llm import DeepSeekAccessor
from electivesmed.errors import LlmError, LlmUnavailable


def _fake_litellm(content: str | None = '{"ok": true}', fail: bool = False):
    module = types.ModuleType("litellm")

    def completion(**kwargs):
        if fail:
            raise RuntimeError("api down")
        message = types.SimpleNamespace(content=content)
        choice = types.SimpleNamespace(message=message)
        return types.SimpleNamespace(choices=[choice])

    module.completion = completion
    return module


def test_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    accessor = DeepSeekAccessor(api_key="")

    assert not accessor.available
    with pytest.raises(LlmUnavailable):
        accessor.chat_json("system", "user")


def test_chat_json_parses_fenced_response(monkeypatch):
    monkeypatch.setitem(sys.modules, "litellm", _fake_litellm('```json\n{"ok": true}\n```'))
    accessor = DeepSeekAccessor(api_key="test-key")

    assert accessor.chat_json("system", "user") == {"ok": True}
    assert accessor.available


def test_chat_text_returns_raw_content(monkeypatch):
    monkeypatch.setitem(sys.modules, "litellm", _fake_litellm("plain text"))
    accessor = DeepSeekAccessor(api_key="test-key")

    assert accessor.chat_text("system", "user") == "plain text"


def test_empty_response_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "litellm", _fake_litellm(None))
    accessor = DeepSeekAccessor(api_key="test-key")

    with pytest.raises(LlmError, match="empty"):
        accessor.chat_text("system", "user")


def test_provider_failure_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "litellm", _fake_litellm(fail=True))
    accessor = DeepSeekAccessor(api_key="test-key")

    with pytest.raises(LlmError, match="DeepSeek call failed"):
        accessor.chat_text("system", "user")


def test_reasoner_model_skips_json_mode(monkeypatch):
    captured: dict = {}

    def completion(**kwargs):
        captured.update(kwargs)
        message = types.SimpleNamespace(content="{}")
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    module = types.ModuleType("litellm")
    module.completion = completion
    monkeypatch.setitem(sys.modules, "litellm", module)

    accessor = DeepSeekAccessor(api_key="test-key")
    accessor.chat_json("system", "user", model="deepseek/deepseek-reasoner")

    assert "response_format" not in captured
    assert captured["model"] == "deepseek/deepseek-reasoner"


def test_environment_api_key_is_used(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env")
    accessor = DeepSeekAccessor()

    assert accessor.available
    assert accessor.api_key == "from-env"
