"""Atomic context selection stays bounded without changing any story sources."""

from dataclasses import replace
import json

import pytest

from scripts.context_bundle import (
    SECTION_TITLES,
    ContextBlock,
    SourceRef,
    build_context_bundle,
)


def keys(bundle):
    return [item["key"] for item in bundle.metadata["included"]]


def test_required_blocks_fail_instead_of_truncating():
    block = ContextBlock("intent", "author_intent", "保留完整情節。", required=True)
    with pytest.raises(ValueError, match="Required context needs"):
        build_context_bundle([block], max_chars=1)


def test_entire_rendered_envelope_and_sources_count_against_exact_budget():
    source = SourceRef("planning/arc.yaml", 3, 5, "a" * 64)
    block = ContextBlock("intent", "author_intent", "保留完整情節。", True, sources=(source,))
    args = {"title": "章前脈絡", "footer": "結尾：先核對來源，再寫作。"}
    original = build_context_bundle([block], max_chars=10000, **args)
    exact = len(original.text)
    bundle = build_context_bundle([block], max_chars=exact, **args)
    assert bundle.text == original.text
    assert bundle.metadata["char_count"] == exact
    assert bundle.metadata["budget_unit"] == "characters"
    assert source.sha256 in bundle.text
    assert "planning/arc.yaml:3-5" in bundle.text
    assert bundle.text.startswith("# 章前脈絡\n\n## ")
    assert bundle.text.endswith(args["footer"])
    with pytest.raises(ValueError):
        build_context_bundle([block], max_chars=exact - 1, **args)


def test_huge_irrelevant_background_does_not_crowd_required_or_target_clue():
    required = ContextBlock("task", "author_intent", "本章找出失蹤信件。", required=True)
    background = ContextBlock("background", "reference", "久遠的背景。" * 1000, priority=-5)
    clue = ContextBlock("target-clue", "continuity", "第2章的抽屜藏有信件。", priority=50)
    budget = len(build_context_bundle([required, clue], max_chars=10000).text)
    bundle = build_context_bundle([background, required, clue], max_chars=budget)
    assert keys(bundle) == ["task", "target-clue"]
    assert bundle.metadata["omitted"] == [
        {"key": "background", "section": "reference", "reason": "char_budget"},
    ]
    assert "久遠的背景" not in bundle.text


def test_target_clue_ranked_before_small_but_irrelevant_first_input():
    clue = ContextBlock("clue", "reference", "與當前謎題直接相關的線索。", priority=10)
    background = ContextBlock("background", "reference", "背景。", priority=0)
    budget = len(build_context_bundle([clue], max_chars=10000).text)
    bundle = build_context_bundle([background, clue], max_chars=budget)
    assert keys(bundle) == ["clue"]


def test_skip_oversized_high_priority_candidate_and_keep_later_smaller_candidate():
    huge = ContextBlock("huge", "reference", "大" * 10000, priority=100)
    small = ContextBlock("small", "reference", "完整小線索。", priority=1)
    budget = len(build_context_bundle([small], max_chars=10000).text)
    bundle = build_context_bundle([huge, small], max_chars=budget)
    assert keys(bundle) == ["small"]
    assert bundle.metadata["omitted"][0]["key"] == "huge"


def test_equal_priority_keeps_original_order_and_output_is_deterministic():
    blocks = [ContextBlock(key, "continuity", "同長度。", priority=3) for key in ("b", "a")]
    budget = len(build_context_bundle(blocks[:1], max_chars=10000).text)
    first = build_context_bundle(iter(blocks), max_chars=budget)
    second = build_context_bundle(iter(blocks), max_chars=budget)
    assert first == second
    assert keys(first) == ["b"]


def test_sections_distinguish_plan_canon_and_belief_in_fixed_order():
    blocks = [ContextBlock(section, section, f"{section}內容。") for section in SECTION_TITLES]
    bundle = build_context_bundle(reversed(blocks), max_chars=10000)
    assert [item["section"] for item in bundle.metadata["included"]] == list(SECTION_TITLES)
    assert "不是已發生事實" in bundle.text
    assert "不是後續情節" in bundle.text
    assert "不等於客觀事實" in bundle.text


def test_identical_duplicate_merges_requirement_and_priority_without_double_counting():
    block = ContextBlock("fact", "canon_as_of", "第1章下過雨。", priority=1)
    duplicate = replace(block, required=True, priority=20)
    bundle = build_context_bundle([block, duplicate], max_chars=10000)
    assert bundle.text.count("第1章下過雨。") == 1
    assert bundle.metadata["included_count"] == 1
    assert bundle.metadata["omitted_count"] == 1
    assert bundle.metadata["input_count"] == 2
    assert bundle.metadata["included"][0]["required"] is True
    assert bundle.metadata["included"][0]["priority"] == 20
    assert bundle.metadata["omitted"][0]["reason"] == "duplicate_key"


