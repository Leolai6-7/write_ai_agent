"""Chapter context must recall prior evidence without leaking later outcomes."""

import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import assemble_context as context  # noqa: E402

FIRST_SUMMARY = "過去一" + "文" * 2000


@pytest.fixture
def story(tmp_path):
    for name in ("planning", "runtime", "outputs", "world", "chroma"):
        (tmp_path / name).mkdir()
    chapters = [
        {"chapter": number, "title": f"章{number}", "line": line,
         "objective": "尋找記憶", "key_events": ["返回舊屋"],
         "characters": ["阿青"], "locations": ["舊屋"]}
        for number, line in [(1, "R"), (2, "S"), (3, "R"), (4, "S")]
    ]
    (tmp_path / "planning" / "arc_plan_1.yaml").write_text(
        yaml.safe_dump({"chapters": chapters}, allow_unicode=True), encoding="utf-8",
    )
    (tmp_path / "runtime" / "story_log.md").write_text(
        f"# Log\n\n## 第1章：第一\n- 摘要：{FIRST_SUMMARY}\n\n"
        "## 第2章：第二\n- 摘要：過去二\n\n"
        "## 第3章：第三\n- 摘要：本章洩漏\n\n"
        "## 第4章：第四\n- 摘要：未來洩漏\n",
        encoding="utf-8",
    )
    for number in range(1, 5):
        (tmp_path / "outputs" / f"chapter_{number:03d}.md").write_text(
            f"章{number}的結尾", encoding="utf-8",
        )
    return tmp_path


@pytest.fixture
def indexed_story(story):
    from index_chapter import index_chapter

    class IndexBackend:
        def __init__(self, *args, **kwargs):
            pass

        def add_chapter(self, **kwargs):
            pass

    for chapter in (1, 2):
        result = index_chapter(story, chapter, story / "outputs" / f"chapter_{chapter:03d}.md",
                               retriever_factory=IndexBackend)
        assert result["status"] == "ok"
    return story


def test_yaml_same_line_ending_and_chronological_logs(story):
    ending = context.get_previous_chapter_ending(story, 3, "R")
    assert "from ch1" in ending
    assert "章1的結尾" in ending
    assert "章2的結尾" not in ending
    recent = context.get_recent_log_entries(story, before_chapter=3)
    assert "過去一" in recent and "過去二" in recent
    assert "本章洩漏" not in recent and "未來洩漏" not in recent
    other_line = context.get_dual_line_info(story, "R", before_chapter=3)
    assert "過去二" in other_line and "洩漏" not in other_line


def test_markdown_same_line_fallback_remains_compatible(tmp_path):
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs" / "chapter_001.md").write_text("舊版結尾", encoding="utf-8")
    beat_table = "| 1 | 前章 | R | 目標 | 事件 | 情緒 | 角色 | 場景 | ①plant |"
    assert "舊版結尾" in context.get_previous_chapter_ending(tmp_path, 3, "R", beat_table)


def test_combined_lines_match_but_empty_line_is_not_a_wildcard():
    assert context._lines_overlap("R", "R+S")
    assert context._lines_overlap("S", "融合")
    assert not context._lines_overlap("R", "")
    assert not context._lines_overlap("R", "S")


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {"chapter_id": 4, "summary": "future", "distance": 0.01},
            {"chapter_id": 3, "summary": "current", "distance": 0.02},
            {"chapter_id": 1, "summary": FIRST_SUMMARY, "distance": 0.2},
            {"chapter_id": 1, "summary": "duplicate", "distance": 0.2},
            {"chapter_id": 2, "summary": "過去二", "distance": 0.3},
        ]


def test_candidate_recall_preserves_source_and_enforces_bounds(indexed_story):
    story = indexed_story
    retriever = FakeRetriever()
    result = context.recall_semantic_candidates(
        story, 3, {"objective": "查找" * 1000}, retriever=retriever,
    )
    assert result["status"] == "ok"
    assert [r["chapter_id"] for r in result["results"]] == [1, 2]
    assert result["results"][0]["source"] == str(story / "outputs" / "chapter_001.md")
    assert len(result["results"][0]["summary"]) <= 600
    assert len(retriever.calls[0]["query_text"]) <= 1200
    assert retriever.calls[0]["before_chapter"] == 3


def test_missing_index_does_not_initialize_retriever(story, monkeypatch):
    def unexpected(*args):
        raise AssertionError("must not load a model")

    monkeypatch.setattr(context, "get_retriever", unexpected)
    assert context.recall_semantic_candidates(story, 3, {})["status"] == "not_indexed"
    assert not (story / "chroma" / "chroma.sqlite3").exists()


def test_backend_failure_is_visible_in_context_status(story):
    class BrokenRetriever:
        def query(self, **kwargs):
            raise ModuleNotFoundError("missing optional dependency")

    assert context.recall_semantic_candidates(story, 3, {}, retriever=BrokenRetriever()) == {
        "status": "unavailable", "results": [], "error": "ModuleNotFoundError",
    }


