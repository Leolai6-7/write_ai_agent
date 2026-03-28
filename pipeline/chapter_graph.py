"""LangGraph StateGraph for single chapter generation pipeline.

Flow: assemble_context → generate → judge → (rewrite loop) → consistency_check → summarize → update_memory
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import StateGraph, END

from config.models import (
    ChapterObjective,
    ChapterSummary,
    ChapterContext,
    JudgementResult,
    ConsistencyReport,
)
from agents.chapter_generator import ChapterGeneratorAgent
from agents.judge_agent import JudgeAgent
from agents.rewrite_agent import RewriteAgent
from agents.summarizer import SummarizerAgent
from memory.memory_manager import MemoryManager


class ChapterState(TypedDict):
    """State for the chapter generation graph."""
    chapter_objective: ChapterObjective
    context: ChapterContext | None
    draft: str
    judgement: JudgementResult | None
    rewrite_count: int
    final_chapter: str
    summary: ChapterSummary | None
    consistency: ConsistencyReport | None


# ── Conditional Edges ────────────────────────────────────────────

def should_rewrite(state: ChapterState) -> str:
    """Decide whether to rewrite based on judge score."""
    judgement = state["judgement"]
    if judgement and judgement.pass_threshold:
        return "check_consistency"
    if state["rewrite_count"] >= 2:
        return "force_accept"
    return "rewrite"


def should_fix_consistency(state: ChapterState) -> str:
    """Decide whether to fix consistency issues."""
    consistency = state.get("consistency")
    if consistency and consistency.is_consistent:
        return "summarize"
    return "rewrite_consistency"


# ── Graph Builder ────────────────────────────────────────────────

class ChapterGraphBuilder:
    """Builds the LangGraph StateGraph with injected agent dependencies."""

    def __init__(
        self,
        generator: ChapterGeneratorAgent,
        judge: JudgeAgent,
        rewriter: RewriteAgent,
        summarizer: SummarizerAgent,
        memory: MemoryManager,
    ):
        self.generator = generator
        self.judge = judge
        self.rewriter = rewriter
        self.summarizer = summarizer
        self.memory = memory

    def build(self) -> StateGraph:
        """Build the compiled graph with real agent implementations."""
        graph = StateGraph(ChapterState)

        # Add nodes with closures that capture agent references
        graph.add_node("assemble_context", self._assemble_context)
        graph.add_node("generate", self._generate)
        graph.add_node("judge", self._judge)
        graph.add_node("rewrite", self._rewrite)
        graph.add_node("force_accept", _force_accept)
        graph.add_node("check_consistency", self._check_consistency)
        graph.add_node("rewrite_consistency", self._rewrite_consistency)
        graph.add_node("summarize", self._summarize)
        graph.add_node("update_memory", self._update_memory)

        # Set entry point
        graph.set_entry_point("assemble_context")

        # Add edges
        graph.add_edge("assemble_context", "generate")
        graph.add_edge("generate", "judge")
        graph.add_conditional_edges("judge", should_rewrite, {
            "check_consistency": "check_consistency",
            "force_accept": "force_accept",
            "rewrite": "rewrite",
        })
        graph.add_edge("rewrite", "judge")
        graph.add_edge("force_accept", "update_memory")
        graph.add_conditional_edges("check_consistency", should_fix_consistency, {
            "summarize": "summarize",
            "rewrite_consistency": "rewrite_consistency",
        })
        graph.add_edge("rewrite_consistency", "judge")
        graph.add_edge("summarize", "update_memory")
        graph.add_edge("update_memory", END)

        return graph

    # ── Node implementations ─────────────────────────────────────

    def _assemble_context(self, state: ChapterState) -> dict:
        context = self.memory.assemble_context(state["chapter_objective"])
        return {"context": context}

    def _generate(self, state: ChapterState) -> dict:
        draft = self.generator.run(
            objective=state["chapter_objective"],
            context=state["context"],
        )
        return {"draft": draft}

    def _judge(self, state: ChapterState) -> dict:
        # Get previous chapter summary for context
        prev_id = state["chapter_objective"].chapter_id - 1
        prev_summary = ""
        if prev_id > 0:
            row = self.memory.db.conn.execute(
                "SELECT one_line_summary FROM chapter_summaries WHERE chapter_id = ?",
                (prev_id,),
            ).fetchone()
            if row:
                prev_summary = row["one_line_summary"]

        judgement = self.judge.run(
            chapter_text=state["draft"],
            objective=state["chapter_objective"],
            previous_summary=prev_summary,
        )
        return {"judgement": judgement}

    def _rewrite(self, state: ChapterState) -> dict:
        rewritten = self.rewriter.run(
            chapter_text=state["draft"],
            judgement=state["judgement"],
        )
        return {
            "draft": rewritten,
            "rewrite_count": state["rewrite_count"] + 1,
        }

    def _check_consistency(self, state: ChapterState) -> dict:
        # Phase 3: ConsistencyChecker.run()
        # For now, pass through
        return {
            "final_chapter": state["draft"],
            "consistency": ConsistencyReport(is_consistent=True),
        }

    def _rewrite_consistency(self, state: ChapterState) -> dict:
        rewritten = self.rewriter.run(
            chapter_text=state["draft"],
            consistency=state["consistency"],
        )
        return {"draft": rewritten}

    def _summarize(self, state: ChapterState) -> dict:
        summary = self.summarizer.run(
            chapter_id=state["chapter_objective"].chapter_id,
            chapter_text=state["final_chapter"],
        )
        return {"summary": summary}

    def _update_memory(self, state: ChapterState) -> dict:
        if state.get("summary"):
            self.memory.save_summary(state["summary"])
        elif state.get("final_chapter"):
            # Force-accepted without summary — still save the chapter
            self.memory.save_summary(ChapterSummary(
                chapter_id=state["chapter_objective"].chapter_id,
                plot_events=["(force accepted, no summary)"],
                character_changes={},
                world_state_changes=[],
                unresolved_threads=[],
                emotional_arc="unknown",
                one_line_summary="(force accepted)",
            ))
        return {}


# ── Standalone builder for testing ──────────────────────────────

def build_chapter_graph() -> StateGraph:
    """Build a placeholder graph for testing (no real agents)."""
    graph = StateGraph(ChapterState)

    graph.add_node("assemble_context", lambda s: {"context": ChapterContext(
        short_term_memory="", long_term_memory="",
        character_context="", world_context="",
    )})
    graph.add_node("generate", lambda s: {
        "draft": f"[Draft for chapter {s['chapter_objective'].chapter_id}]"
    })
    graph.add_node("judge", lambda s: {"judgement": JudgementResult(
        overall_score=8.0, plot_progression=8.0, character_consistency=8.0,
        writing_quality=7.5, pacing=8.0, objective_alignment=8.5,
        pass_threshold=True, issues=[], rewrite_suggestions=[],
    )})
    graph.add_node("rewrite", lambda s: {
        "draft": f"[Rewritten v{s['rewrite_count'] + 1}]",
        "rewrite_count": s["rewrite_count"] + 1,
    })
    graph.add_node("force_accept", _force_accept)
    graph.add_node("check_consistency", lambda s: {
        "final_chapter": s["draft"],
        "consistency": ConsistencyReport(is_consistent=True),
    })
    graph.add_node("rewrite_consistency", lambda s: {"draft": "[Consistency-fixed]"})
    graph.add_node("summarize", lambda s: {"summary": ChapterSummary(
        chapter_id=s["chapter_objective"].chapter_id,
        plot_events=["placeholder"], character_changes={},
        world_state_changes=[], unresolved_threads=[],
        emotional_arc=s["chapter_objective"].emotional_tone,
        one_line_summary=f"Chapter {s['chapter_objective'].chapter_id} summary",
    )})
    graph.add_node("update_memory", lambda s: {})

    graph.set_entry_point("assemble_context")
    graph.add_edge("assemble_context", "generate")
    graph.add_edge("generate", "judge")
    graph.add_conditional_edges("judge", should_rewrite, {
        "check_consistency": "check_consistency",
        "force_accept": "force_accept",
        "rewrite": "rewrite",
    })
    graph.add_edge("rewrite", "judge")
    graph.add_edge("force_accept", "update_memory")
    graph.add_conditional_edges("check_consistency", should_fix_consistency, {
        "summarize": "summarize",
        "rewrite_consistency": "rewrite_consistency",
    })
    graph.add_edge("rewrite_consistency", "judge")
    graph.add_edge("summarize", "update_memory")
    graph.add_edge("update_memory", END)

    return graph


def _force_accept(state: ChapterState) -> dict:
    return {"final_chapter": state["draft"]}
