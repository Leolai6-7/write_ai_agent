"""Narrative facts never imply what a character knows or believes."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts.narrative_state import (
    normalized_hash, prepare_narrative_sources, select_narrative_state,
)
from scripts.story_graph_nx import StoryGraph, validate_chapter_diff, validate_flat_history
from scripts.story_snapshot import StorySnapshot


@pytest.fixture
def story(tmp_path):
    (tmp_path / "outputs").mkdir()
    (tmp_path / "runtime").mkdir()
    texts = {
        1: "# 第一章\n阿青把鑰匙藏在石牆內。\n阿青相信小白已離城。\n\n",
        2: "# 第二章\n阿青把鑰匙交給小白。\n小白尚未知道暗門。\n",
        3: "# 第三章\n小白得知暗門在東牆。\n",
    }
    for number, text in texts.items():
        (tmp_path / "outputs" / f"chapter_{number:03d}.md").write_text(text, encoding="utf-8")
    return tmp_path


def record(record_id="key-location", *, chapter=1, kind="fact", character=None,
           text="鑰匙在石牆內", status=None, start=2, end=2):
    result = {"id": record_id, "kind": kind, "text": text,
              "source": {"chapter": chapter, "start_line": start, "end_line": end}}
    if character is not None:
        result["character"] = character
    if status is not None:
        result["status"] = status
    return result


def apply(graph, story, chapter, records, *, replace=False):
    prepared = prepare_narrative_sources({"chapter": chapter, "narrative_updates": records}, story)
    graph.apply_chapter_diff(prepared, replace=replace)
    graph.save_flat()
    return prepared


def test_source_preparation_is_immutable_stable_and_normalizes_line_endings(story):
    path = story / "outputs" / "chapter_001.md"
    text = path.read_text(encoding="utf-8")
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    original = {"chapter": 1, "narrative_updates": [record()]}
    before = deepcopy(original)
    prepared = prepare_narrative_sources(original, story)
    assert original == before
    update = prepared["narrative_updates"][0]
    assert update["source"]["sha256"] == normalized_hash(text)
    assert update["status"] == "active"
    assert prepare_narrative_sources(prepared, story) == prepared
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    graph.apply_chapter_diff(prepared)
    assert graph.apply_chapter_diff(prepare_narrative_sources(original, story))["replayed"]


@pytest.mark.parametrize("bad", [
    record(chapter=2),
    record(start=0),
    record(start=3, end=2),
    record(end=90),
    record(start=4, end=4),
    record(kind="fact", character="阿青"),
    record(kind="knowledge"),
    record(kind="belief", character=""),
    record(kind="planning"),
    record(status="confirmed"),
    {**record(), "introduced_in": 9},
    {**record(), "source": {"chapter": 1, "start_line": 2, "end_line": 2, "sha256": None}},
    {**record(), "source": {"chapter": 1, "start_line": 2, "end_line": 2, "sha256": "0" * 64}},
])
def test_invalid_or_unverified_sources_are_rejected(story, bad):
    with pytest.raises(ValueError):
        prepare_narrative_sources({"chapter": 1, "narrative_updates": [bad]}, story)
    assert not (story / "runtime" / "story_graph.json").exists()


def test_duplicate_stable_ids_and_unprepared_graph_updates_are_rejected(story):
    with pytest.raises(ValueError, match="Duplicate narrative id"):
        prepare_narrative_sources({"chapter": 1, "narrative_updates": [record(), record()]}, story)
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    before = graph.to_flat()
    with pytest.raises(ValueError, match="prepare chapter sources"):
        graph.apply_chapter_diff({"chapter": 1, "narrative_updates": [record()]})
    assert graph.to_flat() == before


def test_fact_knowledge_belief_stay_separate_and_pov_is_explicit(story):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    apply(graph, story, 1, [record(),
        record("qing-knows-key", kind="knowledge", character="阿青", text="阿青知道藏鑰匙的位置"),
        record("qing-believes-bai", kind="belief", character="阿青", text="小白已離城", start=3, end=3),
        record("bai-believes-key", kind="belief", character="小白", text="阿青可能仍帶著鑰匙"),
    ])
    snapshot = StorySnapshot(story)
    selected = select_narrative_state(snapshot, graph.flat_before(2), 2, ["阿青"])
    assert selected["status"] == "ok"
    assert [r["id"] for r in selected["canon"]] == ["key-location"]
    assert {r["kind"] for r in selected["pov"]} == {"knowledge", "belief"}
    assert {r["character"] for r in selected["pov"]} == {"阿青"}
    assert selected["excluded"] == [{"id": "bai-believes-key", "reason": "wrong_pov"}]
    evidence = selected["canon"][0]
    assert evidence["source"]["path"] == "outputs/chapter_001.md"
    assert evidence["source"]["start_line"] == evidence["source"]["end_line"] == 2
    assert evidence["excerpt"] == "阿青把鑰匙藏在石牆內。"
    without_pov = select_narrative_state(snapshot, graph.flat_before(2), 2, [])
    assert without_pov["status"] == "missing_pov"
    assert without_pov["pov"] == [] and len(without_pov["canon"]) == 1


def test_latest_record_is_projected_by_update_chapter_without_stale_fallback(story):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    apply(graph, story, 1, [record()])
    apply(graph, story, 2, [record(chapter=2, text="鑰匙現在由小白保管")])
    latest = graph.to_flat()["narrative_state"]["key-location"]
    assert latest["introduced_in"] == 1 and latest["updated_in"] == 2
    assert graph.flat_before(2)["narrative_state"]["key-location"]["text"] == "鑰匙在石牆內"
    full = select_narrative_state(StorySnapshot(story), graph.to_flat(), 2, ["阿青"])
    assert full["canon"] == [] and full["excluded"] == [{"id": "key-location", "reason": "future"}]
    (story / "outputs" / "chapter_002.md").write_text("改寫後已沒有交出鑰匙的情節", encoding="utf-8")
    selected = select_narrative_state(StorySnapshot(story), graph.flat_before(3), 3, ["阿青"])
    assert selected["canon"] == []
    assert selected["excluded"] == [{"id": "key-location", "reason": "stale_source"}]


def test_retired_records_are_not_resurrected(story):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    apply(graph, story, 1, [record()])
    apply(graph, story, 2, [record(chapter=2, status="retired", text="原藏匿狀態已失效")])
    selected = select_narrative_state(StorySnapshot(story), graph.flat_before(3), 3, ["阿青"])
    assert selected["canon"] == []
    assert selected["excluded"] == [{"id": "key-location", "reason": "retired"}]


@pytest.mark.parametrize("replacement", [False, True])
@pytest.mark.parametrize("change", ["kind", "character"])
def test_stable_record_identity_cannot_be_redefined(story, replacement, change):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    apply(graph, story, 1, [record("knows-key", kind="knowledge", character="阿青")])
    before = graph.to_flat()
    chapter = 1 if replacement else 2
    changed = record("knows-key", chapter=chapter, kind="belief" if change == "kind" else "knowledge",
                     character="小白" if change == "character" else "阿青")
    prepared = prepare_narrative_sources({"chapter": chapter, "narrative_updates": [changed]}, story)
    with pytest.raises(ValueError, match="cannot change kind or character"):
        graph.apply_chapter_diff(prepared, replace=replacement)
    assert graph.to_flat() == before


def test_narrative_state_cannot_be_edited_around_authoritative_history(story):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    apply(graph, story, 1, [record()])
    edited = graph.to_flat()
    edited["narrative_state"]["key-location"]["text"] = "繞過歷史修改"
    with pytest.raises(ValueError, match="snapshot differs"):
        validate_flat_history(edited)


def test_old_events_concepts_and_notes_do_not_become_narrative_knowledge(story):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    legacy = {"characters": {"阿青": {"chapters": [1], "events": "暗門在東牆"}},
              "concepts": {"暗門": {"introduced_in": 1}}, "author_plan": "阿青將來才知道"}
    graph.load_flat(legacy)
    before = graph.to_flat()
    assert "narrative_state" not in before
    graph.apply_chapter_diff({"chapter": 2})
    graph.save_flat()
    assert "narrative_state" not in graph.to_flat()
    result = select_narrative_state(StorySnapshot(story), graph.flat_before(3), 3, ["阿青"])
    assert result["status"] == "empty" and result["canon"] == [] and result["pov"] == []
    assert graph.flat_before(2) == before


def test_source_change_after_snapshot_returns_no_evidence(story):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    apply(graph, story, 1, [record()])
    snapshot = StorySnapshot(story)
    (story / "outputs" / "chapter_001.md").write_text("已改稿", encoding="utf-8")
    result = select_narrative_state(snapshot, graph.flat_before(2), 2, ["阿青"])
    assert result["status"] == "source_changed"
    assert result["canon"] == [] and result["pov"] == []


def test_update_graph_cli_stamps_sources_and_rejects_bad_source_before_save(story):
    command = [sys.executable, str(Path(__file__).resolve().parents[2] / "scripts" / "update_graph.py"),
               "--story-dir", str(story)]
    diff_path = story / "chapter_diff.yaml"
    raw = {"chapter": 1, "narrative_updates": [record()]}
    diff_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    first = subprocess.run([*command, "--diff", str(diff_path)], capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    graph_path = story / "runtime" / "story_graph.json"
    saved = graph_path.read_bytes()
    state = json.loads(saved)["narrative_state"]["key-location"]
    assert state["source"]["sha256"] == normalized_hash((story / "outputs" / "chapter_001.md").read_text())
    retry = subprocess.run([*command, "--diff", str(diff_path)], capture_output=True, text=True)
    assert retry.returncode == 0 and json.loads(retry.stdout)["replayed"]
    assert graph_path.read_bytes() == saved
    raw["narrative_updates"][0]["source"]["sha256"] = "0" * 64
    diff_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    rejected = subprocess.run([*command, "--diff", str(diff_path)], capture_output=True, text=True)
    assert rejected.returncode == 1
    assert "hash does not match" in rejected.stderr
    assert graph_path.read_bytes() == saved


def test_source_provenance_cannot_claim_an_earlier_evidence_chapter():
    with pytest.raises(ValueError, match="must equal diff.chapter"):
        validate_chapter_diff({"chapter": 3, "narrative_updates": [record(chapter=1)]})
