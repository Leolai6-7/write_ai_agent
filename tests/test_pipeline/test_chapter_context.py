"""Writer context integration: source distinctions, bounded output and safe receipts."""

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import assemble_context as assemble  # noqa: E402
from chapter_context import build_chapter_context, target_length  # noqa: E402
from chapter_workflow import chapter_status, record_context, record_graph  # noqa: E402
from narrative_state import prepare_narrative_sources  # noqa: E402
from story_graph_nx import StoryGraph  # noqa: E402
from story_snapshot import StorySnapshot, text_hash  # noqa: E402


def record(record_id, text, *, chapter=1, kind="fact", character=None, line=2, status="active"):
    item = {"id": record_id, "kind": kind, "text": text, "status": status,
            "source": {"chapter": chapter, "start_line": line, "end_line": line}}
    if character is not None:
        item["character"] = character
    return item


def apply(story, chapter, records=(), *, threads=(), replace=False):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    if graph.path.exists():
        graph.load_flat(json.loads(graph.path.read_text(encoding="utf-8")))
    prepared = prepare_narrative_sources({
        "chapter": chapter, "narrative_updates": list(records),
        "foreshadowing_updates": [{"thread": name, "action": "plant"} for name in threads],
    }, story)
    graph.apply_chapter_diff(prepared, replace=replace)
    graph.save_flat()
    return graph


@pytest.fixture
def story(tmp_path):
    for directory in ("planning", "runtime", "outputs", "world"):
        (tmp_path / directory).mkdir()
    (tmp_path / "outputs" / "chapter_001.md").write_text(
        "# 第一章\n鑰匙在石牆內：KEY_IN_WALL。\n"
        "阿青知道鑰匙的位置：A_KNOWS_KEY。\n小白以為鑰匙在口袋：B_BELIEVES_POCKET。\n",
        encoding="utf-8",
    )
    (tmp_path / "outputs" / "chapter_002.md").write_text(
        "# 第二章\n鑰匙已交給小白：KEY_WITH_B。\n小白確認收下鑰匙。\n", encoding="utf-8",
    )
    (tmp_path / "runtime" / "story_log.md").write_text(
        "# 故事紀錄\n\n## 第1章：發現\n- 摘要：第一段歷史摘要。\n\n"
        "## 第2章：交會\n- 摘要：第二段歷史摘要。\n", encoding="utf-8",
    )
    chapters = [
        {"chapter": 1, "title": "發現", "line": "R"},
        {"chapter": 2, "title": "交會", "line": "R"},
        {"chapter": 3, "title": "下一步", "line": "R", "pov": "小白",
         "objective": "找到入口", "key_events": ["PLANNED_FUTURE_REVEAL"],
         "characters": ["阿青", "小白"], "locations": ["舊屋"]},
        {"chapter": 4, "title": "尚未來到", "key_events": ["CH4_FUTURE_DO_NOT_INCLUDE"]},
    ]
    (tmp_path / "planning" / "arc_plan_1.yaml").write_text(
        yaml.safe_dump({"chapters": chapters}, allow_unicode=True, sort_keys=False), encoding="utf-8",
    )
    (tmp_path / "planning" / "story_brief.md").write_text(
        "# 故事規格\n\n- **每章字數**：1200–1600 字\n", encoding="utf-8",
    )
    (tmp_path / "world" / "character_cast.md").write_text(
        "# 人物\n\n## 阿青\nLIVE_A_PROFILE_SECRET\n\n## 小白\nLIVE_B_PROFILE_SECRET\n"
        + "\n".join(f"現在狀態 {n}" for n in range(60)) + "\n## 路人\nUNRELATED_PROFILE\n",
        encoding="utf-8",
    )
    (tmp_path / "world" / "world_bible.md").write_text(
        "# 世界\n## 舊屋\nLIVE_LOCATION_SECRET\n## 別處\nOTHER_LOCATION_SECRET\n",
        encoding="utf-8",
    )
    apply(tmp_path, 1, [
        record("key-location", "KEY_IN_WALL"),
        record("a-knows", "A_KNOWS_KEY", kind="knowledge", character="阿青", line=3),
        record("b-believes", "B_BELIEVES_POCKET", kind="belief", character="小白", line=4),
    ])
    apply(tmp_path, 2)
    return tmp_path


