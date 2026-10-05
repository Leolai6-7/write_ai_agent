"""Index receipts use real summaries and distinguish missing infrastructure."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from chapter_workflow import chapter_status
from index_chapter import index_chapter, parse_story_log_entry


def fixture_story(tmp_path, log="## 第1章：初見\n- 摘要：角色發現線索。\n- 角色變化：伊澤開始調查"):
    (tmp_path / "runtime").mkdir()
    (tmp_path / "outputs").mkdir()
    (tmp_path / "runtime" / "story_log.md").write_text(log, encoding="utf-8")
    chapter = tmp_path / "outputs" / "chapter_001.md"
    chapter.write_text("章節正文", encoding="utf-8")
    return chapter


def test_missing_summary_is_error_not_placeholder_success(tmp_path):
    chapter = fixture_story(tmp_path, "## 第1章：初見\n- 摘要：\n- 角色變化：伊澤開始調查")
    calls = []
    result = index_chapter(tmp_path, 1, chapter, retriever_factory=lambda *a, **k: calls.append(1))
    assert result["status"] == "error"
    assert not calls
    assert chapter_status(tmp_path, 1)["index"]["status"] == "error"


def test_dependency_failure_saved_as_unavailable(tmp_path):
    chapter = fixture_story(tmp_path)
    def unavailable(*args, **kwargs):
        raise ModuleNotFoundError("No module named chromadb")
    result = index_chapter(tmp_path, 1, chapter, retriever_factory=unavailable)
    assert result["status"] == "unavailable"
    assert chapter_status(tmp_path, 1)["index"]["status"] == "unavailable"


def test_success_stores_exact_summary_and_defaults_to_local_model(tmp_path):
    chapter = fixture_story(tmp_path)
    calls = []
    class Retriever:
        def __init__(self, path, **kwargs):
            calls.append(kwargs)
        def add_chapter(self, **kwargs):
            calls.append(kwargs)
    result = index_chapter(tmp_path, 1, chapter, retriever_factory=Retriever)
    assert result["status"] == "ok"
    assert calls[0] == {"allow_model_download": False}
    assert calls[1]["summary"] == "角色發現線索。"
    assert calls[1]["characters"] == ["伊澤"]
    assert chapter_status(tmp_path, 1)["index"]["status"] == "ok"


def test_content_change_during_index_is_not_reported_current(tmp_path):
    chapter = fixture_story(tmp_path)
    class Retriever:
        def __init__(self, *args, **kwargs):
            pass
        def add_chapter(self, **kwargs):
            chapter.write_text("索引期間已改寫的正文", encoding="utf-8")
    result = index_chapter(tmp_path, 1, chapter, retriever_factory=Retriever)
    assert result["status"] == "stale"


def test_entry_parser_keeps_multiline_summary_and_chapter_boundary():
    entry = parse_story_log_entry("## 第 1 章：初見\n- 摘要：第一行\n  第二行\n"
                                  "- 角色變化：角色改變\n## 第2章：後續\n- 摘要：別章", 1)
    assert entry["summary"] == "第一行\n  第二行"
    assert entry["title"] == "初見"


def test_duplicate_log_entries_are_ambiguous():
    assert parse_story_log_entry("## 第1章：初見\n- 摘要：第一版\n"
                                 "## 第1章：初見\n- 摘要：第二版", 1) is None
