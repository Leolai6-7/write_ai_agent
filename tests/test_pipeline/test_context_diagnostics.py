"""Text and JSON hand off omitted source navigation, never omitted evidence."""

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts.context_bundle import ContextBlock, SourceRef, build_context_bundle, format_context_diagnostics


def test_omitted_source_is_navigable_without_omitted_prose():
    ref = SourceRef("outputs/chapter_001.md", 4, 7, "a" * 64)
    bundle = build_context_bundle([
        ContextBlock("beat", "author_intent", "目的", required=True),
        ContextBlock("narrative:belief", "pov_knowledge", "PRIVATE_PROSE" * 200,
                     sources=(ref,)),
    ], max_chars=400)
    appendix = format_context_diagnostics(bundle.metadata)
    assert "narrative:belief" in appendix
    assert "char_budget" in appendix
    assert "outputs/chapter_001.md:4-7" in appendix
    assert "PRIVATE_PROSE" not in appendix + json.dumps(bundle.metadata)
    assert bundle.metadata["omitted_sources"]["narrative:belief"] == [ref.as_dict()]
    assert len(bundle.text) <= 400


def test_invalid_and_wrong_pov_only_report_reason_not_source_or_prose():
    metadata = {"narrative_excluded": [
        {"id": "old-belief", "reason": "retired", "text": "PRIVATE_PROSE"},
        {"id": "other-mind", "reason": "wrong_pov"},
    ], "graph_excluded": [{"key": "value:door", "reason": "source_needs_review"}]}
    appendix = format_context_diagnostics(metadata)
    assert all(value in appendix for value in ("old-belief", "retired", "other-mind", "wrong_pov"))
    assert "value:door" in appendix and "source_needs_review" in appendix
    assert "PRIVATE_PROSE" not in appendix
    assert "不可當有效知情補回" in appendix


def test_diagnostic_preview_is_bounded_without_truncating_identifiers():
    rows = [{"key": f"narrative:{n}", "reason": "char_budget"} for n in range(100)]
    metadata = {"omitted": rows}
    appendix = format_context_diagnostics(metadata, max_chars=500, max_items=3)
    assert len(appendix) <= 500
    assert "共 100 筆" in appendix and "/100 筆" in appendix
    assert appendix.count("- narrative:") <= 3
    huge = "KEY_" + "x" * 1000
    appendix = format_context_diagnostics({"omitted": [{"key": huge, "reason": "char_budget"}]},
                                         max_chars=400)
    assert "顯示 0/1" in appendix
    assert "KEY_" not in appendix and len(appendix) <= 400


def test_no_omissions_need_no_appendix():
    assert format_context_diagnostics({}) == ""


@pytest.mark.parametrize("kwargs", [{"max_chars": 0}, {"max_chars": True}, {"max_items": 0}])
def test_bad_diagnostic_bounds_rejected(kwargs):
    with pytest.raises(ValueError):
        format_context_diagnostics({}, **kwargs)


def test_public_text_cli_reports_omitted_log_and_exact_source(tmp_path):
    for directory in ("planning", "runtime", "outputs"):
        (tmp_path / directory).mkdir()
    (tmp_path / "planning/arc_plan_1.yaml").write_text(yaml.safe_dump({"chapters": [
        {"chapter": 2, "line": "main", "objective": "回訪"},
    ]}), encoding="utf-8")
    (tmp_path / "runtime/story_log.md").write_text(
        "## 第1章：先前\n- 摘要：" + "PRIVATE_LOG_PROSE" * 500 + "\n", encoding="utf-8")
    script = Path(__file__).resolve().parents[2] / "scripts/assemble_context.py"
    command = [sys.executable, str(script), "--story-dir", str(tmp_path),
               "--chapter", "2", "--max-context-chars", "2200"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=True)
    assert "CONTEXT DIAGNOSTICS" in result.stdout
    assert "log:1 | char_budget | runtime/story_log.md:1-2" in result.stdout
    assert "PRIVATE_LOG_PROSE" not in result.stdout
    data = json.loads(subprocess.run([*command, "--format", "json"], capture_output=True,
                                     text=True, timeout=10, check=True).stdout)
    assert data["context_metadata"]["omitted_sources"]["log:1"][0]["start_line"] == 1
    assert "PRIVATE_LOG_PROSE" not in json.dumps(data)
    assert len(data["context_package"]) <= 2200
