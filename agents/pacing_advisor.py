"""Pacing advisor - recommends rhythm and scene types for each chapter."""

from __future__ import annotations

from config.models import PacingAdvice, ChapterObjective
from agents.base_agent import BaseAgent


class PacingAdvisor(BaseAgent):
    """Analyzes recent chapter patterns and advises on pacing for the next chapter."""

    def run(
        self,
        recent_emotional_arcs: list[str],
        objective: ChapterObjective,
    ) -> PacingAdvice:
        """Generate pacing advice for the next chapter.

        Args:
            recent_emotional_arcs: Emotional arcs of recent 5 chapters.
            objective: Current chapter's objective.

        Returns:
            PacingAdvice with pace, scene types, avoidances.
        """
        recent = "\n".join(
            f"- 第{i+1}章前: {arc}" for i, arc in enumerate(recent_emotional_arcs)
        ) if recent_emotional_arcs else "（第一章，無前置章節）"

        messages = self.prompt.render(
            recent_arcs=recent,
            chapter_objective=objective.objective,
            emotional_tone=objective.emotional_tone,
        )

        result = self.call_llm(
            messages, response_model=PacingAdvice,
            temperature=0.3, max_tokens=500,
        )
        self.logger.info(
            "Pacing advice for ch%d: %s, types=%s",
            objective.chapter_id, result.suggested_pace, result.scene_types,
        )
        return result
