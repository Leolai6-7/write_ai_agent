"""Graph round trips and chapter edits must preserve story facts."""

from copy import deepcopy

import pytest

from scripts.story_graph_nx import StoryGraph, validate_flat_history


def delta(chapter, events):
    return {"chapter": chapter, "characters_appeared": [{"name": "小青", "events": events}]}


def test_round_trip_keeps_concepts_and_extensions(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    original = {
        "characters": {"小青": {"chapters": [1], "events": "收到信", "notes": "原設定"}},
        "concepts": {"暗號": {"introduced_in": 1, "definition": "三次敲門"}},
        "editor_notes": ["保留原註記"],
    }
    graph.load_flat(original)
    graph.apply_chapter_diff(delta(2, "回信"))
    graph.save_flat()
    other = StoryGraph(graph.path)
    import json
    other.load_flat(json.loads(graph.path.read_text()))
    assert other.to_flat()["concepts"] == original["concepts"]
    assert other.to_flat()["editor_notes"] == original["editor_notes"]
    assert other.to_flat()["characters"]["小青"]["notes"] == "原設定"


def test_retry_does_not_duplicate_and_replacement_replays(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    first = delta(1, "收到紅信")
    graph.apply_chapter_diff(first)
    graph.apply_chapter_diff(delta(2, "找到鑰匙"))
    previous = deepcopy(graph.to_flat())
    assert graph.apply_chapter_diff(first)["replayed"] is True
    assert graph.to_flat() == previous
    with pytest.raises(ValueError, match="--replace"):
        graph.apply_chapter_diff(delta(1, "收到藍信"))
    assert graph.to_flat() == previous
    graph.apply_chapter_diff(delta(1, "收到藍信"), replace=True)
    events = graph.get_character_history("小青")["events"]
    assert events == "收到藍信 · 找到鑰匙"
    assert "找到鑰匙" not in graph.flat_before(2)["characters"]["小青"]["events"]


def test_same_chapter_can_plant_and_hint(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.apply_chapter_diff({"chapter": 1, "foreshadowing_updates": [
        {"thread": "信封", "action": "plant"}, {"thread": "信封", "action": "hint"},
    ]})
    flat = graph.to_flat()
    assert flat["foreshadowing"]["信封"]["planted_in"] == [1]
    assert flat["foreshadowing"]["信封"]["hinted_in"] == [1]
    restored = StoryGraph(graph.path)
    restored.load_flat(flat)
    assert restored.get_foreshadow_chain("信封")["hinted_in"] == [1]


@pytest.mark.parametrize("bad", [None, {"chapter": 0}, {"chapter": True},
    {"chapter": 1, "characters_appeared": [{"name": ""}]},
    {"chapter": 1, "foreshadowing_updates": [{"thread": "信", "action": "oops"}]},
    {"chapter": 1, "concepts_introduced": [{"name": "秘密", "chapter": 2}]},
])
def test_invalid_diff_never_mutates_graph(tmp_path, bad):
    graph = StoryGraph(tmp_path / "story_graph.json")
    before = graph.to_flat()
    with pytest.raises(ValueError):
        graph.apply_chapter_diff(bad)
    assert graph.to_flat() == before


def test_legacy_history_cannot_be_invented(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.load_flat({"characters": {"小青": {"chapters": [3], "events": "最後狀態"}}})
    graph.apply_chapter_diff(delta(4, "繼續前進"))
    with pytest.raises(ValueError, match="predates"):
        graph.flat_before(3)
    with pytest.raises(ValueError, match="legacy baseline"):
        graph.apply_chapter_diff(delta(3, "改寫"), replace=True)
    assert graph.flat_before(4)["characters"]["小青"]["events"] == "最後狀態"


def test_concept_dates_and_event_dates_bound_legacy_history(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.load_flat({"concepts": {"秘密": {"introduced_in": 5}}})
    with pytest.raises(ValueError, match="legacy baseline"):
        graph.apply_chapter_diff(delta(2, "提早知道"))
    with pytest.raises(ValueError, match="historical snapshot"):
        graph.flat_before(3)


def test_repeated_event_text_keeps_distinct_chapter_provenance(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.load_flat({"causal_chains": [
        {"cause": "收到信", "cause_ch": 1, "effect": "前往港口", "effect_ch": 1},
        {"cause": "收到信", "cause_ch": 2, "effect": "返回山城", "effect_ch": 2},
    ]})
    assert {item["cause_ch"] for item in graph.to_flat()["causal_chains"]} == {"1", "2"}


def test_remention_does_not_change_first_concept_introduction(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    for ch in (1, 4):
        graph.apply_chapter_diff({"chapter": ch, "concepts_introduced": [{"name": "暗號", "chapter": ch}]})
    assert graph.to_flat()["concepts"]["暗號"]["introduced_in"] == 1


def test_divergent_snapshot_rejected_on_load_without_mutation(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.apply_chapter_diff(delta(1, "原事件"))
    before = graph.to_flat()
    edited = deepcopy(before)
    edited["characters"]["小青"]["events"] = "直接改快照的事件"
    with pytest.raises(ValueError, match="snapshot differs"):
        graph.load_flat(edited)
    assert graph.to_flat() == before


@pytest.mark.parametrize("operation", ["same_diff", "new_diff", "save_flat", "save", "flat_before"])
def test_in_memory_edits_cannot_be_overwritten_or_saved(tmp_path, operation):
    graph = StoryGraph(tmp_path / "story_graph.json")
    first = delta(1, "原事件")
    graph.apply_chapter_diff(first)
    graph.save_flat()
    persisted = graph.path.read_bytes()
    graph.G.nodes["character:小青"]["events"] = "尚未形成差分的人工修訂"
    actions = {
        "same_diff": lambda: graph.apply_chapter_diff(first),
        "new_diff": lambda: graph.apply_chapter_diff(delta(2, "下一章")),
        "save_flat": graph.save_flat,
        "save": graph.save,
        "flat_before": lambda: graph.flat_before(2),
    }
    with pytest.raises(ValueError, match="snapshot differs"):
        actions[operation]()
    assert graph.G.nodes["character:小青"]["events"] == "尚未形成差分的人工修訂"
    assert graph.path.read_bytes() == persisted


@pytest.mark.parametrize("history", [
    None,
    {"version": True, "baseline": {}, "diffs": {}},
    {"version": 2, "baseline": {}, "diffs": {}},
    {"version": 1, "baseline": {}, "diffs": []},
    {"version": 1, "baseline": {"_history": {}}, "diffs": {}},
    {"version": 1, "baseline": {"characters": []}, "diffs": {}},
    {"version": 1, "baseline": {}, "diffs": {"01": {"chapter": 1}}},
    {"version": 1, "baseline": {}, "diffs": {"1": {"chapter": 2}}},
    {"version": 1, "baseline": {}, "diffs": {"1": {"chapter": 1, "unknown": []}}},
    {"version": 1, "baseline": {}, "diffs": {"1": {
        "chapter": 1, "concepts_introduced": [{"name": "秘密", "chapter": 2}]}}},
    {"version": 1, "baseline": {"chapters": [1]}, "diffs": {"1": {"chapter": 1}}},
])
def test_invalid_history_rejected_before_graph_mutation(tmp_path, history):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.apply_chapter_diff(delta(1, "原事件"))
    before = graph.to_flat()
    edited = deepcopy(before)
    edited["_history"] = history
    with pytest.raises(ValueError):
        validate_flat_history(edited)
    with pytest.raises(ValueError):
        graph.load_flat(edited)
    assert graph.to_flat() == before


def test_legacy_custom_fields_survive_authoritative_replay(tmp_path):
    baseline = {
        "characters": {"小青": {"chapters": ["1"], "events": "收到信", "notes": "保留"}},
        "editor_notes": ["第一項", "第二項"],
        "causal_chains": [{"cause": "收到信", "cause_ch": "1", "effect": "想起故鄉",
                          "effect_ch": 1, "confidence": "作者已確認"}],
        "mirrors": [{"r_line": "山城", "s_line": "港口", "annotation": "保留對照"}],
    }
    validate_flat_history(baseline)
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.load_flat(baseline)
    graph.apply_chapter_diff(delta(2, "回信"))
    validate_flat_history(graph.to_flat())
    graph.save()
    loaded = StoryGraph(graph.path)
    assert loaded.load()
    loaded.apply_chapter_diff(delta(3, "出發"))
    result = loaded.to_flat()
    assert result["_history"]["diffs"]["2"]["chapter"] == 2
    assert result["characters"]["小青"]["notes"] == "保留"
    assert result["editor_notes"] == baseline["editor_notes"]
    assert result["causal_chains"][0]["confidence"] == "作者已確認"
    assert result["mirrors"][0]["annotation"] == "保留對照"


def test_custom_snapshot_changes_are_not_ignored(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.load_flat({"editor_notes": ["原設定"]})
    graph.apply_chapter_diff(delta(1, "原事件"))
    edited = graph.to_flat()
    edited["editor_notes"] = ["新的設定"]
    with pytest.raises(ValueError, match="snapshot differs"):
        validate_flat_history(edited)


def test_relation_order_does_not_change_snapshot_meaning(tmp_path):
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.apply_chapter_diff({"chapter": 1, "causal_chains": [
        {"cause": "來信", "effect": "回信", "cause_ch": 1, "effect_ch": 1},
        {"cause": "回信", "effect": "出發", "cause_ch": 1, "effect_ch": 1},
    ]})
    reordered = graph.to_flat()
    reordered["causal_chains"].reverse()
    validate_flat_history(reordered)


def test_node_link_load_cannot_silently_discard_attached_history(tmp_path):
    import json
    graph = StoryGraph(tmp_path / "story_graph.json")
    graph.path.write_text(json.dumps({"directed": True, "multigraph": True,
        "graph": {}, "nodes": [], "edges": [],
        "_history": {"version": 1, "baseline": {}, "diffs": {}}}))
    with pytest.raises(ValueError, match="flat snapshot format"):
        graph.load()
