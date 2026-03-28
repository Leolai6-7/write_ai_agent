"""Base agent class for all novel writing agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel

from infrastructure.llm_client import LLMClient
from infrastructure.logger import get_logger


class BaseAgent(ABC):
    """Base class providing unified LLM access for all agents."""

    def __init__(
        self,
        llm: LLMClient,
        model: str,
        name: str | None = None,
    ):
        self.llm = llm
        self.model = model
        self.name = name or self.__class__.__name__
        self.logger = get_logger(self.name)

    def call_llm(
        self,
        messages: list[dict[str, str]],
        response_model: Type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str | BaseModel:
        """Call LLM with automatic retry, logging, and optional structured output."""
        self.logger.info("Calling LLM (model=%s, structured=%s)", self.model, response_model is not None)
        result = self.llm.chat(
            messages=messages,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_model=response_model,
        )
        self.logger.info("LLM call completed")
        return result

    @abstractmethod
    def run(self, **kwargs) -> Any:
        """Execute the agent's main task."""
        ...
