"""Summarizer agent - generates structured chapter summaries."""

from __future__ import annotations

from config.models import ChapterSummary
from agents.base_agent import BaseAgent


class SummarizerAgent(BaseAgent):
    """Generates structured chapter summaries for memory management."""

    def run(self, chapter_id: int, chapter_text: str) -> ChapterSummary:
        """Generate a structured summary of a chapter."""
        messages = self.prompt.render(
            chapter_id=chapter_id,
            chapter_text=chapter_text,
        )
        result = self.call_llm(messages, response_model=ChapterSummary, temperature=0.3, max_tokens=1500)
        result.chapter_id = chapter_id
        self.logger.info("Summarized chapter %d: %s", chapter_id, result.one_line_summary)
        return result
