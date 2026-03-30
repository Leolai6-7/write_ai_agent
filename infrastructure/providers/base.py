"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Type

from pydantic import BaseModel


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    def call(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        response_model: Type[BaseModel] | None,
    ) -> tuple[str | BaseModel, "TokenUsage"]:
        """Execute an LLM call and return (result, usage)."""
        ...

    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model identifier."""
        ...
