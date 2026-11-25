"""LLM adapter: any OpenAI-compatible endpoint (OpenRouter, Venice AI)."""

from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI

from app.backend.core.errors import ConfigError
from app.backend.core.settings import Settings


@dataclass(frozen=True)
class LLM:
    client: AsyncOpenAI
    model: str


def make_llm(settings: Settings) -> LLM:
    missing = [
        name
        for name, value in (
            ("LLM_BASE_URL", settings.llm_base_url),
            ("LLM_API_KEY", settings.llm_api_key),
            ("LLM_MODEL", settings.llm_model),
        )
        if not value
    ]
    if missing:
        raise ConfigError(f"LLM is not configured: set {', '.join(missing)} in .env.")
    client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    return LLM(client=client, model=settings.llm_model)
