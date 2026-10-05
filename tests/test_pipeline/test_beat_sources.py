"""YAML beat citations end at content, not the next chapter's indentation."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import assemble_context as context  # noqa: E402


PATH = Path("/synthetic-story/planning/arc_plan_1.yaml")


class MemorySnapshot:
    def __init__(self, text):
        self.text = text

    def read_text(self, path):
        assert path == PATH
        return self.text


def source(text, chapter=2):
    return context._yaml_beat_source(PATH, chapter, MemorySnapshot(text))


def cited(text, ref):
    assert ref["path"] == "planning/arc_plan_1.yaml"
    return "\n".join(text.splitlines()[ref["start_line"] - 1:ref["end_line"]])


@pytest.mark.parametrize("indent", [0, 2, 4])
def test_block_mapping_end_mark_does_not_include_next_chapter(indent):
    pad = " " * indent
    text = "chapters:\n" + "".join(
        f"{pad}- chapter: {n}\n{pad}  title: 章{n}\n" for n in (1, 2, 3)
    )
    ref = source(text)
    assert (ref["start_line"], ref["end_line"]) == (4, 5)
    assert cited(text, ref) == f"{pad}- chapter: 2\n{pad}  title: 章2"
    assert "chapter: 3" not in cited(text, ref)


def test_trailing_comments_and_blank_lines_are_not_part_of_the_beat():
    text = ("chapters:\n  - chapter: 2\n    title: 本章\n"
            "\n  # 第三章才發生的事\n\n  - chapter: 3\n    title: 後章\n")
    ref = source(text)
    assert (ref["start_line"], ref["end_line"]) == (2, 3)
    assert "第三章" not in cited(text, ref)


@pytest.mark.parametrize("chomping", ["|", "|-", "|+", ">"])
def test_multiline_scalar_retains_all_content_without_trailing_whitespace(chomping):
    text = (f"chapters:\n  - chapter: 2\n    objective: {chomping}\n"
            "      第一段\n\n      第二段\n\n\n"
            "  # 下一章\n  - chapter: 3\n    title: 未來\n")
    ref = source(text)
    assert (ref["start_line"], ref["end_line"]) == (2, 6)
    assert "第一段\n\n      第二段" in cited(text, ref)
    assert "下一章" not in cited(text, ref)


def test_multiline_quoted_and_nested_values_end_before_next_entry():
    text = ("chapters:\n  - chapter: 2\n    title: '本章\n      標題'\n"
            "    key_events:\n      - 找到信\n      - 查看印章\n"
            "    foreshadowing:\n      - thread: 1\n        action: hint\n"
            "  - chapter: 3\n    title: 未來\n")
    ref = source(text)
    assert (ref["start_line"], ref["end_line"]) == (2, 10)
    assert cited(text, ref).endswith("action: hint")


@pytest.mark.parametrize("text", [
    "chapters: [{chapter: 1, title: 前章}, {chapter: 2, title: 本章}, {chapter: 3, title: 後章}]\n",
    "chapters: [\n  {chapter: 2, title: 本章}, {chapter: 3, title: 後章}\n]\n",
    "chapters: [\n  {chapter: 1, title: 前章}, {chapter: 2, title: 本章}\n]\n",
    "chapters: [\n  {chapter: 2,\n   title: 本章}, {chapter: 3, title: 後章}\n]\n",
    "chapters: [\n  {chapter: 2, title: 本章}]\n",
])
def test_shared_flow_boundary_lines_do_not_get_an_unsafe_reference(text):
    assert source(text) is None


@pytest.mark.parametrize("text,expected", [
    ("chapters: [\n  {chapter: 1, title: 前章},\n  {chapter: 2, title: 本章},\n  {chapter: 3, title: 後章}\n]\n", (3, 3)),
    ("chapters:\n  - {chapter: 2, title: 本章}\n  - {chapter: 3, title: 後章}\n", (2, 2)),
    ("chapters: [\n  {chapter: 2,\n   title: 本章},\n  {chapter: 3, title: 後章}\n]\n", (2, 3)),
    ("chapters:\n  - chapter: 2\n    title: 本章 # 本章註解\n  - chapter: 3\n", (2, 3)),
    ("chapters:\n  - chapter: 2\n    title: 本章", (2, 3)),
    ("chapters:\n  - chapter: 2\n    title:\n  - chapter: 3\n", (2, 3)),
])
def test_isolated_flow_block_and_eof_layouts_remain_citable(text, expected):
    ref = source(text)
    assert (ref["start_line"], ref["end_line"]) == expected
    assert "chapter: 3" not in cited(text, ref)


@pytest.mark.parametrize("text", [
    "common: &outside 外部計畫\nchapters:\n  - chapter: 2\n    title: *outside\n  - chapter: 3\n",
    "chapters:\n  - chapter: 1\n    title: &outside 前章\n  - chapter: 2\n    title: *outside\n",
    "template: &outside {chapter: 2, title: 外部}\nchapters:\n  - *outside\n",
    "template: &outside\n  chapter: 2\n  title: 外部\nchapters:\n  - *outside\n",
    "template: &outside\n  - chapter: 2\n    title: 外部\nchapters: *outside\n",
    "common: &outside {title: 外部}\nchapters:\n  - chapter: 2\n    <<: *outside\n",
    "common: &outside {chapter: 2, title: 外部}\nchapters:\n  - <<: *outside\n",
])
def test_external_aliases_and_merges_do_not_misidentify_chapter_sources(text):
    assert source(text) is None


def test_internal_anchor_and_alias_retain_the_actual_alias_use_line():
    text = ("chapters:\n  - &current\n    chapter: 2\n"
            "    objective: &goal 找到信\n    key_events: [*goal]\n"
            "  - chapter: 3\n    title: 未來\n")
    ref = source(text)
    assert (ref["start_line"], ref["end_line"]) == (2, 5)
    assert cited(text, ref).endswith("key_events: [*goal]")


def test_recursive_alias_safe_fails_instead_of_recursing_forever():
    text = "chapters:\n  - &self\n    chapter: 2\n    objective: *self\n"
    assert source(text) is None


def test_load_beat_keeps_inline_content_without_attaching_unsafe_source(tmp_path):
    planning = tmp_path / "planning"
    planning.mkdir()
    (planning / "arc_plan_1.yaml").write_text(
        "chapters: [{chapter: 2, title: 本章}, {chapter: 3, title: 後章}]\n", encoding="utf-8")
    beat = context.load_beat(tmp_path, 2)
    assert beat["title"] == "本章" and beat["source"] is None


def test_load_beat_accepts_chapter_number_in_external_merge_without_false_source(tmp_path):
    planning = tmp_path / "planning"
    planning.mkdir()
    (planning / "arc_plan_1.yaml").write_text(
        "common: &outside {chapter: 2, title: 本章}\nchapters:\n  - <<: *outside\n", encoding="utf-8")
    beat = context.load_beat(tmp_path, 2)
    assert beat["title"] == "本章" and beat["source"] is None


def test_legacy_markdown_keeps_its_single_row_reference(tmp_path):
    planning = tmp_path / "planning"
    planning.mkdir()
    (planning / "structure.md").write_text(
        "# 規劃\n| 2 | 本章 | R | 目標 | 事件 | 情緒 | 甲 | 房間 | ①plant |\n"
        "| 3 | 後章 | S | 下章 | 後續 | 緊張 | 乙 | 城市 | |\n", encoding="utf-8")
    beat = context.load_beat(tmp_path, 2)
    assert beat["source"] == {"path": "planning/structure.md", "start_line": 2, "end_line": 2}


def test_missing_or_non_mapping_plan_has_no_source():
    assert source("chapters: [{chapter: 1}]\n") is None
    assert source("[]\n") is None
