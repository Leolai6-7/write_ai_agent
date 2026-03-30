"""Shared test fixtures and mock LLM client."""

from __future__ import annotations

import json
from typing import Type
from pathlib import Path

import pytest
from pydantic import BaseModel

from config.models import ChapterObjective
from infrastructure.llm_client import LLMClient, TokenUsage
from prompts.loader import PromptTemplate


class MockLLMClient(LLMClient):
    """Mock LLM client that returns predefined responses without API calls."""

    def __init__(self, responses: dict[str, str | dict] | None = None):
        # Don't initialize real API clients
        self._openai = None
        self._anthropic = None
        self.total_usage: list[TokenUsage] = []
        self._responses = responses or {}
        self._call_log: list[dict] = []

    def count_tokens(self, text: str) -> int:
        return len(text) // 4  # Rough approximation

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str = "mock",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        response_model: Type[BaseModel] | None = None,
        max_retries: int = 3,
        retry_delay: float = 0.0,
    ) -> str | BaseModel:
        self._call_log.append({
            "messages": messages,
            "model": model,
            "response_model": response_model,
        })

        usage = TokenUsage(prompt_tokens=100, completion_tokens=200, model=model, cost_usd=0.001)
        self.total_usage.append(usage)

        # Find matching response
        for key, value in self._responses.items():
            if key in str(messages):
                if response_model and isinstance(value, dict):
                    return response_model.model_validate(value)
                return str(value)

        # Default response
        if response_model:
            # Generate a minimal valid instance
            return self._default_response(response_model)
        return "Mock LLM response"

    def _default_response(self, model_class: Type[BaseModel]) -> BaseModel:
        """Generate a minimal valid Pydantic model instance."""
        schema = model_class.model_json_schema()
        data = self._generate_from_schema(schema)
        return model_class.model_validate(data)

    def _generate_from_schema(self, schema: dict) -> dict | list | str | int | float | bool:
        if schema.get("type") == "object":
            result = {}
            for name, prop in schema.get("properties", {}).items():
                result[name] = self._generate_from_schema(prop)
            return result
        elif schema.get("type") == "array":
            return []
        elif schema.get("type") == "string":
            return "mock"
        elif schema.get("type") == "integer":
            return 1
        elif schema.get("type") == "number":
            return 7.5
        elif schema.get("type") == "boolean":
            return True
        return "mock"


@pytest.fixture
def mock_llm():
    """Provide a mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def sample_objective():
    """Provide a sample chapter objective."""
    return ChapterObjective(
        chapter_id=1,
        title="初入圖書館",
        objective="主角到達古老圖書館，初遇守護者米娜",
        key_events=["到達圖書館", "遇見米娜", "發現父親的線索"],
        characters_involved=["伊澤", "米娜"],
        emotional_tone="期待與不安",
    )


@pytest.fixture
def mock_prompt():
    """Provide a simple mock prompt template."""
    return PromptTemplate(
        system="You are a test agent.",
        user="Do the task: {task}",
    )


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path."""
    return tmp_path / "test_novel.db"
