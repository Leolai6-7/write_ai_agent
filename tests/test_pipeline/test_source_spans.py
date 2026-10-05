"""Line navigation never expands a projected item into future/sibling evidence."""

import json
from pathlib import Path

import pytest

from scripts.source_spans import graph_source_chapters, graph_sources, json_source_ref
from scripts.story_snapshot import text_hash


class MemorySnapshot:
    """No story files or models are needed to exercise offset/provenance logic."""

    story_dir = Path("/synthetic-story")
    graph_error = None

    def __init__(self, text: str):
        self.text = text
        self.graph = json.loads(text)
        self.reads = 0

    def read_text(self, path):
        assert path == self.story_dir / "runtime" / "story_graph.json"
        self.reads += 1
        return self.text


def snapshot(graph, **kwargs):
    return MemorySnapshot(json.dumps(graph, ensure_ascii=False, indent=2, **kwargs))


def excerpt(snap, ref):
    return "\n".join(snap.text.splitlines()[ref.start_line - 1:ref.end_line])


def ref_for(snap, pointer):
    return json_source_ref(snap, Path("runtime/story_graph.json"), pointer)


def test_exact_nested_member_span_keeps_only_its_complete_paragraph():
    snap = snapshot({"values": {
        "門牌": {"value": "三號", "note": "先敲門；再等回應。\n第二段。"},
        "未來暗號": {"value": "不得讀到"},
    }})
    ref = ref_for(snap, ["values", "門牌"])
    assert ref.path == "runtime/story_graph.json"
    assert ref.sha256 == text_hash(snap.text)
    assert excerpt(snap, ref) == '\n'.join(snap.text.splitlines()[2:6])
    assert "先敲門；再等回應。\\n第二段。" in excerpt(snap, ref)
    assert "未來暗號" not in excerpt(snap, ref)


def test_array_entry_span_handles_escaped_quotes_and_structural_characters():
    snap = snapshot({"rows": [{"text": '說「a\\b」以及 "}, ]"。'}, {"text": "另一筆"}]})
    ref = ref_for(snap, ["rows", 0])
    assert ref is not None
    assert "另一筆" not in excerpt(snap, ref)
    assert json.loads(excerpt(snap, ref).strip().removesuffix(",")) == snap.graph["rows"][0]


@pytest.mark.parametrize("text,pointer", [
    ('{"a":{"value":1},"b":{"future":2}}', ["a"]),
    ('{\n  "rows": [{"value": 1}, {"future": 2}]\n}', ["rows", 0]),
    ('{\n  "outer": {"target": {\n    "value": 1\n  }}\n}', ["outer", "target"]),
    ('{\n  "target": {\n    "value": 1\n  }, "future": 2\n}', ["target"]),
])
def test_ancestor_or_sibling_content_on_boundary_lines_is_not_citable(text, pointer):
    assert ref_for(MemorySnapshot(text), pointer) is None


def test_a_compact_target_alone_on_its_property_line_is_safe():
    snap = MemorySnapshot('{\n  "target": {"value": 1},\n  "future": 2\n}')
    ref = ref_for(snap, ["target"])
    assert (ref.start_line, ref.end_line) == (2, 2)
    assert excerpt(snap, ref) == '  "target": {"value": 1},'


def test_primitive_and_unusual_json_keys_have_exact_member_lines():
    snap = snapshot({"一/二~三\"": {"value": 123}, "empty": []})
    ref = ref_for(snap, ['一/二~三"', "value"])
    assert excerpt(snap, ref).strip() == '"value": 123'
    assert ref_for(snap, ["absent"]) is None
    assert ref_for(snap, ["empty", 0]) is None
    assert ref_for(snap, []) is None


def test_duplicate_keys_cannot_produce_ambiguous_source_spans():
    snap = MemorySnapshot('{\n"value": 1,\n"value": 2\n}')
    assert ref_for(snap, ["value"]) is None


@pytest.mark.parametrize("pointer", [[True], [-1], [None], "values"])
def test_invalid_pointer_is_rejected(pointer):
    with pytest.raises(ValueError, match="JSON pointer"):
        ref_for(snapshot({}), pointer)


def test_external_path_is_not_read():
    snap = snapshot({})
    assert json_source_ref(snap, Path("../other-story/source.json"), ["x"]) is None
    assert snap.reads == 0


