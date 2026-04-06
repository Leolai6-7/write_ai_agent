"""Node: judge chapter quality."""

from __future__ import annotations

from infrastructure.errors import node_handler
from agents.judge_agent import JudgeAgent
from memory.memory_manager import MemoryManager


class JudgeNode:
    def __init__(self, judge: JudgeAgent, memory: MemoryManager):
        self.judge = judge
        self.memory = memory

    @node_handler(fallback=None)  # No silent auto-pass — let it propagate
    def __call__(self, state):
        prev_summary = self.memory.get_previous_summary(
            state["chapter_objective"].chapter_id
        )
        judgement = self.judge.run(
            chapter_text=state["draft"],
            objective=state["chapter_objective"],
            previous_summary=prev_summary,
        )
        return {"judgement": judgement}
