"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Type

from pydantic import BaseModel

if TYPE_CHECKING:
    from infrastructure.llm_client import TokenUsage


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
