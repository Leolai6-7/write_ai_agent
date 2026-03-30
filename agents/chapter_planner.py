"""Chapter planner agent - generates per-chapter objectives for an arc."""

from __future__ import annotations

from pydantic import BaseModel, Field

from config.models import ArcSpec, ChapterObjective
from agents.base_agent import BaseAgent


class ChapterPlanResult(BaseModel):
    """Wrapper for chapter planning output."""
    chapters: list[ChapterObjective] = Field(min_length=1)


class ChapterPlannerAgent(BaseAgent):
    """Plans detailed chapter objectives within an arc."""

    def run(
        self,
        arc: ArcSpec,
        memory_context: str = "",
    ) -> list[ChapterObjective]:
        """Generate per-chapter objectives for an arc."""
        total_chapters = arc.end_chapter - arc.start_chapter + 1
        context_block = f"\n## 故事上下文\n{memory_context}" if memory_context else ""

        messages = self.prompt.render(
            arc_name=arc.arc_name,
            start_chapter=arc.start_chapter,
            end_chapter=arc.end_chapter,
            total_chapters=total_chapters,
            core_objective=arc.core_objective,
            main_conflict=arc.main_conflict,
            ending_twist=arc.ending_twist,
            key_characters="、".join(arc.key_characters),
            memory_context_block=context_block,
        )
        result = self.call_llm(messages, response_model=ChapterPlanResult, temperature=0.7, max_tokens=4000)
        self.logger.info("Planned %d chapters for arc: %s", len(result.chapters), arc.arc_name)
        return result.chapters
