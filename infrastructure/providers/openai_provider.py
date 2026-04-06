"""OpenAI provider."""

from __future__ import annotations

import json
from typing import Any


from infrastructure.providers.base import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)

    def supports_model(self, model: str) -> bool:
        return model.startswith("gpt") or model.startswith("o1") or model.startswith("o3")

    def call(self, messages, model, temperature, max_tokens, response_model):
        from infrastructure.llm_client import TokenUsage

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

        response = self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""

        usage = TokenUsage(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            model=model,
        )

        if response_model:
            from infrastructure.llm_client import LLMClient
            return response_model.model_validate_json(LLMClient._strip_code_fence(content)), usage
        return content, usage
