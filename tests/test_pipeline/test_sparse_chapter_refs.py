"""Sparse chapter references must round-trip without inventing chapter completion."""

from copy import deepcopy

import pytest

from scripts.chapter_workflow import chapter_status, record_context, record_graph
from scripts.story_graph_nx import StoryGraph, validate_flat_history
from scripts.story_snapshot import StorySnapshot


def sparse_diff(field, reference, chapter=4):
    if field == "concept":
        return {
            "chapter": chapter,
            "concepts_introduced": [{"name": "合成概念", "chapter": reference}],
        }
    chain = {
        "cause": "合成原因", "effect": "合成結果",
        "cause_ch": chapter, "effect_ch": chapter,
    }
    chain[field] = reference
    return {"chapter": chapter, "causal_chains": [chain]}


def assert_round_trip(graph):
    flat = graph.to_flat()
    validate_flat_history(flat)
    graph.save_flat()
    restored = StoryGraph(graph.path)
    assert restored.load()
    assert restored.to_flat() == flat
    return restored


@pytest.mark.parametrize("field", ["concept", "cause_ch", "effect_ch"])
@pytest.mark.parametrize("reference", [1, "1"])
def test_sparse_reference_round_trip_and_replay(tmp_path, field, reference):
    graph = StoryGraph(tmp_path / "story_graph.json")
    diff = sparse_diff(field, reference)
    graph.apply_chapter_diff(diff)
    flat = graph.to_flat()
    assert flat["chapters"] == [1, 4]
    assert set(flat["_history"]["diffs"]) == {"4"}
    assert graph.G.nodes["chapter:ch1"] == {"type": "chapter", "number": 1}

    restored = assert_round_trip(graph)
    assert restored.apply_chapter_diff(diff)["replayed"] is True
    assert restored.to_flat() == flat
    before = restored.flat_before(4)
    assert before["chapters"] == []
    assert before["concepts"] == {}
    assert before["causal_chains"] == []


@pytest.mark.parametrize("field", ["concept", "cause_ch", "effect_ch"])
def test_replace_removes_unreferenced_placeholders(tmp_path, field):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.apply_chapter_diff(sparse_diff(field, 1))
    graph.apply_chapter_diff({"chapter": 5})
    result = graph.apply_chapter_diff(sparse_diff(field, 2), replace=True)
    assert result["replaced"] is True
    assert graph.to_flat()["chapters"] == [2, 4, 5]
    assert not graph.G.has_node("chapter:ch1")
    assert graph.G.nodes["chapter:ch2"] == {"type": "chapter", "number": 2}
    assert set(graph.to_flat()["_history"]["diffs"]) == {"4", "5"}
    graph = assert_round_trip(graph)

    graph.apply_chapter_diff({"chapter": 4}, replace=True)
    assert graph.to_flat()["chapters"] == [4, 5]
    assert graph.to_flat()["concepts"] == {}
    assert graph.to_flat()["causal_chains"] == []
    assert_round_trip(graph)


def test_replace_preserves_placeholder_referenced_by_another_diff(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.apply_chapter_diff(sparse_diff("concept", 1))
    graph.apply_chapter_diff(sparse_diff("cause_ch", 1, chapter=5))
    graph.apply_chapter_diff({"chapter": 4}, replace=True)
    assert graph.to_flat()["chapters"] == [1, 4, 5]
    assert_round_trip(graph)
    graph.apply_chapter_diff({"chapter": 5}, replace=True)
    assert graph.to_flat()["chapters"] == [4, 5]
    assert_round_trip(graph)


@pytest.mark.parametrize("field", ["cause_ch", "effect_ch"])
@pytest.mark.parametrize("mode", ["omitted", "empty", "null"])
def test_unannotated_causal_reference_round_trip(tmp_path, field, mode):
    graph = StoryGraph(tmp_path / "story_graph.json")
    diff = sparse_diff(field, None if mode == "null" else "")
    if mode == "omitted":
        del diff["causal_chains"][0][field]
    graph.apply_chapter_diff(diff)
    flat = graph.to_flat()
    assert flat["chapters"] == [4]
    assert flat["causal_chains"][0][field] == ""
    assert flat["_history"]["diffs"]["4"] == diff
    restored = assert_round_trip(graph)
    assert restored.apply_chapter_diff(diff)["replayed"] is True
    assert restored.to_flat() == flat


@pytest.mark.parametrize("field", ["concept", "cause_ch", "effect_ch"])
@pytest.mark.parametrize("reference", [5, 0, -1, True])
def test_invalid_reference_never_mutates_graph(tmp_path, field, reference):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.apply_chapter_diff({"chapter": 2})
    before = deepcopy(graph.to_flat())
    with pytest.raises(ValueError, match="this or an earlier chapter"):
        graph.apply_chapter_diff(sparse_diff(field, reference))
    assert graph.to_flat() == before


@pytest.mark.parametrize("reference", [None, ""])
def test_explicit_empty_concept_reference_remains_invalid(tmp_path, reference):
    graph = StoryGraph(tmp_path / "story_graph.json")
    before = graph.to_flat()
    with pytest.raises(ValueError, match="omit the field"):
        graph.apply_chapter_diff(sparse_diff("concept", reference))
    assert graph.to_flat() == before


def test_omitted_concept_reference_uses_current_chapter(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.apply_chapter_diff({
        "chapter": 4, "concepts_introduced": [{"name": "合成概念"}],
    })
    assert graph.to_flat()["chapters"] == [4]
    assert graph.to_flat()["concepts"]["合成概念"]["introduced_in"] == 4
    assert_round_trip(graph)


def test_placeholder_does_not_complete_workflow_or_backfill_history(tmp_path):
    (tmp_path / "outputs").mkdir()
    (tmp_path / "runtime").mkdir()
    (tmp_path / "outputs" / "chapter_001.md").write_text("合成第一章正文。", encoding="utf-8")
    (tmp_path / "runtime" / "story_log.md").write_text(
        "## 第1章：合成章節\n- 摘要：合成事件。", encoding="utf-8",
    )
    graph = StoryGraph(tmp_path / "runtime" / "story_graph.json")
    graph.apply_chapter_diff(sparse_diff("cause_ch", 1))
    graph.save_flat()

    snapshot = StorySnapshot(tmp_path)
    assert snapshot.graph_error is None
    assert snapshot.chapter_diff_signature(1) is None
    assert snapshot.graph_signature(1) is None
    assert snapshot.chapter_diff_signature(4) is not None
    assert snapshot.graph_signature(4) is not None
    record_context(tmp_path, 1)
    state = chapter_status(tmp_path, 1)
    assert state["missing"] == ["story_graph"]
    assert state["complete"] is False
    assert state["review_allowed"] is False
    with pytest.raises(ValueError, match="validated diff"):
        record_graph(tmp_path, 1)
