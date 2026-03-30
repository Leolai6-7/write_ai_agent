"""Anthropic direct API provider."""

from __future__ import annotations

import json
from typing import Type

from pydantic import BaseModel

from infrastructure.providers.base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic direct API provider."""

    def __init__(self, api_key: str):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)

    def supports_model(self, model: str) -> bool:
        return "claude" in model.lower() and not model.startswith("bedrock:")

    def call(self, messages, model, temperature, max_tokens, response_model):
        from infrastructure.llm_client import TokenUsage

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

        response = self._client.messages.create(
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

        if response_model:
            from infrastructure.llm_client import LLMClient
            return response_model.model_validate_json(LLMClient._strip_code_fence(content)), usage
        return content, usage
