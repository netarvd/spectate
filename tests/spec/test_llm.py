from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest

from spectate.spec.llm import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    AnthropicSpecClient,
    generate_spec,
)


class _FakeMessages:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="version: 1\n")],
        )


class _FakeAnthropic:
    def __init__(self) -> None:
        self.messages = _FakeMessages()


def test_generate_spec_calls_anthropic_with_expected_payload() -> None:
    fake = _FakeAnthropic()
    client = AnthropicSpecClient(client=fake)
    out = generate_spec(
        "allow outbound to api.example.com",
        system_prompt="SYSTEM",
        client=client,
    )
    assert out == "version: 1\n"
    assert len(fake.messages.calls) == 1
    call = fake.messages.calls[0]
    assert call["model"] == DEFAULT_MODEL
    assert call["max_tokens"] == DEFAULT_MAX_TOKENS
    assert call["system"] == [
        {"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}
    ]
    assert call["messages"] == [{"role": "user", "content": "allow outbound to api.example.com"}]


def test_generate_spec_respects_model_override() -> None:
    fake = _FakeAnthropic()
    client = AnthropicSpecClient(client=fake)
    generate_spec(
        "x",
        system_prompt="S",
        model="claude-haiku-4-5",
        client=client,
    )
    assert fake.messages.calls[0]["model"] == "claude-haiku-4-5"


def test_generate_spec_concatenates_text_blocks() -> None:
    class MultiBlockMessages:
        def create(self, **_: Any) -> Any:
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="text", text="version: 1\n"),
                    SimpleNamespace(type="text", text="network:\n"),
                ]
            )

    client = AnthropicSpecClient(client=SimpleNamespace(messages=MultiBlockMessages()))
    out = generate_spec("x", system_prompt="S", client=client)
    assert out == "version: 1\nnetwork:\n"


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set; skipping integration test",
)
def test_integration_returns_non_empty_string() -> None:
    pytest.importorskip("anthropic")
    out = generate_spec(
        "Allow outbound network calls to api.example.com only.",
        system_prompt=(
            "You produce Spectate Spec YAML. Output only the YAML body, no fences. "
            "Top-level field 'version: 1' is required."
        ),
    )
    assert out.strip()
