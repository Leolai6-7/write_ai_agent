"""Tests for the LangGraph chapter generation pipeline."""

from config.models import ChapterObjective
from pipeline.chapter_graph import build_chapter_graph, ChapterState


def test_graph_builds_successfully():
    """Graph should compile without errors."""
    graph = build_chapter_graph()
    compiled = graph.compile()
    assert compiled is not None


def test_graph_happy_path(sample_objective):
    """Graph should complete successfully with passing judgement."""
    graph = build_chapter_graph()
    compiled = graph.compile()

    initial_state: ChapterState = {
        "chapter_objective": sample_objective,
        "context": None,
        "draft": "",
        "judgement": None,
        "rewrite_count": 0,
        "final_chapter": "",
        "summary": None,
        "consistency": None,
    }

    result = compiled.invoke(initial_state)

    assert result["final_chapter"] != ""
    assert result["summary"] is not None
    assert result["summary"].chapter_id == sample_objective.chapter_id
    assert result["rewrite_count"] == 0  # No rewrites needed


def test_graph_nodes_exist():
    """All expected nodes should be present in the graph."""
    graph = build_chapter_graph()
    expected_nodes = [
        "assemble_context", "generate", "judge", "rewrite",
        "force_accept", "check_consistency", "rewrite_consistency",
        "summarize", "update_memory",
    ]
    for node in expected_nodes:
        assert node in graph.nodes


def test_should_rewrite_logic():
    """Test conditional edge logic for judge -> rewrite decision."""
    from pipeline.chapter_graph import should_rewrite
    from config.models import JudgementResult

    # Pass case
    state_pass: ChapterState = {
        "chapter_objective": ChapterObjective(
            chapter_id=1, title="t", objective="o",
            key_events=[], characters_involved=[], emotional_tone="",
        ),
        "context": None, "draft": "", "final_chapter": "",
        "summary": None, "consistency": None,
        "judgement": JudgementResult(
            overall_score=8.0, plot_progression=8.0, character_consistency=8.0,
            writing_quality=8.0, pacing=8.0, objective_alignment=8.0,
            pass_threshold=True, issues=[], rewrite_suggestions=[],
        ),
        "rewrite_count": 0,
    }
    assert should_rewrite(state_pass) == "check_consistency"

    # Fail case - should rewrite
    state_fail = {**state_pass}
    state_fail["judgement"] = JudgementResult(
        overall_score=5.0, plot_progression=5.0, character_consistency=5.0,
        writing_quality=5.0, pacing=5.0, objective_alignment=5.0,
        pass_threshold=False, issues=["太短"], rewrite_suggestions=["加細節"],
    )
    assert should_rewrite(state_fail) == "rewrite"

    # Max retries - force accept
    state_max = {**state_fail, "rewrite_count": 2}
    assert should_rewrite(state_max) == "force_accept"
