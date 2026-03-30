"""Node: check chapter consistency."""

from __future__ import annotations

from config.models import ConsistencyReport
from infrastructure.errors import node_handler
from agents.consistency_checker import ConsistencyChecker


class ConsistencyNode:
    def __init__(self, checker: ConsistencyChecker | None = None):
        self.checker = checker

    @node_handler(fallback={
        "final_chapter": "",  # Will be filled from state["draft"] below
        "consistency": ConsistencyReport(is_consistent=True, warnings=["Check skipped"]),
    })
    def __call__(self, state):
        if not self.checker:
            return {
                "final_chapter": state["draft"],
                "consistency": ConsistencyReport(is_consistent=True),
            }

        context = state.get("context")
        report = self.checker.run(
            chapter_text=state["draft"],
            chapter_id=state["chapter_objective"].chapter_id,
            character_context=context.character_context if context else "",
            relevant_history=context.short_term_memory if context else "",
        )
        return {"final_chapter": state["draft"], "consistency": report}
