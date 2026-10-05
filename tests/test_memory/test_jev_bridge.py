"""Bridge contracts and opt-in tests of the actual upstream Jev-Mem worker."""

import json
import os
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from memory import jev_bridge as bridge
from scripts.chapter_workflow import record_context, record_graph
from scripts.story_graph_nx import StoryGraph


def make_story(tmp_path, *, name="synthetic", mode="shadow", mock=True, config=None):
    story = tmp_path / name
    for folder in ("planning", "runtime", "outputs"):
        (story / folder).mkdir(parents=True)
    (story / "runtime" / "story_log.md").write_text("# Story log\n", encoding="utf-8")
    (story / "runtime" / "story_graph.json").write_text("{}", encoding="utf-8")
    values = {"mode": mode, "mock": mock, **(config or {})}
    (story / "planning" / "memory_config.json").write_text(json.dumps(values), encoding="utf-8")
    return story


def add_chapter(story, chapter, summary):
    (story / "outputs" / f"chapter_{chapter:03d}.md").write_text(summary, encoding="utf-8")
    log = story / "runtime" / "story_log.md"
    log.write_text(log.read_text(encoding="utf-8") +
                   f"\n## 第{chapter}章：Synthetic {chapter}\n- 摘要：{summary}\n", encoding="utf-8")
    record_context(story, chapter)
    update_graph(story, chapter, summary)


def update_graph(story, chapter, summary):
    graph_path = story / "runtime" / "story_graph.json"
    graph = StoryGraph(graph_path)
    graph.load_flat(json.loads(graph_path.read_text(encoding="utf-8")))
    graph.apply_chapter_diff({"chapter": chapter, "characters_appeared": [
        {"name": "Mina", "events": summary}]}, replace=True)
    graph.save_flat()
    assert record_graph(story, chapter)["complete"]


@pytest.fixture
def fake_backend(monkeypatch):
    calls = []
    monkeypatch.setattr(bridge, "_backend", lambda c: {"mock": c["mock"], "source_hash": "fake"})

    def run(config, backend, request):
        calls.append(request)
        if request["action"] == "query":
            return {"status": "ok", "evidence": [{"chapter": r["chapter"], "text": r["text"]}
                                                   for r in request["allowed"]], "trace": {}}
        return {"status": "ok", "trace": {"controller": "jev-mem"}}

    monkeypatch.setattr(bridge, "_run_worker", run)
    return calls


def test_off_has_no_worker_or_files(tmp_path, monkeypatch):
    story = tmp_path / "absent"
    monkeypatch.setattr(bridge, "_run_worker", lambda *a: pytest.fail("off started a worker"))
    assert bridge.query_memory(story, 3, "Mina")["status"] == "disabled"
    assert bridge.sync_chapter(story, 1)["status"] == "disabled"
    assert not story.exists()


def test_sync_requires_current_complete_receipt(tmp_path, fake_backend):
    story = make_story(tmp_path)
    add_chapter(story, 1, "Mina hides a key.")
    (story / "outputs" / "chapter_001.md").write_text("A changed manuscript.", encoding="utf-8")
    with pytest.raises(bridge.MemoryBridgeError, match="complete workflow receipt"):
        bridge.sync_chapter(story, 1)
    assert not fake_backend


def test_duplicate_noop_revision_rebuild_retains_previous_generation(tmp_path, fake_backend):
    story = make_story(tmp_path)
    add_chapter(story, 1, "Mina hides a key.")
    first = bridge.sync_chapter(story, 1)
    assert bridge.sync_chapter(story, 1)["status"] == "unchanged"
    assert len(fake_backend) == 1
    add_chapter(story, 2, "Mina searches for a key.")
    second = bridge.sync_chapter(story, 2)
    assert not second["rebuilt"]
    assert len(fake_backend[-1]["observations"]) == 1
    (story / "outputs" / "chapter_001.md").write_text("Mina returns the key.", encoding="utf-8")
    log = story / "runtime" / "story_log.md"
    log.write_text(log.read_text().replace("Mina hides a key.", "Mina returns the key."), encoding="utf-8")
    update_graph(story, 1, "Mina returns the key.")
    revised = bridge.sync_chapter(story, 1)
    # Revising an earlier graph invalidates downstream completion receipts.
    assert revised["rebuilt"] and revised["observations"] == 1
    assert revised["stale_chapters_excluded"] == [2]
    assert [r["chapter"] for r in fake_backend[-1]["observations"]] == [1]
    assert (story / "runtime" / "jev_memory" / first["generation"] / "manifest.json").exists()
    assert (story / "runtime" / "jev_memory" / second["generation"] / "manifest.json").exists()


