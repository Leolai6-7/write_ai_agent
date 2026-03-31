"""Node: story bible keeper - updates story bible after summarization."""

from __future__ import annotations

from infrastructure.logger import get_logger
from agents.story_bible_keeper import StoryBibleKeeper
from memory.memory_manager import MemoryManager
from memory.repositories.world_repo import WorldRepository

logger = get_logger("node.story_bible")


class StoryBibleKeeperNode:
    def __init__(
        self,
        keeper: StoryBibleKeeper,
        memory: MemoryManager,
        world_repo: WorldRepository | None = None,
    ):
        self.keeper = keeper
        self.memory = memory
        self.world_repo = world_repo

    def __call__(self, state):
        summary = state.get("summary")
        final_chapter = state.get("final_chapter", "")

        if not summary:
            return {}

        try:
            # Get current character states for context
            chars = state["chapter_objective"].characters_involved
            char_states = self.memory.characters.get_many(chars)
            char_text = "\n".join(
                f"【{s.name}】{s.emotional_state} | 位置:{s.current_location}"
                for s in char_states
            ) if char_states else "（無角色資料）"

            update = self.keeper.run(
                chapter_summary=summary,
                chapter_ending=final_chapter,
                character_states=char_text,
            )

            # Apply world changes
            if self.world_repo:
                chapter_id = state["chapter_objective"].chapter_id
                for change in update.world_changes:
                    self.world_repo.add_event(change, chapter_id)

            # Apply character updates
            for char_name, change in update.character_updates.items():
                try:
                    self.memory.update_character(
                        char_name, change, state["chapter_objective"].chapter_id
                    )
                except Exception as e:
                    logger.warning("Failed to update character %s: %s", char_name, e)

            logger.info(
                "Story bible updated: %d char, %d world, %d relationship changes",
                len(update.character_updates),
                len(update.world_changes),
                len(update.relationship_changes),
            )
        except Exception as e:
            logger.warning("Story bible keeper failed, skipping: %s", e)

        return {}
