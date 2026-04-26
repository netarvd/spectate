from __future__ import annotations

import os
from typing import Any, Protocol

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 8192


class SpecLLMClient(Protocol):
    def generate(
        self,
        *,
        english: str,
        system_prompt: str,
        model: str,
        max_tokens: int,
    ) -> str: ...


class AnthropicSpecClient:
    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            import anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set")
            client = anthropic.Anthropic(api_key=api_key)
        self._client = client

    def generate(
        self,
        *,
        english: str,
        system_prompt: str,
        model: str,
        max_tokens: int,
    ) -> str:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": english}],
        )
        parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)  # type: ignore[union-attr]
        return "".join(parts)


def generate_spec(
    english: str,
    *,
    system_prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    client: SpecLLMClient | None = None,
) -> str:
    if client is None:
        client = AnthropicSpecClient()
    return client.generate(
        english=english,
        system_prompt=system_prompt,
        model=model,
        max_tokens=max_tokens,
    )