def test_query_excludes_future_and_stale_before_worker(tmp_path, fake_backend):
    story = make_story(tmp_path)
    for n in (1, 2, 3):
        add_chapter(story, n, f"Mina chapter {n}.")
        bridge.sync_chapter(story, n)
    result = bridge.query_memory(story, 3, "Mina")
    assert [r["chapter"] for r in fake_backend[-1]["allowed"]] == [1, 2]
    assert [r["chapter"] for r in result["evidence"]] == [1, 2]
    call_count = len(fake_backend)
    (story / "outputs" / "chapter_001.md").write_text("Changed", encoding="utf-8")
    result = bridge.query_memory(story, 3, "Mina")
    assert result["mode"] == "shadow"
    # An earlier manuscript change also invalidates downstream context receipts.
    assert len(fake_backend) == call_count
    assert result["trace"]["stale_chapters_excluded"] == [1, 2]
    assert result["evidence"] == []


def test_failed_rebuild_keeps_current_pointer(tmp_path, fake_backend, monkeypatch):
    story = make_story(tmp_path)
    add_chapter(story, 1, "Mina hides a key.")
    bridge.sync_chapter(story, 1)
    pointer = story / "runtime" / "jev_memory" / "current.json"
    before = pointer.read_bytes()
    add_chapter(story, 2, "Mina returns a key.")
    def fail(*args):
        raise bridge.MemoryBridgeError("Synthetic interruption")
    monkeypatch.setattr(bridge, "_run_worker", fail)
    with pytest.raises(bridge.MemoryBridgeError, match="interruption"):
        bridge.sync_chapter(story, 2)
    assert pointer.read_bytes() == before


def test_mock_and_live_cannot_mix(tmp_path, fake_backend):
    story = make_story(tmp_path)
    add_chapter(story, 1, "Mina hides a key.")
    bridge.sync_chapter(story, 1)
    path = story / "planning" / "memory_config.json"
    path.write_text(json.dumps({"mode": "active", "mock": False}), encoding="utf-8")
    with pytest.raises(bridge.MemoryBridgeError, match="Mock and live"):
        bridge.sync_chapter(story, 1)
    assert bridge.query_memory(story, 2, "Mina")["status"] == "error"


def test_query_withholds_result_if_source_changes_during_worker(tmp_path, fake_backend, monkeypatch):
    story = make_story(tmp_path)
    add_chapter(story, 1, "Mina hides a key.")
    bridge.sync_chapter(story, 1)
    def change_during_query(*args):
        (story / "outputs" / "chapter_001.md").write_text("Mina now gives the key back.", encoding="utf-8")
        return {"status": "ok", "evidence": [{"chapter": 1, "text": "Old source"}], "trace": {}}
    monkeypatch.setattr(bridge, "_run_worker", change_during_query)
    result = bridge.query_memory(story, 2, "Mina")
    assert result["status"] == "stale" and not result["evidence"]
    assert result["trace"]["sources_changed_during_query"] == [1]


@pytest.mark.parametrize("change", ["log", "workflow", "graph"])
def test_query_revalidates_all_receipt_sources_after_worker(tmp_path, fake_backend, monkeypatch, change):
    story = make_story(tmp_path)
    add_chapter(story, 1, "Mina hides a key.")
    bridge.sync_chapter(story, 1)

    def change_during_query(*args):
        if change == "log":
            (story / "runtime" / "story_log.md").write_text("## 第1章：Changed\n- 摘要：Changed")
        elif change == "workflow":
            path = story / "runtime" / "chapter_workflow.json"
            state = json.loads(path.read_text())
            state["chapters"]["1"]["context"]["prior_story_sha256"] = "changed"
            path.write_text(json.dumps(state))
        else:
            path = story / "runtime" / "story_graph.json"
            graph = json.loads(path.read_text())
            graph["characters"]["Mina"]["events"] = "Only the snapshot changed"
            path.write_text(json.dumps(graph))
        return {"status": "ok", "evidence": [{"chapter": 1, "text": "Old"}], "trace": {}}

    monkeypatch.setattr(bridge, "_run_worker", change_during_query)
    result = bridge.query_memory(story, 2, "Mina")
    assert result["status"] == "stale" and not result["evidence"]


def test_query_reads_each_story_source_once_per_validation_phase(tmp_path, fake_backend, monkeypatch):
    story = make_story(tmp_path)
    for chapter in range(1, 7):
        add_chapter(story, chapter, f"Mina chapter {chapter}.")
        bridge.sync_chapter(story, chapter)
    reads = {}
    original = Path.read_bytes

    def counted(path):
        if path.parent in (story / "runtime", story / "outputs"):
            reads[str(path)] = reads.get(str(path), 0) + 1
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", counted)
    result = bridge.query_memory(story, 7, "Mina")
    assert result["status"] == "ok"
    assert max(reads.values()) == 2  # Initial snapshot + independent post-worker view.
    assert len(reads) == 9


