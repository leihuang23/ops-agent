from __future__ import annotations

from typing import Literal

ProviderName = Literal["openai", "anthropic"]

OPENAI_MODELS: frozenset[str] = frozenset({"gpt-4o-mini", "gpt-4o"})
ANTHROPIC_MODELS: frozenset[str] = frozenset(
    {
        "claude-fable-5",
        "claude-opus-4-8",
        "claude-sonnet-5",
        "claude-haiku-4-5",
        "claude-haiku-4-5-20251001",
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
        "claude-3-haiku-20240307",
    }
)
ALLOWED_LLM_MODELS: frozenset[str] = OPENAI_MODELS | ANTHROPIC_MODELS


def provider_for_model(model: str) -> ProviderName | None:
    if model in OPENAI_MODELS:
        return "openai"
    if model in ANTHROPIC_MODELS:
        return "anthropic"
    return None
