"""Node: pacing advisor - recommends rhythm before chapter generation."""

from __future__ import annotations

from infrastructure.logger import get_logger
from agents.pacing_advisor import PacingAdvisor
from memory.memory_manager import MemoryManager

logger = get_logger("node.pacing")


class PacingAdvisorNode:
    def __init__(self, advisor: PacingAdvisor, memory: MemoryManager):
        self.advisor = advisor
        self.memory = memory

    def __call__(self, state):
        # Get recent emotional arcs from memory
        recent = self.memory.summaries.get_recent(
            state["chapter_objective"].chapter_id, limit=5
        )
        recent_arcs = [r["emotional_arc"] for r in recent]

        try:
            advice = self.advisor.run(recent_arcs, state["chapter_objective"])

            # Inject into context
            context = state.get("context")
            if context:
                advice_text = (
                    f"## 節奏建議\n"
                    f"節奏：{advice.suggested_pace}\n"
                    f"場景類型：{'、'.join(advice.scene_types)}\n"
                    f"避免：{'、'.join(advice.avoid)}\n"
                    f"目標字數：{advice.chapter_length_target}"
                )
                context.pacing_advice = advice_text

            return {"context": context}
        except Exception as e:
            logger.warning("Pacing advisor failed, skipping: %s", e)
            return {}
