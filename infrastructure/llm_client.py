"""Multi-model LLM client with retry, logging, and token tracking.

Supports: AWS Bedrock (primary), OpenAI, Anthropic direct API.
"""

from __future__ import annotations

import json
import time
from typing import Any, Type

import tiktoken
from pydantic import BaseModel, ValidationError

from infrastructure.logger import get_logger

logger = get_logger("llm_client")


class TokenUsage(BaseModel):
    """Track token usage for a single LLM call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    cost_usd: float = 0.0


class LLMClient:
    """Unified LLM client supporting AWS Bedrock, OpenAI, and Anthropic.

    Model routing:
        - "bedrock:..." → AWS Bedrock (e.g. "bedrock:anthropic.claude-sonnet-4-20250514-v1:0")
        - "claude-..." → Anthropic direct API
        - anything else → OpenAI
    """

    # Approximate pricing per 1M tokens (input/output)
    PRICING = {
        # Bedrock Claude models
        "anthropic.claude-sonnet-4-20250514-v1:0": (3.0, 15.0),
        "anthropic.claude-haiku-4-5-20251001-v1:0": (0.8, 4.0),
        "us.anthropic.claude-sonnet-4-20250514-v1:0": (3.0, 15.0),
        "us.anthropic.claude-haiku-4-5-20251001-v1:0": (0.8, 4.0),
        # OpenAI
        "gpt-4-turbo": (10.0, 30.0),
        "gpt-4o": (2.5, 10.0),
        "gpt-3.5-turbo": (0.5, 1.5),
        # Direct Anthropic
        "claude-sonnet-4-20250514": (3.0, 15.0),
        "claude-haiku-4-5-20251001": (0.8, 4.0),
    }

    def __init__(
        self,
        aws_region: str = "us-west-2",
        aws_profile: str | None = None,
        openai_api_key: str = "",
        anthropic_api_key: str = "",
    ):
        # AWS Bedrock client (lazy init)
        self._aws_region = aws_region
        self._aws_profile = aws_profile
        self._bedrock_client = None

        # Optional direct API clients
        self._openai = None
        self._anthropic = None
        if openai_api_key:
            from openai import OpenAI
            self._openai = OpenAI(api_key=openai_api_key)
        if anthropic_api_key:
            from anthropic import Anthropic
            self._anthropic = Anthropic(api_key=anthropic_api_key)

        self._encoder = tiktoken.get_encoding("cl100k_base")
        self.total_usage: list[TokenUsage] = []

    @property
    def bedrock(self):
        """Lazy-init Bedrock runtime client."""
        if self._bedrock_client is None:
            import boto3
            session_kwargs = {}
            if self._aws_profile:
                session_kwargs["profile_name"] = self._aws_profile
            session = boto3.Session(**session_kwargs)
            self._bedrock_client = session.client(
                "bedrock-runtime", region_name=self._aws_region
            )
        return self._bedrock_client

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        return len(self._encoder.encode(text))

    def _route_model(self, model: str) -> str:
        """Determine which backend to use: 'bedrock', 'anthropic', or 'openai'."""
        if model.startswith("bedrock:"):
            return "bedrock"
        if "claude" in model.lower() and self._anthropic:
            return "anthropic"
        if self._openai:
            return "openai"
        # Default: try bedrock for claude models
        if "claude" in model.lower() or "anthropic" in model.lower():
            return "bedrock"
        return "openai"

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        # Strip "bedrock:" prefix for pricing lookup
        clean_model = model.removeprefix("bedrock:")
        pricing = self.PRICING.get(clean_model, (10.0, 30.0))
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
        """Send a chat completion request with automatic retry and optional structured output."""
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                backend = self._route_model(model)

                if backend == "bedrock":
                    result, usage = self._call_bedrock(
                        messages, model, temperature, max_tokens, response_model
                    )
                elif backend == "anthropic":
                    result, usage = self._call_anthropic(
                        messages, model, temperature, max_tokens, response_model
                    )
                else:
                    result, usage = self._call_openai(
                        messages, model, temperature, max_tokens, response_model
                    )

                self.total_usage.append(usage)
                logger.debug(
                    "LLM call: backend=%s, model=%s, prompt=%d, completion=%d, cost=$%.4f",
                    backend, model, usage.prompt_tokens, usage.completion_tokens, usage.cost_usd,
                )
                return result

            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning("Parse error (attempt %d/%d): %s", attempt, max_retries, e)
                last_error = e
                if response_model and attempt < max_retries:
                    messages = messages + [
                        {"role": "assistant", "content": ""},
                        {"role": "user", "content": (
                            f"Your previous response failed to parse: {e}\n"
                            f"Please respond with valid JSON matching the schema."
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

    # ── AWS Bedrock ──────────────────────────────────────────────

    def _call_bedrock(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
        response_model: Type[BaseModel] | None,
    ) -> tuple[str | BaseModel, TokenUsage]:
        model_id = model.removeprefix("bedrock:")

        # Extract system message
        system_parts = []
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append({"text": msg["content"]})
            else:
                chat_messages.append({"role": msg["role"], "content": [{"text": msg["content"]}]})

        if response_model:
            schema_hint = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
            system_parts.append({"text": f"Respond in JSON matching this schema:\n{schema_hint}"})

        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": chat_messages,
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
        }
        if system_parts:
            kwargs["system"] = system_parts

        response = self.bedrock.converse(**kwargs)

        content = response["output"]["message"]["content"][0]["text"]
        token_usage = response.get("usage", {})

        usage = TokenUsage(
            prompt_tokens=token_usage.get("inputTokens", 0),
            completion_tokens=token_usage.get("outputTokens", 0),
            model=model_id,
        )
        usage.cost_usd = self._estimate_cost(model_id, usage.prompt_tokens, usage.completion_tokens)

        if response_model:
            return response_model.model_validate_json(content), usage
        return content, usage

    # ── OpenAI ───────────────────────────────────────────────────

    def _call_openai(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
        response_model: Type[BaseModel] | None,
    ) -> tuple[str | BaseModel, TokenUsage]:
        if not self._openai:
            raise RuntimeError("OpenAI client not initialized (missing API key)")

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_model:
            kwargs["response_format"] = {"type": "json_object"}
            schema_hint = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
            kwargs["messages"] = [
                {"role": "system", "content": f"Respond in JSON matching this schema:\n{schema_hint}"},
                *messages,
            ]

        response = self._openai.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""

        usage = TokenUsage(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            model=model,
        )
        usage.cost_usd = self._estimate_cost(model, usage.prompt_tokens, usage.completion_tokens)

        if response_model:
            return response_model.model_validate_json(content), usage
        return content, usage

    # ── Anthropic Direct ─────────────────────────────────────────

    def _call_anthropic(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
        response_model: Type[BaseModel] | None,
    ) -> tuple[str | BaseModel, TokenUsage]:
        if not self._anthropic:
            raise RuntimeError("Anthropic client not initialized (missing API key)")

        system_parts = []
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                chat_messages.append(msg)

        if response_model:
            schema_hint = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
            system_parts.append(f"Respond in JSON matching this schema:\n{schema_hint}")

        system = "\n\n".join(system_parts) if system_parts else ""

        response = self._anthropic.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=chat_messages,
        )
        content = response.content[0].text

        usage = TokenUsage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            model=model,
        )
        usage.cost_usd = self._estimate_cost(model, usage.prompt_tokens, usage.completion_tokens)

        if response_model:
            return response_model.model_validate_json(content), usage
        return content, usage

    # ── Helpers ───────────────────────────────────────────────────

    def get_total_cost(self) -> float:
        """Get total cost across all LLM calls."""
        return sum(u.cost_usd for u in self.total_usage)

    def get_usage_summary(self) -> dict:
        """Get usage summary by model."""
        summary: dict[str, dict] = {}
        for u in self.total_usage:
            if u.model not in summary:
                summary[u.model] = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
            summary[u.model]["calls"] += 1
            summary[u.model]["prompt_tokens"] += u.prompt_tokens
            summary[u.model]["completion_tokens"] += u.completion_tokens
            summary[u.model]["cost"] += u.cost_usd
        return summary
