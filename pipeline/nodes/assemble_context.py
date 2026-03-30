"""Node: assemble context from memory layers."""

from __future__ import annotations

from config.models import ChapterContext
from infrastructure.errors import node_handler
from memory.memory_manager import MemoryManager


class AssembleContextNode:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    @node_handler(fallback={"context": ChapterContext(
        short_term_memory="", long_term_memory="",
        character_context="", world_context="",
    )})
    def __call__(self, state):
        context = self.memory.assemble_context(state["chapter_objective"])
        return {"context": context}
