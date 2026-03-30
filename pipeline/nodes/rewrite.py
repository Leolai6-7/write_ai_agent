"""Node: rewrite chapter based on feedback."""

from __future__ import annotations

from infrastructure.errors import node_handler
from infrastructure.logger import get_logger
from agents.rewrite_agent import RewriteAgent

logger = get_logger("node.rewrite")


class RewriteNode:
    def __init__(self, rewriter: RewriteAgent):
        self.rewriter = rewriter

    @node_handler()  # Propagate errors — rewrite failure is significant
    def __call__(self, state):
        rewritten = self.rewriter.run(
            chapter_text=state["draft"],
            judgement=state.get("judgement"),
        )
        return {"draft": rewritten, "rewrite_count": state["rewrite_count"] + 1}


class RewriteConsistencyNode:
    def __init__(self, rewriter: RewriteAgent):
        self.rewriter = rewriter

    @node_handler()
    def __call__(self, state):
        rewritten = self.rewriter.run(
            chapter_text=state["draft"],
            consistency=state.get("consistency"),
        )
        return {"draft": rewritten}
