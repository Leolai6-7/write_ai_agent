"""Multi-model LLM client - routes calls to provider backends.

Supports: AWS Bedrock (primary), OpenAI, Anthropic direct API.
Each provider is implemented in infrastructure/providers/.
"""

from __future__ import annotations

import json
import time
from typing import Type

import tiktoken
from pydantic import BaseModel, ValidationError

from infrastructure.logger import get_logger
from infrastructure.providers.base import LLMProvider

logger = get_logger("llm_client")

# Approximate pricing per 1M tokens (input/output)
PRICING = {
    "anthropic.claude-sonnet-4-20250514-v1:0": (3.0, 15.0),
    "anthropic.claude-haiku-4-5-20251001-v1:0": (0.8, 4.0),
    "us.anthropic.claude-sonnet-4-20250514-v1:0": (3.0, 15.0),
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": (0.8, 4.0),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-3.5-turbo": (0.5, 1.5),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.8, 4.0),
}


class TokenUsage(BaseModel):
    """Track token usage for a single LLM call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    cost_usd: float = 0.0


class LLMClient:
    """Unified LLM client that routes calls to the appropriate provider.

    Model routing:
        - "bedrock:..." → AWS Bedrock
        - "claude-..." + Anthropic provider → Anthropic direct
        - "gpt-..." + OpenAI provider → OpenAI
        - Default fallback: Bedrock for claude models
    """

    def __init__(
        self,
        aws_region: str = "us-west-2",
        aws_profile: str | None = None,
        openai_api_key: str = "",
        anthropic_api_key: str = "",
    ):
        self._providers: dict[str, LLMProvider] = {}

        # Register providers (lazy — only create if credentials available)
        from infrastructure.providers.bedrock import BedrockProvider
        self._providers["bedrock"] = BedrockProvider(aws_region, aws_profile)

        if openai_api_key:
            from infrastructure.providers.openai_provider import OpenAIProvider
            self._providers["openai"] = OpenAIProvider(openai_api_key)

        if anthropic_api_key:
            from infrastructure.providers.anthropic_provider import AnthropicProvider
            self._providers["anthropic"] = AnthropicProvider(anthropic_api_key)

        self._encoder = tiktoken.get_encoding("cl100k_base")
        self.total_usage: list[TokenUsage] = []

    def count_tokens(self, text: str) -> int:
        return len(self._encoder.encode(text))

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """Strip markdown code fences from LLM response."""
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.index("\n") if "\n" in text else len(text)
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _route(self, model: str) -> LLMProvider:
        """Route model to the appropriate provider."""
        if model.startswith("bedrock:"):
            return self._providers["bedrock"]
        if "claude" in model.lower() and "anthropic" in self._providers:
            return self._providers["anthropic"]
        if "openai" in self._providers:
            return self._providers["openai"]
        # Fallback: bedrock for claude/anthropic models
        if "claude" in model.lower() or "anthropic" in model.lower():
            return self._providers["bedrock"]
        raise RuntimeError(f"No provider available for model: {model}")

    @staticmethod
    def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        clean_model = model.removeprefix("bedrock:")
        pricing = PRICING.get(clean_model, (10.0, 30.0))
        return (prompt_tokens * pricing[0] + completion_tokens * pricing[1]) / 1_000_000

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str = "bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        response_model: Type[BaseModel] | None = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> str | BaseModel:
        """Send a chat completion request with automatic retry."""
        last_error = None
        provider = self._route(model)

        for attempt in range(1, max_retries + 1):
            try:
                result, usage = provider.call(
                    messages, model, temperature, max_tokens, response_model
                )
                usage.cost_usd = self._estimate_cost(
                    usage.model or model, usage.prompt_tokens, usage.completion_tokens
                )
                self.total_usage.append(usage)
                logger.debug(
                    "LLM call: model=%s, prompt=%d, completion=%d, cost=$%.4f",
                    model, usage.prompt_tokens, usage.completion_tokens, usage.cost_usd,
                )
                return result

            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning("Parse error (attempt %d/%d): %s", attempt, max_retries, e)
                last_error = e
                if response_model and attempt < max_retries:
                    messages = messages + [
                        {"role": "assistant", "content": "I apologize for the formatting error."},
                        {"role": "user", "content": (
                            f"Your previous response failed to parse: {e}\n"
                            f"Please respond with valid JSON only. "
                            f"Do NOT wrap in markdown code fences like ```json."
                        )},
                    ]
            except Exception as e:
                logger.warning("API error (attempt %d/%d): %s", attempt, max_retries, e)
                last_error = e
                if attempt < max_retries:
                    delay = retry_delay * (2 ** (attempt - 1))
                    logger.info("Retrying in %.1fs...", delay)
                    time.sleep(delay)

        raise RuntimeError(
            f"LLM call failed after {max_retries} attempts: {last_error}"
        ) from last_error

    def get_total_cost(self) -> float:
        return sum(u.cost_usd for u in self.total_usage)

    def get_usage_summary(self) -> dict:
        summary: dict[str, dict] = {}
        for u in self.total_usage:
            if u.model not in summary:
                summary[u.model] = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
            summary[u.model]["calls"] += 1
            summary[u.model]["prompt_tokens"] += u.prompt_tokens
            summary[u.model]["completion_tokens"] += u.completion_tokens
            summary[u.model]["cost"] += u.cost_usd
        return summary
