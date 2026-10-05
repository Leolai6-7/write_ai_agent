"""Read-once, source-bound views without changing any story artifacts."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.story_graph_nx import StoryGraph
from scripts.story_snapshot import StorySnapshot, chapter_log_entry, value_hash


def story_fixture(tmp_path, count=3):
    (tmp_path / "outputs").mkdir()
    (tmp_path / "runtime").mkdir()
    graph = StoryGraph(tmp_path / "runtime" / "story_graph.json")
    for chapter in range(1, count + 1):
        (tmp_path / "outputs" / f"chapter_{chapter:03d}.md").write_text(f"正文{chapter}\n")
        graph.apply_chapter_diff({"chapter": chapter, "characters_appeared": [
            {"name": "阿青", "events": f"事件{chapter}"}]})
    graph.save_flat()
    (tmp_path / "runtime" / "story_log.md").write_text("\n\n".join(
        f"## 第{chapter}章：章名\n- 摘要：事件{chapter}" for chapter in range(1, count + 1)))
    return tmp_path


def test_snapshot_reads_sources_once_for_many_chapter_checks(tmp_path, monkeypatch):
    story = story_fixture(tmp_path, 12)
    original = Path.read_bytes
    reads = {}

    def counted(path):
        reads[str(path)] = reads.get(str(path), 0) + 1
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", counted)
    snapshot = StorySnapshot(story)
    for _ in range(3):
        for chapter in range(1, 13):
            snapshot.source_fingerprints(chapter)
            snapshot.manuscript_bytes(chapter)
            snapshot.context_signature(chapter)
            snapshot.graph_signature(chapter)
    assert snapshot.is_current()
    assert max(reads.values()) == 1
    assert len(reads) == 15  # 12 manuscripts + graph/log/workflow (absent).
    assert not (story / "runtime" / "chapter_workflow.json").exists()


def test_v1_context_and_graph_signature_compatibility(tmp_path):
    story = story_fixture(tmp_path)
    snapshot = StorySnapshot(story)
    history = snapshot.graph["_history"]
    expected_context = value_hash({
        "baseline": {}, "diffs": {"1": history["diffs"]["1"]},
        "logs": {"1": snapshot.log_entry(1)},
        "manuscripts": {"chapter_001.md": hashlib.sha256("正文1\n".encode()).hexdigest()},
    })
    assert snapshot.context_signature(2) == expected_context
    assert snapshot.graph_signature(2) == value_hash({
        "baseline": history["baseline"],
        "diffs": {str(n): history["diffs"][str(n)] for n in (1, 2)},
    })


def test_crlf_preserves_workflow_text_and_jev_raw_fingerprints(tmp_path):
    story = story_fixture(tmp_path, 1)
    raw = "第一行\r\n第二行\r\n".encode()
    (story / "outputs" / "chapter_001.md").write_bytes(raw)
    snapshot = StorySnapshot(story)
    assert snapshot.manuscript_bytes(1) == raw
    assert snapshot.source_fingerprints(1)["chapter_sha256"] == hashlib.sha256(
        "第一行\n第二行\n".encode()).hexdigest()


@pytest.mark.parametrize("change", ["manuscript", "log", "new_output", "new_workflow", "delete"])
def test_snapshot_detects_changes_without_refreshing_cached_evidence(tmp_path, change):
    story = story_fixture(tmp_path)
    snapshot = StorySnapshot(story)
    original = snapshot.source_fingerprints(1)
    if change == "manuscript":
        (story / "outputs" / "chapter_001.md").write_text("修改")
    elif change == "log":
        (story / "runtime" / "story_log.md").write_text("修改")
    elif change == "new_output":
        (story / "outputs" / "chapter_004.md").write_text("未來")
    elif change == "new_workflow":
        (story / "runtime" / "chapter_workflow.json").write_text('{"version":1,"chapters":{}}')
    else:
        (story / "outputs" / "chapter_001.md").unlink()
    assert not snapshot.is_current()
    assert snapshot.source_fingerprints(1) == original


def test_graph_divergence_cannot_get_receipt_signature(tmp_path):
    story = story_fixture(tmp_path)
    path = story / "runtime" / "story_graph.json"
    raw = json.loads(path.read_text())
    raw["characters"]["阿青"]["events"] = "只改快照"
    path.write_text(json.dumps(raw))
    snapshot = StorySnapshot(story)
    assert "differs" in snapshot.graph_error
    assert snapshot.graph_signature(1) is None
    assert snapshot.chapter_diff_signature(1) is None
    with pytest.raises(ValueError, match="differs"):
        snapshot.context_signature(1)


def test_single_parser_preserves_duplicate_rejection_and_section_boundaries():
    log = "## 第 01 章：標題\n- 摘要：第一行\n第二行\n## 備註\n不是章節\n"
    assert chapter_log_entry(log, 1) == "## 第 01 章：標題\n- 摘要：第一行\n第二行"
    assert chapter_log_entry(log + "## 第1章：重複\n- 摘要：另一版", 1) is None


def test_empty_snapshot_does_not_create_files(tmp_path):
    absent = tmp_path / "absent"
    snapshot = StorySnapshot(absent)
    assert snapshot.graph == {}
    assert snapshot.source_fingerprints(1) == {"chapter_sha256": None, "log_sha256": None}
    assert snapshot.is_current()
    assert not absent.exists()


def test_new_plan_cannot_join_an_inflight_context_snapshot(tmp_path):
    story = story_fixture(tmp_path)
    (story / "planning").mkdir()
    snapshot = StorySnapshot(story)
    (story / "planning" / "arc_plan_2.yaml").write_text("chapters: []")
    assert not snapshot.is_current()
