"""Offline regression tests for log-only completion and cross-story leakage."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from chapter_workflow import (
    acknowledge_review,
    chapter_status, handle_post_tool, pending_chapters, queue_index,
    record_chapter, record_context, record_graph, record_index,
)
from story_graph_nx import StoryGraph
from story_snapshot import StorySnapshot


def apply_graph(story, chapter, text="初見", replace=False):
    path = story / "runtime" / "story_graph.json"
    graph = StoryGraph(path)
    if path.exists():
        graph.load_flat(json.loads(path.read_text()))
    graph.apply_chapter_diff({"chapter": chapter, "characters_appeared": [
        {"name": "小青", "events": text},
    ]}, replace=replace)
    graph.save_flat()


def make_story(root, name="story", chapters=(1,)):
    story = root / "data" / "stories" / name
    (story / "outputs").mkdir(parents=True)
    (story / "runtime").mkdir()
    for ch in chapters:
        (story / "outputs" / f"chapter_{ch:03d}.md").write_text(f"第{ch}章正文", encoding="utf-8")
    (story / "runtime" / "story_log.md").write_text(
        "\n\n".join(f"## 第{ch}章：初見\n- 摘要：角色發現線索。" for ch in chapters),
        encoding="utf-8",
    )
    for chapter in chapters:
        apply_graph(story, chapter)
    return story


def test_log_edit_does_not_complete_graph_step(tmp_path):
    story = make_story(tmp_path)
    record_context(story, 1)
    result = handle_post_tool(tmp_path, {"session_id": "s1", "tool_input": {
        "file_path": str(story / "outputs" / "chapter_001.md")}})
    assert result[0]["missing"] == ["story_graph"]
    result = handle_post_tool(tmp_path, {"tool_input": {
        "file_path": str(story / "runtime" / "story_log.md")}})
    assert result[0]["missing"] == ["story_graph"]
    assert len(pending_chapters(tmp_path, "s1")) == 1
    assert record_graph(story, 1)["complete"]


def test_story_and_chapter_receipts_are_independent(tmp_path):
    first, second = make_story(tmp_path, "first"), make_story(tmp_path, "second")
    for story in (first, second):
        record_context(story, 1)
        record_chapter(story, 1, session_id="same-session")
    record_graph(second, 1)
    assert not chapter_status(first, 1)["complete"]
    assert chapter_status(second, 1)["complete"]
    assert [item["story_dir"] for item in pending_chapters(tmp_path)] == [str(first)]


def test_missing_context_is_not_inferred_from_existing_files(tmp_path):
    story = make_story(tmp_path)
    assert record_graph(story, 1)["missing"] == ["context"]


def test_rewrite_and_log_correction_invalidate_receipt(tmp_path):
    story = make_story(tmp_path)
    record_context(story, 1)
    record_graph(story, 1)
    record_index(story, 1, "ok")
    chapter = story / "outputs" / "chapter_001.md"
    chapter.write_text("改寫後的正文", encoding="utf-8")
    state = chapter_status(story, 1)
    assert state["missing"] == ["story_graph"]
    assert state["index"]["status"] == "stale"
    record_graph(story, 1)
    log = story / "runtime" / "story_log.md"
    log.write_text("## 第1章：初見\n- 摘要：新的線索。", encoding="utf-8")
    assert chapter_status(story, 1)["missing"] == ["story_graph"]


def test_later_chapter_preserves_prior_receipt_but_earlier_replace_invalidates_later(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    for ch in (1, 2):
        record_context(story, ch)
        record_graph(story, ch)
    apply_graph(story, 3)
    assert chapter_status(story, 1)["complete"]
    assert chapter_status(story, 2)["complete"]
    apply_graph(story, 1, "改寫", replace=True)
    assert not chapter_status(story, 2)["complete"]


def test_graph_deletion_cannot_preserve_completion(tmp_path):
    story = make_story(tmp_path)
    record_context(story, 1)
    record_graph(story, 1)
    (story / "runtime" / "story_graph.json").write_text("{}")
    assert not chapter_status(story, 1)["complete"]
    with pytest.raises(ValueError, match="validated diff"):
        record_graph(story, 1)


def test_index_unavailable_is_visible_and_nonblocking(tmp_path):
    story = make_story(tmp_path)
    record_context(story, 1)
    record_graph(story, 1)
    state = record_index(story, 1, "unavailable", "Embedding model not cached")
    assert state["complete"]
    assert state["index"]["status"] == "unavailable"
    assert pending_chapters(tmp_path) == []


def test_index_only_queued_after_required_steps(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("chapter_workflow.subprocess.Popen", lambda *a, **kw: calls.append((a, kw)))
    story = make_story(tmp_path)
    record_context(story, 1)
    assert not queue_index(story, 1)["complete"]
    assert not calls
    record_graph(story, 1)
    assert queue_index(story, 1)["index"]["status"] == "pending"
    queue_index(story, 1)
    assert len(calls) == 1
    assert "--allow-model-download" not in calls[0][0][0]


def set_memory_mode(story, mode):
    (story / "planning").mkdir(exist_ok=True)
    (story / "planning" / "memory_config.json").write_text(json.dumps({"mode": mode}))


def test_active_mode_skips_baseline_index_process(tmp_path, monkeypatch):
    monkeypatch.setattr("chapter_workflow.subprocess.Popen",
                        lambda *a, **kw: pytest.fail("active mode started baseline index"))
    story = make_story(tmp_path)
    set_memory_mode(story, "active")
    record_context(story, 1)
    record_graph(story, 1)
    state = queue_index(story, 1)
    assert state["complete"]
    assert state["index"]["status"] == "not_selected"
    assert "active" in state["index"]["detail"]
    assert not (story / "chroma").exists()
    assert not (story / "runtime" / "jev_memory").exists()


@pytest.mark.parametrize("mode", ["off", "shadow"])
def test_baseline_index_resumes_after_leaving_active(tmp_path, monkeypatch, mode):
    calls = []
    monkeypatch.setattr("chapter_workflow.subprocess.Popen", lambda *a, **kw: calls.append((a, kw)))
    story = make_story(tmp_path)
    record_context(story, 1)
    record_graph(story, 1)
    set_memory_mode(story, "active")
    assert queue_index(story, 1)["index"]["status"] == "not_selected"
    set_memory_mode(story, mode)
    assert queue_index(story, 1)["index"]["status"] == "pending"
    assert len(calls) == 1


@pytest.mark.parametrize("config", ['{"mode":"unknown"}', '{bad json', '[]'])
def test_invalid_memory_config_does_not_queue_index(tmp_path, monkeypatch, config):
    monkeypatch.setattr("chapter_workflow.subprocess.Popen",
                        lambda *a, **kw: pytest.fail("invalid config started baseline index"))
    story = make_story(tmp_path)
    record_context(story, 1)
    record_graph(story, 1)
    (story / "planning").mkdir()
    (story / "planning" / "memory_config.json").write_text(config)
    state = queue_index(story, 1)
    assert state["index"]["status"] == "error"
    assert "Cannot select memory route" in state["index"]["detail"]
    assert not (story / "chroma").exists()


def test_active_mode_does_not_complete_missing_workflow_steps(tmp_path, monkeypatch):
    monkeypatch.setattr("chapter_workflow.subprocess.Popen",
                        lambda *a, **kw: pytest.fail("active mode started baseline index"))
    story = make_story(tmp_path)
    set_memory_mode(story, "active")
    state = queue_index(story, 1)
    assert not state["complete"]
    assert state["missing"] == ["context", "story_graph"]
    assert state["index"]["status"] == "not_selected"


def test_stop_cli_blocks_incomplete_and_ignores_other_session(tmp_path):
    story = make_story(tmp_path, "story with ' quotes")
    record_context(story, 1)
    record_chapter(story, 1, session_id="session-a")
    script = Path(__file__).resolve().parents[2] / "scripts" / "chapter_workflow.py"
    command = [sys.executable, str(script), "stop", "--project-dir", str(tmp_path)]
    blocked = subprocess.run(command, input='{"session_id":"session-a"}',
                             text=True, capture_output=True)
    assert blocked.returncode == 2
    assert "story_graph" in blocked.stderr
    other = subprocess.run(command, input='{"session_id":"session-b"}',
                           text=True, capture_output=True)
    assert other.returncode == 0
    record_graph(story, 1)
    done = subprocess.run(command, input='{"session_id":"session-a"}',
                          text=True, capture_output=True)
    assert done.returncode == 0


def test_unrelated_story_log_append_preserves_receipt(tmp_path):
    story = make_story(tmp_path)
    record_context(story, 1)
    record_graph(story, 1)
    log = story / "runtime" / "story_log.md"
    log.write_text(log.read_text() + "\n\n## 第2章：後續\n- 摘要：新事件。")
    assert chapter_status(story, 1)["complete"]


def test_earlier_rewrite_requires_fresh_context_even_after_graph_retry(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    record_graph(story, 2)
    apply_graph(story, 1, "改寫", replace=True)
    state = record_graph(story, 2)
    assert state["missing"] == ["context"]
    assert record_context(story, 2)["complete"]


def test_first_chapter_context_survives_initial_graph_creation(tmp_path):
    story = tmp_path / "data" / "stories" / "new-story"
    record_context(story, 1)
    (story / "outputs").mkdir()
    (story / "outputs" / "chapter_001.md").write_text("章節正文")
    (story / "runtime" / "story_log.md").write_text("## 第1章：起點\n- 摘要：故事開始。")
    apply_graph(story, 1)
    assert record_graph(story, 1)["complete"]


def test_hook_ignores_chapter_named_test_artifacts(tmp_path):
    fixture = tmp_path / "tests" / "fixture" / "outputs" / "chapter_001.md"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("synthetic chapter")
    assert handle_post_tool(tmp_path, {"tool_input": {"file_path": str(fixture)}}) == []
    assert not (fixture.parent.parent / "runtime").exists()


def test_duplicate_log_entries_cannot_complete_chapter(tmp_path):
    story = make_story(tmp_path)
    record_context(story, 1)
    log = story / "runtime" / "story_log.md"
    log.write_text(log.read_text() + "\n\n## 第1章：另一版\n- 摘要：矛盾內容。")
    assert "story_log" in record_graph(story, 1)["missing"]


def test_prior_manuscript_edit_invalidates_downstream_context(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    assert record_graph(story, 2)["complete"]
    (story / "outputs" / "chapter_001.md").write_text("前章結尾改寫，紀錄尚未變更。")
    assert chapter_status(story, 2)["missing"] == ["context"]
    assert record_context(story, 2)["complete"]


def test_current_and_future_manuscripts_do_not_invalidate_context(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    (story / "outputs" / "chapter_002.md").write_text("使用上下文後寫好的本章。")
    (story / "outputs" / "chapter_003.md").write_text("未来章不能影響章前快照。")
    assert record_graph(story, 2)["complete"]


def test_prior_manuscript_deletion_invalidates_context(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    record_graph(story, 2)
    (story / "outputs" / "chapter_001.md").unlink()
    assert chapter_status(story, 2)["missing"] == ["context"]


def test_downstream_review_does_not_block_stop_but_current_direct_edit_does(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    for chapter in (1, 2):
        record_context(story, chapter)
        record_graph(story, chapter)
    apply_graph(story, 1, "前章新線索", replace=True)
    current, historical = chapter_status(story, 1), chapter_status(story, 2)
    assert current["lifecycle"] == "writing" and current["blocking"]
    assert not historical["complete"]
    assert historical["lifecycle"] == "needs_review" and not historical["blocking"]
    assert historical["review_allowed"]
    record_graph(story, 1)
    script = Path(__file__).resolve().parents[2] / "scripts" / "chapter_workflow.py"
    stop = subprocess.run([sys.executable, str(script), "stop", "--project-dir", str(tmp_path)],
                          input="{}", text=True, capture_output=True)
    assert stop.returncode == 0
    assert "needs review" in stop.stderr
    assert len(pending_chapters(tmp_path)) == 1


def test_review_acknowledgement_binds_current_evidence_and_expires_on_new_change(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    record_graph(story, 2)
    apply_graph(story, 1, "前章只是文字補充", replace=True)
    assert acknowledge_review(story, 2, "已核對前章補充；本章人物行動仍然成立")["complete"]
    receipt = json.loads((story / "runtime" / "chapter_workflow.json").read_text())["chapters"]["2"]
    snapshot = StorySnapshot(story)
    review = receipt["reviews"][-1]
    assert review["reason"].startswith("已核對")
    assert review["context_sha256"] == snapshot.context_signature(2)
    assert review["history_sha256"] == snapshot.graph_signature(2)
    assert review["chapter_diff_sha256"] == snapshot.chapter_diff_signature(2)
    assert review["evidence_sha256"]
    apply_graph(story, 1, "又新增實質改變", replace=True)
    assert chapter_status(story, 2)["lifecycle"] == "needs_review"
    assert not chapter_status(story, 2)["complete"]


@pytest.mark.parametrize("change", ["chapter", "log", "own_diff", "corrupt_graph"])
def test_review_cannot_bless_direct_changes_or_corrupt_graph(tmp_path, change):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    record_graph(story, 2)
    if change == "chapter":
        (story / "outputs" / "chapter_002.md").write_text("直接改寫正文")
    elif change == "log":
        log = story / "runtime" / "story_log.md"
        log.write_text(log.read_text().replace("## 第2章：初見", "## 第2章：新的標題"))
    elif change == "own_diff":
        apply_graph(story, 2, "本章也有新事實", replace=True)
    else:
        (story / "runtime" / "story_graph.json").write_text("{not json")
    state = chapter_status(story, 2)
    assert state["lifecycle"] == "writing" and state["blocking"]
    assert not state["review_allowed"]
    workflow_path = story / "runtime" / "chapter_workflow.json"
    previous = workflow_path.read_bytes()
    with pytest.raises(ValueError, match="only unchanged"):
        acknowledge_review(story, 2, "已看過")
    assert workflow_path.read_bytes() == previous


def test_review_requires_reason_and_current_snapshot(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    record_graph(story, 2)
    (story / "outputs" / "chapter_001.md").write_text("前章第一次修改")
    snapshot = StorySnapshot(story)
    with pytest.raises(ValueError, match="nonempty reason"):
        acknowledge_review(story, 2, " ")
    (story / "outputs" / "chapter_001.md").write_text("前章第二次修改")
    previous = (story / "runtime" / "chapter_workflow.json").read_bytes()
    with pytest.raises(ValueError, match="changed during review"):
        acknowledge_review(story, 2, "核對第一版", snapshot=snapshot)
    assert (story / "runtime" / "chapter_workflow.json").read_bytes() == previous


def test_review_cli_records_reason_and_unblocks_review_state(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    record_graph(story, 2)
    (story / "outputs" / "chapter_001.md").write_text("前文補充場景")
    script = Path(__file__).resolve().parents[2] / "scripts" / "chapter_workflow.py"
    result = subprocess.run([sys.executable, str(script), "review", "--story-dir", str(story),
                             "--chapter-num", "2", "--reason", "已核對前文場景補充"],
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["lifecycle"] == "complete"


def test_background_index_bookkeeping_does_not_reopen_historical_chapter(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    record_graph(story, 2)
    (story / "outputs" / "chapter_001.md").write_text("前文變更")
    assert record_chapter(story, 2, story / "outputs" / "chapter_002.md")["lifecycle"] == "needs_review"
    assert record_index(story, 2, "ok")["lifecycle"] == "needs_review"
    assert not chapter_status(story, 2)["complete"]


def test_reopening_context_marks_historical_review_as_active_writing(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    record_graph(story, 2)
    apply_graph(story, 1, "改變前提", replace=True)
    assert chapter_status(story, 2)["lifecycle"] == "needs_review"
    state = record_context(story, 2)
    assert state["lifecycle"] == "writing" and state["blocking"]
    with pytest.raises(ValueError, match="only unchanged"):
        acknowledge_review(story, 2, "不能跳過已重開的寫作步驟")
    assert record_graph(story, 2)["complete"]


def test_context_receipt_cannot_describe_a_changed_snapshot(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    snapshot = StorySnapshot(story)
    (story / "outputs" / "chapter_001.md").write_text("context 建立後變更")
    with pytest.raises(ValueError, match="changed while assembling"):
        record_context(story, 2, snapshot=snapshot)
    assert not (story / "runtime" / "chapter_workflow.json").exists()


def test_legacy_completed_receipt_derives_review_without_writing_migration(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    record_graph(story, 2)
    path = story / "runtime" / "chapter_workflow.json"
    state = json.loads(path.read_text())
    state["chapters"]["2"].pop("completion")
    path.write_text(json.dumps(state))
    previous = path.read_bytes()
    assert chapter_status(story, 2)["complete"]
    assert path.read_bytes() == previous
    (story / "outputs" / "chapter_001.md").write_text("只改前文，graph 沒變")
    assert chapter_status(story, 2)["lifecycle"] == "needs_review"
    assert path.read_bytes() == previous
    assert acknowledge_review(story, 2, "前文補充不影響本章")["complete"]
    assert "completion" in json.loads(path.read_text())["chapters"]["2"]


def test_legacy_prefix_drift_cannot_invent_unchanged_local_diff(tmp_path):
    story = make_story(tmp_path, chapters=(1, 2))
    record_context(story, 2)
    record_graph(story, 2)
    path = story / "runtime" / "chapter_workflow.json"
    state = json.loads(path.read_text())
    state["chapters"]["2"].pop("completion")
    path.write_text(json.dumps(state))
    apply_graph(story, 1, "歷史已經改過", replace=True)
    state = chapter_status(story, 2)
    assert state["lifecycle"] == "writing" and not state["review_allowed"]
    assert "No completion receipt" in state["review_unavailable_reason"]


def test_pending_reads_each_story_once_for_all_chapters(tmp_path, monkeypatch):
    import chapter_workflow

    story = make_story(tmp_path, chapters=(1, 2, 3))
    for chapter in (1, 2, 3):
        record_context(story, chapter)
        record_graph(story, chapter)
    reads = []
    original_read = Path.read_bytes

    def tracked_read(path):
        reads.append(path)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", tracked_read)
    assert chapter_workflow.pending_chapters(tmp_path) == []
    assert reads.count(story / "runtime" / "story_graph.json") == 1
    assert reads.count(story / "runtime" / "story_log.md") == 1
    assert reads.count(story / "runtime" / "chapter_workflow.json") == 1
    for chapter in (1, 2, 3):
        assert reads.count(story / "outputs" / f"chapter_{chapter:03d}.md") == 1