def recall_state(backend="chroma"):
    return {"selected_backend": backend,
            "semantic_recall": {"status": "not_indexed", "results": []},
            "jev_memory": {"status": "disabled", "evidence": []}}


def context(story, *, beat_changes=None, max_chars=12000, recall=None):
    snapshot = StorySnapshot(story)
    beat = assemble.load_beat(story, 3, snapshot=snapshot)
    beat.update(beat_changes or {})
    projected = assemble._graph_snapshot(story, snapshot.graph, 3, snapshot=snapshot)
    return build_chapter_context(snapshot, 3, beat, projected, recall or recall_state(),
                                 max_chars=max_chars)


def included(bundle):
    return {item["key"]: item for item in bundle.metadata["included"]}


def test_fact_and_conflicting_belief_are_distinct_from_planned_future(story):
    bundle = context(story)
    entries = included(bundle)
    assert entries["narrative:key-location"]["section"] == "canon_as_of"
    assert entries["narrative:b-believes"]["section"] == "pov_knowledge"
    assert entries["chapter_intent"]["section"] == "author_intent"
    assert "事實紀錄：KEY_IN_WALL" in bundle.text
    assert "相信（不保證真實）：B_BELIEVES_POCKET" in bundle.text
    assert "PLANNED_FUTURE_REVEAL" in bundle.text
    assert "CH4_FUTURE_DO_NOT_INCLUDE" not in bundle.text


def test_pov_b_does_not_inherit_a_knowledge_even_when_a_is_present(story):
    bundle = context(story)
    assert bundle.metadata["pov"] == ["小白"]
    assert "narrative:b-believes" in included(bundle)
    assert "narrative:a-knows" not in included(bundle)
    assert "A_KNOWS_KEY" not in bundle.text
    assert {"id": "a-knows", "reason": "wrong_pov"} in bundle.metadata["narrative_excluded"]
    both = context(story, beat_changes={"pov": ["阿青", "小白"]})
    assert "阿青｜已知紀錄：A_KNOWS_KEY" in both.text
    assert "小白｜相信（不保證真實）：B_BELIEVES_POCKET" in both.text


def test_missing_pov_is_explicit_and_not_inferred_from_cast(story):
    bundle = context(story, beat_changes={"pov": None})
    assert bundle.metadata["narrative_status"] == "missing_pov"
    assert bundle.metadata["pov"] == []
    assert "視角未標註" in bundle.text
    assert "narrative:key-location" in included(bundle)
    assert "narrative:a-knows" not in included(bundle)
    assert "narrative:b-believes" not in included(bundle)


def test_one_hundred_valid_pov_cards_fit_default_budget_by_omitting_whole_records(story):
    texts = [
        f"POV_CARD_{number:03d}_BEGIN：小白確認第 {number} 個抽屜的鑰匙仍在原處，"
        f"並記住該抽屜須先扣緊底板才可拉開。POV_CARD_{number:03d}_END"
        for number in range(100)
    ]
    (story / "outputs" / "chapter_001.md").write_text(
        "# 第一章\n" + "\n".join(texts) + "\n", encoding="utf-8",
    )
    apply(story, 1, [
        record(f"pov-{number:03d}", text, kind="knowledge", character="小白", line=number + 2)
        for number, text in enumerate(texts)
    ], replace=True)
    bundle = context(story, max_chars=None)
    entries = included(bundle)
    knowledge_keys = {key for key in entries if key.startswith("narrative:pov-")}
    assert bundle.metadata["max_chars"] == 12000
    assert len(bundle.text) == bundle.metadata["char_count"] <= 12000
    assert 0 < len(knowledge_keys) < 100
    omitted = {item["key"]: item for item in bundle.metadata["omitted"]}
    assert len(knowledge_keys) + sum(key.startswith("narrative:pov-") for key in omitted) == 100
    for number, text in enumerate(texts):
        key = f"narrative:pov-{number:03d}"
        if key in knowledge_keys:
            assert text in bundle.text
        else:
            assert omitted[key]["reason"] == "char_budget"
            assert f"POV_CARD_{number:03d}_BEGIN" not in bundle.text
            assert f"POV_CARD_{number:03d}_END" not in bundle.text
            assert text not in json.dumps(bundle.metadata, ensure_ascii=False)
    assert {"boundaries", "chapter_intent", "canon_unknown", "pov_boundary"} <= entries.keys()
    assert "未標註知情" in bundle.text
    assert "不等於人物不知道" in bundle.text


