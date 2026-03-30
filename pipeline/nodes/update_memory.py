"""Node: update memory stores after chapter completion."""

from __future__ import annotations

from config.models import ChapterSummary
from infrastructure.logger import get_logger
from memory.memory_manager import MemoryManager

logger = get_logger("node.update_memory")


class UpdateMemoryNode:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    def __call__(self, state):
        summary = state.get("summary")
        if not summary and state.get("final_chapter"):
            summary = ChapterSummary(
                chapter_id=state["chapter_objective"].chapter_id,
                plot_events=["(force accepted, no summary)"],
                character_changes={},
                world_state_changes=[],
                unresolved_threads=[],
                emotional_arc="unknown",
                one_line_summary="(force accepted)",
            )

        if summary:
            self.memory.save_summary(summary)

            # Auto-update character states
            chapter_id = state["chapter_objective"].chapter_id
            for char_name, change_desc in summary.character_changes.items():
                try:
                    self.memory.update_character(char_name, change_desc, chapter_id)
                except Exception as e:
                    logger.warning("Failed to update character %s: %s", char_name, e)

        return {}
