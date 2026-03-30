"""Unified error types and node error handling decorator."""

from __future__ import annotations

import functools
from typing import Callable

from infrastructure.logger import get_logger

logger = get_logger("errors")


class AgentError(Exception):
    """Agent execution failed (retryable)."""
    pass


class FatalError(Exception):
    """Unrecoverable error (stops pipeline)."""
    pass


def node_handler(fallback: dict | None = None):
    """Decorator for LangGraph node functions with consistent error handling.

    Args:
        fallback: If provided, return this dict on non-fatal errors instead of raising.
                  If None, errors propagate.
    """
    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except FatalError:
                raise  # Never catch fatal errors
            except Exception as e:
                node_name = fn.__name__.lstrip("_")
                if fallback is not None:
                    logger.error("Node '%s' failed, using fallback: %s", node_name, e)
                    return fallback
                logger.error("Node '%s' failed: %s", node_name, e)
                raise AgentError(f"Node '{node_name}' failed: {e}") from e
        return wrapper
    return decorator