@pytest.fixture
def tracked():
    # Deliberately includes misleading current outer state: provenance helpers
    # must navigate the history instead. Canonical validation is the caller's job.
    return snapshot({
        "values": {"銀幣": {"value": "未來九枚"}},
        "_history": {
            "version": 1,
            "baseline": {
                "values": {"銀幣": {"value": "原先一枚"}},
                "foreshadowing": {"信": {"status": "已植入", "planted_in": [1]}},
                "concepts": {"舊術": {"introduced_in": 1}},
            },
            "diffs": {
                "2": {"chapter": 2,
                      "new_values": [{"setting": "銀幣", "value": "現在兩枚"}],
                      "foreshadowing_updates": [{"thread": "信", "action": "hint"}],
                      "concepts_introduced": [{"name": "新術"}],
                      "causal_chains": [{"cause": "信到", "effect": "動身", "cause_ch": 1, "effect_ch": 2}],
                      "mirrors": [{"r_line": "打開門", "s_line": "關上窗"}]},
                "4": {"chapter": 4,
                      "new_values": [{"setting": "銀幣", "value": "未來九枚"}],
                      "foreshadowing_updates": [{"thread": "信", "action": "resolve"}],
                      "concepts_introduced": [{"name": "未來術"}],
                      "causal_chains": [{"cause": "信到", "effect": "動身", "cause_ch": 3, "effect_ch": 4}],
                      "mirrors": [{"r_line": "打開門", "s_line": "關上窗"}]},
            },
        },
    })


def test_values_reference_latest_prior_diff_never_outer_future_or_old_setting(tracked):
    refs = graph_sources(tracked, 4, "values", "銀幣")
    assert len(refs) == 1
    text = excerpt(tracked, refs[0])
    assert "現在兩枚" in text
    assert "原先一枚" not in text and "未來九枚" not in text
    assert graph_source_chapters(tracked, 4, "values", "銀幣") == (2,)
    baseline = graph_sources(tracked, 2, "values", "銀幣")
    assert len(baseline) == 1 and "原先一枚" in excerpt(tracked, baseline[0])
    assert graph_source_chapters(tracked, 2, "values", "銀幣") == ()


def test_thread_sources_keep_baseline_and_prior_contributors_only(tracked):
    refs = graph_sources(tracked, 4, "foreshadowing", "信")
    assert len(refs) == 2
    text = "\n".join(excerpt(tracked, ref) for ref in refs)
    assert "已植入" in text and "hint" in text
    assert "resolve" not in text and "new_values" not in text
    assert graph_source_chapters(tracked, 4, "foreshadowing", "信") == (1, 2)


@pytest.mark.parametrize("section,item,expected", [
    ("concepts", "新術", '"name": "新術"'),
    ("concepts", "舊術", '"introduced_in": 1'),
    ("causal_chains", {"cause": "信到", "effect": "動身", "cause_ch": "1", "effect_ch": "2"}, '"cause_ch": 1'),
    ("mirrors", {"r_line": "打開門", "s_line": "關上窗"}, '"r_line": "打開門"'),
])
def test_other_supported_items_cite_only_matching_record(tracked, section, item, expected):
    refs = graph_sources(tracked, 4, section, item)
    assert len(refs) == 1
    assert expected in excerpt(tracked, refs[0])
    assert "chapter" not in excerpt(tracked, refs[0])


def test_same_prose_at_different_chapter_pair_does_not_match(tracked):
    item = {"cause": "信到", "effect": "動身", "cause_ch": "3", "effect_ch": "4"}
    assert graph_sources(tracked, 4, "causal_chains", item) == ()
    refs = graph_sources(tracked, 5, "causal_chains", item)
    assert len(refs) == 1 and '"cause_ch": 3' in excerpt(tracked, refs[0])


def test_compact_graph_has_no_span_but_retains_lifecycle_contributor_ids(tracked):
    compact = MemorySnapshot(json.dumps(tracked.graph, ensure_ascii=False))
    assert graph_sources(compact, 4, "values", "銀幣") == ()
    assert graph_source_chapters(compact, 4, "values", "銀幣") == (2,)


def test_legacy_flat_graph_references_just_the_item_and_explicit_chapters():
    snap = snapshot({
        "values": {"門牌": {"value": 3}, "無關": {"value": 100}},
        "causal_chains": [{"cause": "敲門", "effect": "開門", "cause_ch": 1, "effect_ch": 2}],
    })
    refs = graph_sources(snap, 3, "values", "門牌")
    assert len(refs) == 1 and "無關" not in excerpt(snap, refs[0])
    item = snap.graph["causal_chains"][0]
    assert graph_source_chapters(snap, 3, "causal_chains", item) == (1, 2)
    assert graph_source_chapters(snap, 3, "values", "門牌") == ()


def test_invalid_graph_has_no_reference(tracked):
    tracked.graph_error = "Snapshot differs from replay"
    assert graph_sources(tracked, 4, "values", "銀幣") == ()
    assert graph_source_chapters(tracked, 4, "values", "銀幣") == ()