@pytest.mark.parametrize("first_required,second_required", [(True, False), (False, True)])
def test_conflicting_required_duplicates_fail_in_either_order(first_required, second_required):
    blocks = [
        ContextBlock("fact", "canon_as_of", "下雨。", required=first_required),
        ContextBlock("fact", "canon_as_of", "晴天。", required=second_required),
    ]
    with pytest.raises(ValueError, match="Conflicting required duplicate"):
        build_context_bundle(blocks, max_chars=10000)


def test_conflicting_optional_duplicate_keeps_first_and_omits_second_content():
    blocks = [
        ContextBlock("fact", "reference", "原始資料。"),
        ContextBlock("fact", "reference", "不同資料。", priority=100),
    ]
    bundle = build_context_bundle(blocks, max_chars=10000)
    assert "原始資料。" in bundle.text
    assert "不同資料。" not in bundle.text
    assert "不同資料。" not in json.dumps(bundle.metadata, ensure_ascii=False)


def test_later_required_promotion_cannot_hide_an_earlier_conflicting_duplicate():
    first = ContextBlock("fact", "reference", "原始資料。")
    conflicting = replace(first, text="不同資料。")
    with pytest.raises(ValueError, match="Conflicting required duplicate"):
        build_context_bundle(
            [first, conflicting, replace(first, required=True)], max_chars=10000,
        )


def test_evidence_sources_deduplicate_and_omitted_sources_are_navigation_only():
    shared = SourceRef("outputs/chapter_001.md", 1, 3)
    excluded = SourceRef("outputs/chapter_002.md", 7, 9)
    blocks = [
        ContextBlock("first", "continuity", "線索甲。", True, sources=[shared, shared]),
        ContextBlock("second", "continuity", "線索乙。", True, sources=[shared]),
        ContextBlock("large", "reference", "字" * 10000, sources=[excluded]),
    ]
    bundle = build_context_bundle(blocks, max_chars=1000)
    assert bundle.metadata["sources"] == [shared.as_dict()]
    assert bundle.metadata["included"][0]["sources"] == [shared.as_dict()]
    assert excluded.path not in bundle.text
    assert bundle.metadata["omitted_sources"] == {"large": [excluded.as_dict()]}
    assert excluded.path not in json.dumps(bundle.metadata["included"])
    assert "字" * 10000 not in json.dumps(bundle.metadata, ensure_ascii=False)


def test_empty_budget_and_empty_envelope_can_produce_empty_bundle():
    bundle = build_context_bundle([], max_chars=0, title="")
    assert bundle.text == ""
    assert bundle.metadata["char_count"] == 0
    assert bundle.metadata["sources"] == []
    with pytest.raises(ValueError):
        build_context_bundle([], max_chars=0)


def test_all_successful_budgets_are_bounded_atomic_and_fully_accounted():
    required = ContextBlock("r", "author_intent", "必須完整。😀", required=True)
    blocks = [required] + [
        ContextBlock(str(number), "reference", f"完整第{number}句：" + "文" * number)
        for number in range(1, 7)
    ]
    minimum = len(build_context_bundle([required], max_chars=1000, footer="終。").text)
    for budget in range(minimum, minimum + 150):
        bundle = build_context_bundle(blocks, max_chars=budget, footer="終。")
        assert bundle.metadata["char_count"] == len(bundle.text) <= budget
        assert bundle.metadata["included_count"] + bundle.metadata["omitted_count"] == len(blocks)
        assert bundle.text.endswith("終。")
        for block in blocks:
            assert (block.text in bundle.text) == (block.key in keys(bundle))


@pytest.mark.parametrize("budget", [-1, True, 1.5])
def test_invalid_budgets_rejected(budget):
    with pytest.raises(ValueError, match="max_chars"):
        build_context_bundle([], max_chars=budget)


def test_invalid_blocks_and_source_spans_rejected():
    with pytest.raises(ValueError, match="section"):
        ContextBlock("bad", "unknown", "資料。")
    with pytest.raises(ValueError, match="Source lines"):
        SourceRef("file.md", 3, 2)
    with pytest.raises(ValueError, match="sha256"):
        SourceRef("file.md", 1, 2, "not-a-hash")
    with pytest.raises(ValueError, match="Block text"):
        ContextBlock("empty", "reference", "  ")
