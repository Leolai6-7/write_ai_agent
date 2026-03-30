"""Node: generate structured chapter summary."""

from __future__ import annotations

from infrastructure.errors import node_handler
from agents.summarizer import SummarizerAgent


class SummarizeNode:
    def __init__(self, summarizer: SummarizerAgent):
        self.summarizer = summarizer

    @node_handler()
    def __call__(self, state):
        summary = self.summarizer.run(
            chapter_id=state["chapter_objective"].chapter_id,
            chapter_text=state["final_chapter"],
        )
        return {"summary": summary}
