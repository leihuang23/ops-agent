from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    root_cause: str = Field(min_length=1)
    confidence: Literal["low", "medium", "high"] = "low"
    next_actions: list[str] = Field(default_factory=list)
    reasoning: str = ""


class LLMUsage(BaseModel):
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    used_llm: bool = False
    fallback_reason: str | None = None
