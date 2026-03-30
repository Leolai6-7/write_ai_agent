"""Node: generate chapter draft (with optional dual-draft mode)."""

from __future__ import annotations

from infrastructure.logger import get_logger
from agents.chapter_generator import ChapterGeneratorAgent
from agents.judge_agent import JudgeAgent

logger = get_logger("node.generate")


class GenerateNode:
    def __init__(self, generator: ChapterGeneratorAgent, judge: JudgeAgent, dual_draft: bool = False):
        self.generator = generator
        self.judge = judge
        self.dual_draft = dual_draft

    def __call__(self, state):
        draft_a = self.generator.run(
            objective=state["chapter_objective"],
            context=state["context"],
        )

        if self.dual_draft:
            try:
                draft_b = self.generator.run(
                    objective=state["chapter_objective"],
                    context=state["context"],
                )
                draft = self.judge.compare(draft_a, draft_b, state["chapter_objective"])
                logger.info("Dual draft: selected best of 2 drafts")
                return {"draft": draft}
            except Exception as e:
                logger.warning("Dual draft failed, using first draft: %s", e)

        return {"draft": draft_a}