def test_crlf_manuscripts_do_not_change_existing_memory_identity(tmp_path, fake_backend):
    story = make_story(tmp_path)
    add_chapter(story, 1, "Mina hides a key.")
    (story / "outputs" / "chapter_001.md").write_bytes(b"Mina hides a key.\r\n")
    record_graph(story, 1)
    bridge.sync_chapter(story, 1)
    assert bridge.sync_chapter(story, 1)["status"] == "unchanged"
    assert bridge.query_memory(story, 2, "Mina")["status"] == "ok"


def test_busy_sync_does_not_block_optional_recall(tmp_path, fake_backend):
    story = make_story(tmp_path)
    add_chapter(story, 1, "Mina hides a key.")
    bridge.sync_chapter(story, 1)
    with bridge._lock(story / "runtime" / "jev_memory", exclusive=True):
        result = bridge.query_memory(story, 2, "Mina")
    assert result["status"] == "error" and "in progress" in result["error"]
    assert len(fake_backend) == 1


def test_explicit_rebuild_can_replace_broken_derived_files(tmp_path, fake_backend):
    story = make_story(tmp_path)
    add_chapter(story, 1, "Mina hides a key.")
    first = bridge.sync_chapter(story, 1)
    result = bridge.sync_chapter(story, 1, rebuild=True)
    assert result["rebuilt"] and result["generation"] != first["generation"]
    assert fake_backend[-1]["load_dir"] is None
    assert len(fake_backend[-1]["observations"]) == 1


@pytest.mark.parametrize("response", [[], {"status": "ok"},
    {"status": "ok", "trace": {"controller": "jev-mem", "llm_calls": 0}, "evidence": "wrong"},
    {"status": "ok", "trace": {"controller": "jev-mem", "llm_calls": 0},
     "evidence": [{"chapter": 99, "text": "Future secret"}]}])
def test_malformed_worker_response_fails_closed(response, monkeypatch):
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw:
                        SimpleNamespace(returncode=0, stdout=json.dumps(response)))
    with pytest.raises(bridge.MemoryBridgeError):
        bridge._run_worker({"timeout_seconds": 5}, {"source": "/unused", "python": sys.executable},
                           {"action": "query", "allowed": [], "limit": 3})


def test_malformed_current_pointer_returns_query_error(tmp_path, fake_backend):
    story = make_story(tmp_path)
    add_chapter(story, 1, "Mina hides a key.")
    bridge.sync_chapter(story, 1)
    (story / "runtime" / "jev_memory" / "current.json").write_text("[]", encoding="utf-8")
    result = bridge.query_memory(story, 2, "Mina")
    assert result["status"] == "error" and not result["evidence"]


def test_backend_keeps_virtualenv_python_path(tmp_path, monkeypatch):
    source = tmp_path / "upstream"
    (source / "jev_mem").mkdir(parents=True)
    (source / "memory").mkdir()
    (source / "jev_mem" / "system.py").write_text("")
    (source / "memory" / "memory_builder.py").write_text("")
    python = tmp_path / "python"
    python.symlink_to(sys.executable)
    config = {"python": str(python), "source": str(source), "mock": True,
              "encoder_model": "any", "jev_model": "jev-latest"}
    assert bridge._backend(config)["python"] == str(python)


@pytest.mark.skipif(os.environ.get("NOVEL_TEST_JEV") != "1",
                    reason="Set NOVEL_TEST_JEV=1 and JEV_MEM_PYTHON/SOURCE for actual upstream mock")
def test_actual_upstream_mock_isolated_recall_and_prefix(tmp_path):
    assert os.environ.get("JEV_MEM_PYTHON") and os.environ.get("JEV_MEM_SOURCE")
    story = make_story(tmp_path, mode="active")
    for n, text in enumerate(("Mina keeps the brass key.", "Mina gives the brass key to Leo.",
                              "Future secret: Mina destroys the brass key."), start=1):
        add_chapter(story, n, text)
        assert bridge.sync_chapter(story, n)["stored"]
    store = story / "runtime" / "jev_memory"
    pointer = json.loads((store / "current.json").read_text())
    generation = store / pointer["generation"]
    before = {p.name: p.read_bytes() for p in generation.iterdir() if p.is_file()}
    result = bridge.query_memory(story, 3, "Mina brass key", limit=3)
    assert result["status"] == "ok", result
    assert result["evidence"] and all(item["chapter"] < 3 for item in result["evidence"])
    assert all("Future secret" not in item["text"] for item in result["evidence"])
    assert result["trace"]["controller"] == "jev-mem"
    assert result["trace"]["llm_calls"] == 0
    assert result["trace"]["excluded_nodes"] == 1
    assert before == {p.name: p.read_bytes() for p in generation.iterdir() if p.is_file()}
    assert bridge.sync_chapter(story, 3)["status"] == "unchanged"
    other = make_story(tmp_path, name="other", mode="active")
    add_chapter(other, 1, "Mina owns only a silver key.")
    bridge.sync_chapter(other, 1)
    other_result = bridge.query_memory(other, 2, "Mina key")
    assert other_result["status"] == "ok", other_result
    assert all("brass" not in item["text"] for item in other_result["evidence"])
