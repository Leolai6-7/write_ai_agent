"""LangGraph StateGraph for single chapter generation pipeline.

Flow: assemble_context → generate → judge → (rewrite loop) → consistency → summarize → update_memory

This module only handles graph wiring. Node implementations are in pipeline/nodes/.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import StateGraph, END

from config.models import (
    ChapterObjective, ChapterSummary, ChapterContext,
    JudgementResult, ConsistencyReport,
)


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
    judgement = state["judgement"]
    if judgement and judgement.pass_threshold:
        return "check_consistency"
    if state["rewrite_count"] >= 2:
        return "force_accept"
    return "rewrite"


def should_fix_consistency(state: ChapterState) -> str:
    consistency = state.get("consistency")
    if consistency and consistency.is_consistent:
        return "summarize"
    return "rewrite_consistency"


def _force_accept(state: ChapterState) -> dict:
    return {"final_chapter": state["draft"]}


# ── Graph Builder ────────────────────────────────────────────────

class ChapterGraphBuilder:
    """Builds the LangGraph StateGraph from injected node callables."""

    def __init__(self, nodes: dict[str, callable]):
        self.nodes = nodes

    def build(self) -> StateGraph:
        graph = StateGraph(ChapterState)

        # Add all nodes
        for name, node in self.nodes.items():
            graph.add_node(name, node)
        graph.add_node("force_accept", _force_accept)

        # Wire edges
        graph.set_entry_point("assemble_context")

        # Pacing advisor is optional — skip if not in nodes
        if "pacing_advisor" in self.nodes:
            graph.add_edge("assemble_context", "pacing_advisor")
            graph.add_edge("pacing_advisor", "generate")
        else:
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

        # Story bible keeper is optional — between summarize and update_memory
        if "story_bible_keeper" in self.nodes:
            graph.add_edge("summarize", "story_bible_keeper")
            graph.add_edge("story_bible_keeper", "update_memory")
        else:
            graph.add_edge("summarize", "update_memory")

        graph.add_edge("update_memory", END)

        return graph


# ── Test helper ──────────────────────────────────────────────────

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