@pytest.mark.parametrize("invalid", ["stale_source", "retired"])
def test_latest_invalid_state_never_falls_back_to_older_fact(story, invalid):
    apply(story, 2, [record("key-location", "KEY_WITH_B", chapter=2,
                           status="retired" if invalid == "retired" else "active")], replace=True)
    if invalid == "stale_source":
        (story / "outputs" / "chapter_002.md").write_text("修訂後已無交付事件。", encoding="utf-8")
    bundle = context(story)
    assert "narrative:key-location" not in included(bundle)
    assert "KEY_IN_WALL" not in bundle.text and "KEY_WITH_B" not in bundle.text
    assert {"id": "key-location", "reason": invalid} in bundle.metadata["narrative_excluded"]


def test_historically_complete_but_review_needed_source_is_not_injected(story):
    apply(story, 2, [record("key-location", "KEY_WITH_B", chapter=2)], replace=True)
    for chapter in (1, 2):
        record_context(story, chapter)
        assert record_graph(story, chapter)["complete"]
    path = story / "outputs" / "chapter_001.md"
    path.write_text(path.read_text(encoding="utf-8") + "上游修訂。\n", encoding="utf-8")
    assert chapter_status(story, 2)["lifecycle"] == "needs_review"
    bundle = context(story)
    assert "KEY_WITH_B" not in bundle.text
    assert {"id": "key-location", "reason": "source_needs_review"} in bundle.metadata["narrative_excluded"]


@pytest.mark.parametrize("lifecycle", ["needs_review", "writing"])
def test_tracked_stale_source_does_not_supply_graph_values_or_thread_progress(story, lifecycle):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    graph.load_flat(json.loads(graph.path.read_text(encoding="utf-8")))
    graph.apply_chapter_diff({
        "chapter": 2,
        "new_values": [{"setting": "保管費", "value": "VALUE_FROM_CHAPTER_TWO",
                        "note": "NOTE_FROM_CHAPTER_TWO"}],
        "foreshadowing_updates": [{"thread": "①第二章的暗門", "action": "plant"}],
    }, replace=True)
    graph.save_flat()
    for chapter in (1, 2):
        record_context(story, chapter)
        assert record_graph(story, chapter)["complete"]
    changed_chapter = 1 if lifecycle == "needs_review" else 2
    path = story / "outputs" / f"chapter_{changed_chapter:03d}.md"
    path.write_text(path.read_text(encoding="utf-8") + "正文修改但尚未更新圖譜。\n", encoding="utf-8")
    assert chapter_status(story, 2)["lifecycle"] == lifecycle
    bundle = context(story, beat_changes={"foreshadow_threads": ["伏筆一"]})
    assert "VALUE_FROM_CHAPTER_TWO" not in bundle.text
    assert "NOTE_FROM_CHAPTER_TWO" not in bundle.text
    assert "植入 [2]" not in bundle.text
    assert any(warning in bundle.text for warning in ("待覆核", "未完成", "待確認", "已省略"))


def test_tiny_budget_main_emits_no_stdout_and_creates_no_context_receipt(story, monkeypatch, capsys):
    monkeypatch.setattr(assemble, "recall_chapter_memory", lambda *a, **kw: recall_state())
    monkeypatch.setattr(sys, "argv", ["assemble_context.py", "--story-dir", str(story),
                                     "--chapter", "3", "--max-context-chars", "1"])
    receipt_path = story / "runtime" / "chapter_workflow.json"
    assert not receipt_path.exists()
    with pytest.raises(SystemExit) as error:
        assemble.main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Required context needs" in captured.err
    assert not receipt_path.exists()


@pytest.mark.parametrize("target_name", ["伏筆一：暗門", "①暗門"])
def test_target_thread_is_required_even_with_huge_unrelated_foreshadowing(story, target_name):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    graph.load_flat(json.loads(graph.path.read_text(encoding="utf-8")))
    original = deepcopy(graph.to_flat()["_history"]["diffs"]["1"])
    original["foreshadowing_updates"] = [
        {"thread": "⑩無關背景" + "長" * 8000, "action": "plant"},
        {"thread": target_name, "action": "plant"},
    ]
    graph.apply_chapter_diff(original, replace=True)
    graph.save_flat()
    bundle = context(story, beat_changes={"foreshadow_threads": ["伏筆一"]}, max_chars=5000)
    assert included(bundle)[f"thread:{target_name}"]["required"] is True
    assert not any(item["key"].startswith("thread:⑩無關背景") for item in bundle.metadata["included"])
    assert "長" * 20 not in bundle.text


