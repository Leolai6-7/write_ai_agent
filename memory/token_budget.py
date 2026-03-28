"""Token budget management for context assembly."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TokenBudget:
    """Manages token allocation across memory layers."""
    total: int = 6000
    short_term: int = 2000
    long_term: int = 1000
    character: int = 1000
    world: int = 500
    instruction: int = 1500

    _used: dict[str, int] = field(default_factory=dict)

    def remaining(self, category: str) -> int:
        budget = getattr(self, category, 0)
        return budget - self._used.get(category, 0)

    def use(self, category: str, tokens: int) -> None:
        self._used[category] = self._used.get(category, 0) + tokens

    def total_used(self) -> int:
        return sum(self._used.values())

    def total_remaining(self) -> int:
        return self.total - self.total_used()

    def truncate_text(self, text: str, category: str, count_fn) -> str:
        """Truncate text to fit within category budget."""
        budget = self.remaining(category)
        if budget <= 0:
            return ""

        tokens = count_fn(text)
        if tokens <= budget:
            self.use(category, tokens)
            return text

        # Binary search for the right truncation point
        ratio = budget / tokens
        end = int(len(text) * ratio * 0.9)  # 90% to be safe
        truncated = text[:end] + "\n...(truncated)"
        actual = count_fn(truncated)
        self.use(category, actual)
        return truncated

    def reset(self) -> None:
        self._used.clear()
