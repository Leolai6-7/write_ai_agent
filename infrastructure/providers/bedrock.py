"""AWS Bedrock provider using the Converse API."""

from __future__ import annotations

import json
from typing import Any


from infrastructure.providers.base import LLMProvider


class BedrockProvider(LLMProvider):
    """AWS Bedrock provider with prompt caching support."""

    def __init__(self, aws_region: str = "us-west-2", aws_profile: str | None = None):
        self._region = aws_region
        self._profile = aws_profile
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            session_kwargs = {}
            if self._profile:
                session_kwargs["profile_name"] = self._profile
            session = boto3.Session(**session_kwargs)
            self._client = session.client("bedrock-runtime", region_name=self._region)
        return self._client

    def supports_model(self, model: str) -> bool:
        return model.startswith("bedrock:") or "anthropic" in model.lower()

    def call(self, messages, model, temperature, max_tokens, response_model):
        from infrastructure.llm_client import TokenUsage

        model_id = model.removeprefix("bedrock:")

        # Extract system messages
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

        # Prompt caching
        if system_parts:
            system_parts.append({"cachePoint": {"type": "default"}})

        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": chat_messages,
            "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
        }
        if system_parts:
            kwargs["system"] = system_parts

        response = self.client.converse(**kwargs)

        content = response["output"]["message"]["content"][0]["text"]
        token_usage = response.get("usage", {})

        usage = TokenUsage(
            prompt_tokens=token_usage.get("inputTokens", 0),
            completion_tokens=token_usage.get("outputTokens", 0),
            model=model_id,
        )

        if response_model:
            from infrastructure.llm_client import LLMClient
            return response_model.model_validate_json(LLMClient._strip_code_fence(content)), usage
        return content, usage
