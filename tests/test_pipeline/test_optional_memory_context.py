"""The experimental memory backend cannot silently contaminate a control run."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import assemble_context as context
from assemble_context import recall_optional_memory


def answer(mode="active", status="ok"):
    return {"mode": mode, "status": status,
            "trace": {"mock": True},
            "evidence": [{"chapter": 1, "text": "先前留下的暗號", "source_path": "story_log.md"},
                         {"chapter": 3, "text": "當章洩漏"},
                         {"chapter": 9, "text": "未來洩漏"}]}


def test_shadow_results_never_enter_text_or_context_json(tmp_path):
    metadata, text = recall_optional_memory(tmp_path, 3, {}, lambda *a, **k: answer("shadow"))
    assert metadata == {"mode": "shadow", "status": "ok", "trace": {"mock": True}}
    assert text == ""
    assert "暗號" not in str(metadata)


def test_active_evidence_has_sources_and_obeys_time_boundary(tmp_path):
    calls = []

    def query(*args, **kwargs):
        calls.append(kwargs)
        return answer()

    metadata, text = recall_optional_memory(tmp_path, 3, {"objective": "找暗號" * 1000}, query)
    assert "先前留下的暗號" in text and "chapter_001.md" in text
    assert "洩漏" not in text
    assert len(metadata["evidence"]) == 1
    assert calls[0]["before_chapter"] == 3
    assert len(calls[0]["query"]) <= 1200


def test_unavailable_backend_keeps_original_context_usable(tmp_path):
    def unavailable(*args, **kwargs):
        raise RuntimeError("backend failed")

    metadata, text = recall_optional_memory(tmp_path, 3, {}, unavailable)
    assert metadata == {"status": "unavailable", "error": "RuntimeError"}
    assert text == ""


def test_default_off_never_creates_memory_files(tmp_path):
    metadata, text = recall_optional_memory(tmp_path, 3, {})
    assert metadata["mode"] == "off" and text == ""
    assert not (tmp_path / "runtime").exists()


def configure(story, mode):
    (story / "planning").mkdir(exist_ok=True)
    (story / "planning" / "memory_config.json").write_text(json.dumps({"mode": mode}))


@pytest.mark.parametrize("mode", ["off", "shadow", "active"])
def test_mode_selects_exactly_one_writer_evidence_backend(tmp_path, monkeypatch, mode):
    configure(tmp_path, mode)
    calls = []

    def semantic(*args):
        calls.append("chroma")
        return {"status": "ok", "results": [
            {"chapter_id": 1, "summary": "BASELINE_ONLY", "source": "chapter_001.md"}]}

    def jev(*args):
        calls.append("jev")
        # Deliberately provide evidence even in shadow to test orchestration's guard.
        return {"mode": mode, "status": "ok", "evidence": ["JEV_ONLY"]}, "JEV_ONLY"

    monkeypatch.setattr(context, "recall_semantic_candidates", semantic)
    monkeypatch.setattr(context, "recall_optional_memory", jev)
    result = context.recall_chapter_memory(tmp_path, 3, {})
    if mode == "active":
        assert calls == ["jev"]
        assert result["selected_backend"] == "jev-mem"
        assert result["semantic_recall"]["status"] == "not_selected"
        assert "JEV_ONLY" in result["text"] and "BASELINE_ONLY" not in result["text"]
    else:
        assert calls == (["chroma"] if mode == "off" else ["chroma", "jev"])
        assert result["selected_backend"] == "chroma"
        assert "BASELINE_ONLY" in result["text"] and "JEV_ONLY" not in str(result)


@pytest.mark.parametrize("status", ["empty", "error", "stale", "unavailable"])
def test_active_failure_does_not_silently_fallback_to_chroma(tmp_path, monkeypatch, status):
    configure(tmp_path, "active")
    monkeypatch.setattr(context, "recall_semantic_candidates",
                        lambda *args: pytest.fail("active must never load Chroma"))
    monkeypatch.setattr(context, "recall_optional_memory",
                        lambda *args: ({"mode": "active", "status": status}, ""))
    result = context.recall_chapter_memory(tmp_path, 3, {})
    assert result["selected_backend"] == "jev-mem"
    assert result["jev_memory"]["status"] == status
    assert status in result["text"]


def test_invalid_config_invokes_neither_backend(tmp_path, monkeypatch):
    configure(tmp_path, "not-a-mode")
    for function in ("recall_semantic_candidates", "recall_optional_memory"):
        monkeypatch.setattr(context, function, lambda *args: pytest.fail("invalid config called backend"))
    result = context.recall_chapter_memory(tmp_path, 3, {})
    assert result["selected_backend"] == "none"
    assert result["jev_memory"]["status"] == "error"


def test_changed_mode_during_shadow_cannot_leak_evidence(tmp_path, monkeypatch):
    configure(tmp_path, "shadow")
    monkeypatch.setattr(context, "recall_semantic_candidates",
                        lambda *args: {"status": "empty", "results": []})
    monkeypatch.setattr(context, "recall_optional_memory", lambda *args: (
        {"mode": "active", "status": "ok", "evidence": ["SHADOW_LEAK"]}, "SHADOW_LEAK"))
    result = context.recall_chapter_memory(tmp_path, 3, {})
    assert result["jev_memory"]["status"] == "configuration_changed"
    assert "SHADOW_LEAK" not in str(result)


def test_backend_error_without_mode_keeps_real_error(tmp_path, monkeypatch):
    configure(tmp_path, "active")
    monkeypatch.setattr(context, "recall_semantic_candidates",
                        lambda *args: pytest.fail("must not load baseline"))
    monkeypatch.setattr(context, "recall_optional_memory", lambda *args: (
        {"status": "unavailable", "error": "RuntimeError"}, ""))
    result = context.recall_chapter_memory(tmp_path, 3, {})
    assert result["jev_memory"] == {
        "mode": "active", "status": "unavailable", "error": "RuntimeError"}
