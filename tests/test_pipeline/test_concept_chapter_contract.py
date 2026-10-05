"""Concept deltas distinguish an omitted chapter from an invalid explicit value."""

from copy import deepcopy

import pytest

from scripts.story_graph_nx import StoryGraph, validate_chapter_diff, validate_flat_history


@pytest.mark.parametrize("chapter", [None, ""])
def test_explicit_empty_concept_chapter_is_rejected(chapter):
    diff = {"chapter": 2, "concepts_introduced": [{"name": "鐘聲", "chapter": chapter}]}

    with pytest.raises(ValueError, match=r"concepts_introduced\.chapter"):
        validate_chapter_diff(diff)


@pytest.mark.parametrize("chapter", [None, ""])
@pytest.mark.parametrize("operation", ["new", "remention", "replace"])
def test_invalid_concept_chapter_preserves_graph_history_and_disk(tmp_path, chapter, operation):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.load_flat({"concepts": {"舊概念": {"introduced_in": None, "definition": "保留"}}})
    graph.apply_chapter_diff({"chapter": 1, "concepts_introduced": [{"name": "鐘聲"}]})
    graph.apply_chapter_diff({"chapter": 2})
    graph.save_flat()
    before = deepcopy(graph.to_flat())
    historical = graph.flat_before(2)
    persisted = graph.path.read_bytes()
    diff = {
        "chapter": 2 if operation == "replace" else 3,
        "characters_appeared": [{"name": "小青", "events": "不應寫入"}],
        "concepts_introduced": [{
            "name": "新概念" if operation == "new" else "鐘聲", "chapter": chapter,
        }],
    }

    with pytest.raises(ValueError, match=r"concepts_introduced\.chapter"):
        graph.apply_chapter_diff(diff, replace=operation == "replace")

    assert graph.to_flat() == before
    assert graph.flat_before(2) == historical
    assert graph.path.read_bytes() == persisted


@pytest.mark.parametrize("chapter", [None, ""])
def test_invalid_concept_in_saved_history_is_rejected_without_mutation(tmp_path, chapter):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.apply_chapter_diff({"chapter": 1, "concepts_introduced": [{"name": "鐘聲"}]})
    graph.save_flat()
    before = deepcopy(graph.to_flat())
    persisted = graph.path.read_bytes()
    malformed = deepcopy(before)
    malformed["_history"]["diffs"]["1"]["concepts_introduced"][0]["chapter"] = chapter

    with pytest.raises(ValueError, match=r"concepts_introduced\.chapter"):
        validate_flat_history(malformed)
    with pytest.raises(ValueError, match=r"concepts_introduced\.chapter"):
        graph.load_flat(malformed)

    assert graph.to_flat() == before
    assert graph.path.read_bytes() == persisted


def test_omitted_concept_chapter_defaults_to_current_through_replay(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    first = {"chapter": 2, "concepts_introduced": [{"name": "鐘聲"}]}
    graph.apply_chapter_diff(first)
    graph.apply_chapter_diff({"chapter": 4, "concepts_introduced": [{"name": "鐘聲"}]})
    before = deepcopy(graph.to_flat())

    assert before["concepts"]["鐘聲"]["introduced_in"] == 2
    assert graph.flat_before(2)["concepts"] == {}
    assert graph.flat_before(4)["concepts"]["鐘聲"]["introduced_in"] == 2
    assert graph.apply_chapter_diff(first)["replayed"] is True
    assert graph.to_flat() == before

    graph.apply_chapter_diff({"chapter": 2, "concepts_introduced": [{"name": "回聲"}]}, replace=True)
    replaced = graph.to_flat()
    assert replaced["concepts"]["回聲"]["introduced_in"] == 2
    assert replaced["concepts"]["鐘聲"]["introduced_in"] == 4
    assert "鐘聲" not in graph.flat_before(4)["concepts"]
    graph.save_flat()
    restored = StoryGraph(graph.path)
    assert restored.load()
    assert restored.to_flat() == replaced
    assert restored.flat_before(4) == graph.flat_before(4)


@pytest.mark.parametrize("chapter", [1, "1", 2, "2"])
def test_explicit_valid_concept_chapter_remains_supported(tmp_path, chapter):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.apply_chapter_diff({"chapter": 1})
    diff = {"chapter": 2, "concepts_introduced": [{"name": "鐘聲", "chapter": chapter}]}
    validate_chapter_diff(diff)
    graph.apply_chapter_diff(diff)

    assert int(graph.to_flat()["concepts"]["鐘聲"]["introduced_in"]) == int(chapter)
    validate_flat_history(graph.to_flat())


def test_legacy_undated_concept_remains_valid_in_baseline_and_round_trip(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    legacy = {"concepts": {"舊概念": {"introduced_in": None, "definition": "保留"}}}
    validate_flat_history(legacy)
    graph.load_flat(legacy)
    graph.apply_chapter_diff({"chapter": 1, "concepts_introduced": [{"name": "鐘聲"}]})
    graph.apply_chapter_diff({"chapter": 2})
    graph.apply_chapter_diff({"chapter": 1, "concepts_introduced": [{"name": "回聲"}]}, replace=True)

    flat = graph.to_flat()
    assert flat["concepts"]["舊概念"] == legacy["concepts"]["舊概念"]
    assert flat["_history"]["baseline"]["concepts"] == legacy["concepts"]
    assert graph.flat_before(1)["concepts"] == legacy["concepts"]
    validate_flat_history(flat)
    graph.save_flat()
    restored = StoryGraph(graph.path)
    assert restored.load()
    assert restored.to_flat() == flat