def test_unreceipted_legacy_index_requires_reindex(story):
    result = context.recall_semantic_candidates(story, 3, {}, retriever=FakeRetriever())
    assert result["status"] == "needs_reindex"
    assert result["results"] == []
    assert {item["reason"] for item in result["skipped"]} == {"index_receipt_not_current"}


@pytest.mark.parametrize("change, reason", [
    ("chapter", "index_receipt_not_current"),
    ("summary", "summary_changed"),
    ("missing_source", "missing_source"),
    ("duplicate_chapter", "missing_or_ambiguous_log"),
    ("duplicate_summary", "missing_or_ambiguous_log"),
])
def test_changed_or_ambiguous_sources_are_excluded(indexed_story, change, reason):
    story = indexed_story
    source = story / "outputs" / "chapter_001.md"
    log = story / "runtime" / "story_log.md"
    if change == "chapter":
        source.write_text("修改後的正文", encoding="utf-8")
    elif change == "summary":
        log.write_text(log.read_text(encoding="utf-8").replace(FIRST_SUMMARY, "新的摘要"),
                       encoding="utf-8")
    elif change == "missing_source":
        source.unlink()
    elif change == "duplicate_chapter":
        log.write_text(log.read_text(encoding="utf-8") + "\n## 第1章：重複\n- 摘要：另一份\n",
                       encoding="utf-8")
    else:
        log.write_text(log.read_text(encoding="utf-8").replace(
            f"- 摘要：{FIRST_SUMMARY}", f"- 摘要：{FIRST_SUMMARY}\n- 摘要：重複摘要"),
            encoding="utf-8")
    result = context.recall_semantic_candidates(story, 3, {}, retriever=FakeRetriever())
    assert [row["chapter_id"] for row in result["results"]] == [2]
    assert result["skipped"] == [{"chapter_id": 1, "reason": reason}]


def test_legacy_cumulative_graph_is_not_presented_as_historical_evidence(story):
    graph = {
        "characters": {"阿青": {"chapters": [1, 4], "events": "未來的角色狀態"}},
        "values": {"寶物": {"value": "未來才發現的值"}},
        "concepts": {"未來概念": {"introduced_in": 4}},
    }
    (story / "runtime" / "story_graph.json").write_text(json.dumps(graph), encoding="utf-8")
    result = context.check_graph_conditions(story, ["阿青"], 3)
    assert result["status"] == "skipped_newer_state"
    assert result["numerical_values"] == ""
    assert "未來的角色狀態" not in result["graph_context"]
    assert "未來概念" not in context.get_concept_tracking(story, before_chapter=3)


def test_tracked_graph_replays_only_prior_chapters(story):
    from story_graph_nx import StoryGraph

    graph = StoryGraph(story / "runtime" / "story_graph.json")
    graph.load_flat({})
    graph.apply_chapter_diff({
        "chapter": 1,
        "characters_appeared": [{"name": "阿青", "events": "先前抵達"}],
        "new_values": [{"setting": "寶物位置", "value": "過去的位置"}],
        "foreshadowing_updates": [{"thread": "身世", "action": "plant"}],
    })
    graph.apply_chapter_diff({
        "chapter": 3,
        "new_values": [{"setting": "寶物位置", "value": "本章才移動的位置"}],
        "foreshadowing_updates": [{"thread": "身世", "action": "resolve"}],
        "concepts_introduced": [{"name": "本章才知的概念"}],
    })
    graph.save_flat()
    result = context.check_graph_conditions(story, ["阿青"], 3)
    assert result["status"] == "ok"
    assert "過去的位置" in result["numerical_values"]
    assert "本章才移動的位置" not in result["numerical_values"]
    assert "planted ch1" in result["graph_context"]
    assert "resolved ch3" not in result["graph_context"]
    assert "本章才知的概念" not in context.get_concept_tracking(story, before_chapter=3)


def test_cli_includes_real_recall_path_and_records_context(indexed_story, monkeypatch, capsys):
    import chapter_workflow

    story = indexed_story
    (story / "chroma" / "chroma.sqlite3").touch()
    retriever = FakeRetriever()
    recorded = []
    monkeypatch.setattr(context, "get_retriever", lambda _: retriever)
    def record(directory, chapter, *, snapshot):
        assert capsys.readouterr().out == ""
        assert snapshot.is_current()
        recorded.append((directory, chapter))

    monkeypatch.setattr(chapter_workflow, "record_context", record)
    monkeypatch.setattr(sys, "argv", ["assemble_context.py", "--story-dir", str(story),
                                     "--chapter", "3", "--format", "json"])
    context.main()
    result = json.loads(capsys.readouterr().out)
    assert result["semantic_recall"]["status"] == "ok"
    assert "SEMANTIC RECALL" in result["context_package"]
    assert "chapter_001.md" in result["context_package"]
    assert "本章洩漏" not in result["context_package"]
    assert "未來洩漏" not in result["context_package"]
    assert recorded == [(story, 3)]


