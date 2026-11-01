"""Thin wrapper around the Anthropic SDK for schema-constrained JSON responses."""

import json
import logging
import time
from typing import Any, Protocol

import anthropic

from app.core.config import settings

log = logging.getLogger("claimlens.llm")


class LlmRefusalError(RuntimeError):
    """Claude (and its server-side fallback) declined the request."""


class StructuredLlm(Protocol):
    model: str

    def json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]: ...


class ClaudeStructuredLlm:
    """Calls Claude with a JSON schema output format.

    - The system prompt is identical on every call, so it is cached (cache_control).
    - Structured outputs (output_config.format) guarantee schema-valid JSON.
    - Server-side refusal fallback is enabled with the "default" routing mode.
    """

    def __init__(self, client: anthropic.Anthropic | None = None, model: str | None = None) -> None:
        self.client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
        self.model = model or settings.anthropic_model

    def json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": settings.anthropic_effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        )
        log.info(
            "claude call model=%s stop=%s in=%s out=%s cache_read=%s latency_ms=%d",
            response.model,
            response.stop_reason,
            response.usage.input_tokens,
            response.usage.output_tokens,
            response.usage.cache_read_input_tokens,
            (time.perf_counter() - started) * 1000,
        )
        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise LlmRefusalError(f"Claude declined the request (category={category})")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("Claude response was truncated at max_tokens")
        text = next(block.text for block in response.content if block.type == "text")
        return json.loads(text)