def test_thread_one_does_not_make_thread_eleven_required(story):
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    graph.load_flat(json.loads(graph.path.read_text(encoding="utf-8")))
    diff = deepcopy(graph.to_flat()["_history"]["diffs"]["1"])
    diff["foreshadowing_updates"] = [{"thread": "伏筆十一：其他線索", "action": "plant"}]
    graph.apply_chapter_diff(diff, replace=True)
    graph.save_flat()
    bundle = context(story, beat_changes={"foreshadow_threads": ["伏筆一"]})
    assert included(bundle)["thread:伏筆十一：其他線索"]["required"] is False


def test_target_thread_reference_points_to_same_identity_not_substring_heading(story):
    (story / "planning" / "foreshadowing.md").write_text(
        "# 伏筆設計\n## 伏筆十一：其他線索\nWRONG_THREAD_DESIGN\n"
        "## ⑩暗門\nTARGET_THREAD_DESIGN\n", encoding="utf-8",
    )
    bundle = context(story, beat_changes={"foreshadow_threads": ["伏筆十"]})
    source = included(bundle)["design_thread:伏筆十"]["sources"][0]
    assert source["start_line"] == 4
    assert source["end_line"] == 5


def test_target_length_comes_from_story_brief_and_beat_can_override(story):
    snapshot = StorySnapshot(story)
    length, sources = target_length(snapshot, {})
    assert length == "1200–1600 字"
    assert sources[0].path == "planning/story_brief.md"
    assert sources[0].start_line == sources[0].end_line == 3
    assert "TARGET LENGTH: 1200–1600 字" in context(story).text
    assert "TARGET LENGTH: 900 字" in context(story, beat_changes={"target_length": 900}).text
    assert "TARGET LENGTH: 依使用者本次指定" in context(
        story, beat_changes={"target_length": "依使用者本次指定"},
    ).text


def test_living_profiles_are_bounded_references_not_copied_content(story):
    bundle = context(story)
    for secret in ("LIVE_A_PROFILE_SECRET", "LIVE_B_PROFILE_SECRET", "LIVE_LOCATION_SECRET",
                   "UNRELATED_PROFILE", "OTHER_LOCATION_SECRET"):
        assert secret not in bundle.text
        assert secret not in json.dumps(bundle.metadata, ensure_ascii=False)
    for key in ("design_character:阿青", "design_character:小白", "design_location:舊屋"):
        item = included(bundle)[key]
        assert item["section"] == "reference"
        assert item["sources"]
        for ref in item["sources"]:
            assert ref["end_line"] - ref["start_line"] + 1 <= 40


def test_compound_location_uses_local_wiki_heading_without_copying_living_content(story):
    location_dir = story / "world" / "locations"
    location_dir.mkdir()
    (location_dir / "小廚房.md").write_text(
        "# 小廚房\nCURRENT_KITCHEN_PROFILE_DO_NOT_INJECT\n\n"
        "# 不相干的側院\nUNRELATED_COURTYARD_PROFILE\n", encoding="utf-8",
    )
    name = "永壽棋院-一樓小廚房備品台"
    bundle = context(story, beat_changes={"locations": [name]})
    references = included(bundle)[f"design_location:{name}"]["sources"]
    assert len(references) == 1
    assert references[0]["path"] == "world/locations/小廚房.md"
    assert references[0]["start_line"] == 1
    assert references[0]["end_line"] == 3
    for content in ("CURRENT_KITCHEN_PROFILE_DO_NOT_INJECT", "UNRELATED_COURTYARD_PROFILE"):
        assert content not in bundle.text
        assert content not in json.dumps(bundle.metadata, ensure_ascii=False)