@pytest.mark.parametrize("changed", ["manuscript", "log", "plan"])
def test_source_change_during_context_emits_nothing_and_records_nothing(
        indexed_story, monkeypatch, capsys, changed):
    import chapter_workflow

    story = indexed_story
    (story / "chroma" / "chroma.sqlite3").touch()
    sources = {"manuscript": story / "outputs" / "chapter_001.md",
               "log": story / "runtime" / "story_log.md",
               "plan": story / "planning" / "arc_plan_1.yaml"}
    state_path = story / "runtime" / "chapter_workflow.json"
    before = state_path.read_bytes()

    class ChangingRetriever(FakeRetriever):
        def query(self, **kwargs):
            source = sources[changed]
            source.write_text(source.read_text(encoding="utf-8") + "\n# 同時修訂\n", encoding="utf-8")
            return super().query(**kwargs)

    monkeypatch.setattr(context, "get_retriever", lambda _: ChangingRetriever())
    monkeypatch.setattr(chapter_workflow, "record_context",
                        lambda *a, **kw: pytest.fail("changed sources were receipted"))
    monkeypatch.setattr(sys, "argv", ["assemble_context.py", "--story-dir", str(story),
                                     "--chapter", "3", "--format", "json"])
    with pytest.raises(SystemExit) as error:
        context.main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "changed while assembling" in captured.err
    assert state_path.read_bytes() == before


def test_invalid_graph_aborts_context_before_backend_or_receipt(indexed_story, monkeypatch, capsys):
    from story_graph_nx import StoryGraph

    story = indexed_story
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    graph.apply_chapter_diff({"chapter": 1, "characters_appeared": [{"name": "阿青", "events": "原事件"}]})
    flat = graph.to_flat()
    flat["characters"]["阿青"]["events"] = "未形成差分的編輯"
    graph.path.write_text(json.dumps(flat), encoding="utf-8")
    monkeypatch.setattr(context, "recall_chapter_memory",
                        lambda *a, **kw: pytest.fail("invalid graph reached memory backend"))
    monkeypatch.setattr(sys, "argv", ["assemble_context.py", "--story-dir", str(story),
                                     "--chapter", "3"])
    before = (story / "runtime" / "chapter_workflow.json").read_bytes()
    with pytest.raises(SystemExit) as error:
        context.main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "snapshot differs" in captured.err
    assert (story / "runtime" / "chapter_workflow.json").read_bytes() == before


def test_main_reads_each_story_and_plan_source_once(indexed_story, monkeypatch, capsys):
    from collections import Counter

    story = indexed_story
    (story / "chroma" / "chroma.sqlite3").touch()
    counts = Counter()
    original_read = Path.read_bytes

    def counted_read(path):
        counts[path.absolute()] += 1
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", counted_read)
    monkeypatch.setattr(context, "get_retriever", lambda _: FakeRetriever())
    monkeypatch.setattr(sys, "argv", ["assemble_context.py", "--story-dir", str(story),
                                     "--chapter", "3", "--format", "json"])
    context.main()
    assert json.loads(capsys.readouterr().out)["semantic_recall"]["status"] == "ok"
    for source in [*sorted((story / "outputs").glob("chapter_*.md")),
                   story / "runtime" / "story_log.md", story / "runtime" / "story_graph.json",
                   story / "planning" / "arc_plan_1.yaml"]:
        assert counts[source.absolute()] == 1, (source, counts[source.absolute()])


@pytest.mark.parametrize("lifecycle", ["writing", "needs_review"])
def test_semantic_recall_excludes_incomplete_tracked_chapter(indexed_story, lifecycle):
    from chapter_workflow import record_context, record_graph, chapter_status
    from story_graph_nx import StoryGraph

    story = indexed_story
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    record_context(story, 1)
    graph.apply_chapter_diff({"chapter": 1})
    graph.save_flat()
    record_graph(story, 1)
    record_context(story, 2)
    if lifecycle == "needs_review":
        graph.apply_chapter_diff({"chapter": 2})
        graph.save_flat()
        assert record_graph(story, 2)["complete"]
        (story / "outputs" / "chapter_001.md").write_text("前章已修訂", encoding="utf-8")
    assert chapter_status(story, 2)["lifecycle"] == lifecycle
    result = context.recall_semantic_candidates(story, 3, {}, retriever=FakeRetriever())
    assert 2 not in [entry["chapter_id"] for entry in result["results"]]
    assert {"chapter_id": 2, "reason": "chapter_" + lifecycle} in result["skipped"]


def test_node_link_graph_uses_snapshot_without_reopening_source(story, monkeypatch):
    from story_graph_nx import StoryGraph
    from story_snapshot import StorySnapshot

    graph = StoryGraph(story / "runtime" / "story_graph.json")
    graph.G.add_node("chapter:ch1", type="chapter", number=1)
    graph.G.add_node("value:暗號", type="value", setting="暗號", value="三次敲門", note="已確定")
    graph.save()
    snapshot = StorySnapshot(story)
    monkeypatch.setattr(StoryGraph, "load", lambda *a: pytest.fail("graph source reopened"))
    result = context.check_graph_conditions(story, [], 5, snapshot=snapshot)
    assert result["status"] == "ok"
    assert "三次敲門" in result["numerical_values"]
