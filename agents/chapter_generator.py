"""Chapter generation agent - produces novel chapter drafts."""

from __future__ import annotations

from config.models import ChapterObjective, ChapterContext
from agents.base_agent import BaseAgent


class ChapterGeneratorAgent(BaseAgent):
    """Generates a chapter draft based on objective and memory context."""

    def run(
        self,
        objective: ChapterObjective,
        context: ChapterContext,
    ) -> str:
        """Generate a chapter draft (3000-5000 Chinese characters)."""
        # Build context block from memory layers
        context_parts = []
        if context.short_term_memory:
            context_parts.append(context.short_term_memory)
        if context.long_term_memory:
            context_parts.append(context.long_term_memory)
        if context.character_context:
            context_parts.append(context.character_context)
        if context.world_context:
            context_parts.append(context.world_context)
        context_block = "\n\n".join(context_parts)

        events = "、".join(objective.key_events) if objective.key_events else "無特定事件"
        characters = "、".join(objective.characters_involved) if objective.characters_involved else "無"

        messages = self.prompt.render(
            context_block=context_block,
            chapter_id=objective.chapter_id,
            title=objective.title,
            objective=objective.objective,
            key_events=events,
            characters=characters,
            emotional_tone=objective.emotional_tone,
        )

        return self.call_llm(messages, temperature=0.8, max_tokens=6000)