def test_included_source_spans_are_exact_and_hash_actual_normalized_sources(story):
    bundle = context(story)
    entries = included(bundle)
    ref = entries["narrative:key-location"]["sources"][0]
    assert ref["start_line"] == ref["end_line"] == 2
    lines = (story / ref["path"]).read_text(encoding="utf-8").splitlines()
    assert lines[ref["start_line"] - 1:ref["end_line"]] == ["鑰匙在石牆內：KEY_IN_WALL。"]
    plan_ref = entries["chapter_intent"]["sources"][0]
    plan_lines = (story / plan_ref["path"]).read_text(encoding="utf-8").splitlines()
    span = "\n".join(plan_lines[plan_ref["start_line"] - 1:plan_ref["end_line"]])
    assert "chapter: 3" in span and "PLANNED_FUTURE_REVEAL" in span
    assert "chapter: 4" not in span and "CH4_FUTURE_DO_NOT_INCLUDE" not in span
    for number in (1, 2):
        source = entries[f"log:{number}"]["sources"][0]
        log_lines = (story / source["path"]).read_text(encoding="utf-8").splitlines()
        excerpt = "\n".join(log_lines[source["start_line"] - 1:source["end_line"]])
        assert excerpt == StorySnapshot(story).log_entry(number)
    for source in bundle.metadata["sources"]:
        text = (story / source["path"]).read_text(encoding="utf-8")
        assert source["sha256"] == text_hash(text)
        assert 1 <= source["start_line"] <= source["end_line"] <= len(text.splitlines())


@pytest.mark.parametrize("backend", ["chroma", "jev-mem"])
def test_json_does_not_reexpose_backend_evidence_outside_bounded_package(
    story, monkeypatch, capsys, backend,
):
    recall = recall_state(backend)
    recall["semantic_recall"].update({"status": "ok", "results": [
        {"chapter_id": 1, "summary": "EXCLUDED_CHROMA_BACKEND_TEXT" * 1000},
        {"chapter_id": 99, "summary": "EXCLUDED_FUTURE_TEXT"},
    ]})
    recall["jev_memory"].update({"status": "ok", "evidence": [
        {"chapter": 1, "text": "EXCLUDED_JEV_BACKEND_TEXT" * 1000},
        {"chapter": 99, "text": "EXCLUDED_FUTURE_TEXT"},
    ]})
    monkeypatch.setattr(assemble, "recall_chapter_memory", lambda *a, **kw: recall)
    monkeypatch.setattr(sys, "argv", ["assemble_context.py", "--story-dir", str(story),
                                     "--chapter", "3", "--format", "json",
                                     "--max-context-chars", "5000"])
    assemble.main()
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert captured.err == ""
    assert "EXCLUDED_" not in captured.out
    assert "results" not in output["semantic_recall"]
    assert "evidence" not in output["jev_memory"]
    assert output["selected_memory_backend"] == backend
    assert len(output["context_package"]) == output["context_metadata"]["char_count"] <= 5000
    assert json.loads((story / "runtime" / "chapter_workflow.json").read_text())["chapters"]["3"]["context"]


def test_log_excluded_by_budget_does_not_escape_in_json_metadata(story, monkeypatch, capsys):
    log_path = story / "runtime" / "story_log.md"
    log_path.write_text(
        "## 第1章：巨大摘要\n- 摘要：" + "OMITTED_SOURCE_LOG" * 1000
        + "\n\n## 第2章：簡短摘要\n- 摘要：小白來到舊屋。\n", encoding="utf-8",
    )
    recall = recall_state()
    recall["semantic_recall"].update({"status": "ok", "results": [
        {"chapter_id": 1, "summary": "OMITTED_SOURCE_LOG" * 1000},
    ]})
    monkeypatch.setattr(assemble, "recall_chapter_memory", lambda *a, **kw: recall)
    monkeypatch.setattr(sys, "argv", ["assemble_context.py", "--story-dir", str(story),
                                     "--chapter", "3", "--format", "json",
                                     "--max-context-chars", "5000"])
    assemble.main()
    raw = capsys.readouterr().out
    output = json.loads(raw)
    assert "OMITTED_SOURCE_LOG" not in raw
    assert {"key": "log:1", "section": "continuity", "reason": "char_budget"} in (
        output["context_metadata"]["omitted"]
    )
    assert len(output["context_package"]) <= 5000


def test_text_main_remains_compatible_and_records_context_after_success(story, monkeypatch, capsys):
    monkeypatch.setattr(assemble, "recall_chapter_memory", lambda *a, **kw: recall_state())
    monkeypatch.setattr(sys, "argv", ["assemble_context.py", "--story-dir", str(story),
                                     "--chapter", "3"])
    assemble.main()
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Chapter 3" in captured.out and "TARGET LENGTH: 1200–1600 字" in captured.out
    workflow = json.loads((story / "runtime" / "chapter_workflow.json").read_text())
    assert workflow["chapters"]["3"]["context"]
