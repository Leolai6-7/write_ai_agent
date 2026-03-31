"""Story bible keeper - actively updates story bible after each chapter."""

from __future__ import annotations

from config.models import StoryBibleUpdate, ChapterSummary
from agents.base_agent import BaseAgent


class StoryBibleKeeper(BaseAgent):
    """Analyzes chapter content and generates update instructions for the story bible."""

    def run(
        self,
        chapter_summary: ChapterSummary,
        chapter_ending: str,
        character_states: str,
    ) -> StoryBibleUpdate:
        """Analyze chapter and determine what story elements need updating.

        Args:
            chapter_summary: Structured summary from SummarizerAgent.
            chapter_ending: Last ~500 chars of chapter text.
            character_states: Current character states as formatted string.

        Returns:
            StoryBibleUpdate with update instructions.
        """
        summary_text = (
            f"第{chapter_summary.chapter_id}章：{chapter_summary.one_line_summary}\n"
            f"事件：{'、'.join(chapter_summary.plot_events)}\n"
            f"角色變化：{chapter_summary.character_changes}\n"
            f"世界變化：{'、'.join(chapter_summary.world_state_changes)}"
        )

        messages = self.prompt.render(
            chapter_summary=summary_text,
            chapter_ending=chapter_ending[-500:] if len(chapter_ending) > 500 else chapter_ending,
            character_states=character_states,
        )

        result = self.call_llm(
            messages, response_model=StoryBibleUpdate,
            temperature=0.3, max_tokens=1500,
        )
        self.logger.info(
            "Bible update: %d char updates, %d world changes, %d relationship changes",
            len(result.character_updates),
            len(result.world_changes),
            len(result.relationship_changes),
        )
        return result
