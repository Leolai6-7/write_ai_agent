"""Synthetic-only foreshadow identity/action contracts; no graph migration."""

import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from assemble_context import load_beat, parse_foreshadow_tag  # noqa: E402
from chapter_context import build_chapter_context, design_reference, _same_thread  # noqa: E402
from foreshadowing import normalize_directives, parse_legacy_directives, resolve_thread  # noqa: E402


class MemorySnapshot:
    story_dir = Path("/synthetic-story")
    graph_error = None
    workflow = {"chapters": {}}
    log_entries = {}

    def __init__(self, *, plan="", design="", graph=None):
        self.graph = graph or {}
        self.files = {
            "planning/arc_plan_1.yaml": plan,
            "planning/foreshadowing.md": design,
            "runtime/story_graph.json": json.dumps(self.graph, ensure_ascii=False, indent=2),
        }

    def read_text(self, path):
        return self.files.get(str(path.relative_to(self.story_dir)), "")

    def is_current(self):
        return True


def load(monkeypatch, items):
    text = yaml.safe_dump({"chapters": [{"chapter": 2, "foreshadowing": items}]},
                          allow_unicode=True, sort_keys=False)
    snapshot = MemorySnapshot(plan=text)
    path = snapshot.story_dir / "planning/arc_plan_1.yaml"
    monkeypatch.setattr(Path, "glob", lambda self, pattern: [path])
    return load_beat(snapshot.story_dir, 2, snapshot=snapshot)


def bundle(items, *, graph=None, design=""):
    directives = normalize_directives(items)
    snapshot = MemorySnapshot(graph=graph, design=design)
    beat = {"foreshadow_directives": directives,
            "foreshadow_threads": list(dict.fromkeys(d["thread_id"] for d in directives))}
    recall = {"selected_backend": "chroma", "semantic_recall": {"status": "not_indexed"},
              "jev_memory": {"status": "disabled"}}
    return build_chapter_context(snapshot, 2, beat, snapshot.graph, recall)


@pytest.mark.parametrize("identity", [13, 25, 120, "十三", "伏筆十三", "⑬", "㉕", "伏筆⑬", "伏筆①"])
def test_unbounded_legacy_ids_survive_load(monkeypatch, identity):
    beat = load(monkeypatch, [{"thread": identity, "action": "hint"}])
    assert len(beat["foreshadow_threads"]) == 1
    assert beat["foreshadow_directives"][0]["action"] == "hint"
    assert beat["source"] is not None


def test_explicit_id_display_and_same_chapter_multiple_actions_survive(monkeypatch):
    beat = load(monkeypatch, [
        {"thread_id": "fs-lost-letter", "name": "失蹤的信", "action": "plant"},
        {"thread_id": "fs-lost-letter", "name": "失蹤的信", "action": "resolve"},
    ])
    assert beat["foreshadow_threads"] == ["fs-lost-letter"]
    assert [d["action"] for d in beat["foreshadow_directives"]] == ["plant", "resolve"]
    assert all(d["name"] == "失蹤的信" and d["legacy"] is False
               for d in beat["foreshadow_directives"])


def test_named_threads_are_exact_not_numeral_or_substring_aliases(monkeypatch):
    beat = load(monkeypatch, [{"thread": "三封未寄出的信", "action": "hint"}])
    assert beat["foreshadow_threads"] == ["三封未寄出的信"]
    assert not _same_thread("伏筆三", "三封未寄出的信")
    assert resolve_thread("失蹤的信", ["另一封失蹤的信"]) is None
    assert _same_thread("伏筆十三", "⑬暗門")
    assert _same_thread("伏筆13", "伏筆⑬暗門")
    assert _same_thread("伏筆一", "伏筆①")
    assert not _same_thread("伏筆一", "郵筒①裡的信")
    assert not _same_thread("伏筆十三", "一封寫著伏筆⑬的信")
    assert resolve_thread("伏筆13", ["伏筆⑬"], explicit=True) is None


@pytest.mark.parametrize("name", ["eggplant", "a hint", "紅、藍兩封信", "錯過/重逢", "red, eggplant"])
def test_plain_legacy_names_with_punctuation_or_action_substrings_are_preserved(name):
    # "a hint" is explicitly separated shorthand, so use a mapping for that
    # deliberately ambiguous display name; plain English suffixes are not tags.
    items = [{"thread": name, "action": "plant"}] if name == "a hint" else [name]
    assert normalize_directives(items)[0]["thread_id"] == name


def test_legacy_shorthand_preserves_multiple_actions_and_bare_name_warning():
    directives = parse_legacy_directives("①plant①resolve、⑬hint；失蹤的信")
    assert [d["action"] for d in directives] == ["plant", "resolve", "hint", None]
    assert parse_foreshadow_tag("①plant、⑬hint") == ["伏筆一", "伏筆13"]
    assert [item["action"] for item in parse_legacy_directives("①plant+⑬hint")] == ["plant", "hint"]
    assert parse_legacy_directives("伏筆⑬hint")[0]["thread_id"] == "伏筆13"
    output = bundle(["失蹤的信"])
    assert "動作未指定" in output.text
    assert "失蹤的信" in output.text


@pytest.mark.parametrize("items", [
    {}, "⑬hint", [13], [True], [""], [{"thread_id": "", "action": "plant"}],
    [{"thread_id": 13, "action": "plant"}], [{"thread": 0, "action": "hint"}],
    [{"thread_id": "fs-a"}], [{"thread": "信", "action": "plnat"}],
    [{"thread": "信", "action": ["plant"]}], [{"thread": "信", "acton": "plant"}],
    [{"thread_id": "fs-a", "thread": 1, "action": "plant"}],
    ["①plnat"], ["①plnat②hint"], ["伏筆13: explode"], ["①plant unexpected"],
    [{"thread": "0", "action": "hint"}], [{"thread": "伏筆零", "action": "hint"}],
    [{"thread": "伏筆十十", "action": "hint"}],
])
def test_invalid_input_is_not_silently_dropped(monkeypatch, items):
    with pytest.raises(ValueError):
        load(monkeypatch, items)


def test_explicit_numeric_like_id_is_opaque_in_graph_and_design():
    graph = {"foreshadowing": {
        "13": {"status": "已植入", "planted_in": [1]},
        "伏筆十三": {"status": "已暗示", "hinted_in": [1]},
    }}
    output = bundle([{"thread_id": "13", "name": "數字代碼", "action": "resolve"}],
                    graph=graph, design="### 13｜數字代碼\nEXACT\n### ⑬舊伏筆\nOLD\n")
    included = {item["key"]: item for item in output.metadata["included"]}
    assert included["thread:13"]["required"] is True
    assert included["thread:伏筆十三"]["required"] is False
    assert included["design_thread:13"]["sources"][0]["start_line"] == 1


def test_required_author_plan_separate_from_historical_status():
    output = bundle([
        {"thread_id": "fs-lost-letter", "name": "失蹤的信", "action": "plant"},
        {"thread_id": "fs-lost-letter", "name": "失蹤的信", "action": "resolve"},
    ], graph={"foreshadowing": {"fs-lost-letter": {"status": "已暗示", "hinted_in": [1]}}},
        design="### fs-lost-letter｜失蹤的信\n作者設計\n")
    included = {item["key"]: item for item in output.metadata["included"]}
    assert included["foreshadow_plan"]["required"] is True
    assert included["foreshadow_plan"]["section"] == "author_intent"
    assert "plant（植入）" in output.text and "resolve（收束）" in output.text
    assert "已暗示" in output.text and "不是歷史進度或角色知情" in output.text
    assert included["design_thread:fs-lost-letter"]["sources"][0]["start_line"] == 1


def test_missing_design_is_a_required_warning_not_a_guessed_name_match():
    output = bundle([{"thread_id": "fs-missing", "name": "失蹤的信", "action": "plant"}],
                    design="### 失蹤的信\n無相同ID的設計\n")
    included = {item["key"]: item for item in output.metadata["included"]}
    assert included["design_thread:fs-missing"]["required"] is True
    assert not included["design_thread:fs-missing"]["sources"]
    assert "未找到獨立標題" in output.text


def test_ambiguous_legacy_graph_aliases_raise_instead_of_merging():
    with pytest.raises(ValueError, match="Ambiguous foreshadow identity"):
        bundle([{"thread": 13, "action": "hint"}], graph={"foreshadowing": {
            "伏筆十三：信": {"status": "已植入"}, "⑬另一封信": {"status": "已植入"},
        }})


def test_duplicate_design_ids_raise_instead_of_taking_first():
    snapshot = MemorySnapshot(design="### fs-a｜第一封信\nA\n### fs-a｜另一封信\nB\n")
    with pytest.raises(ValueError, match="Ambiguous foreshadow identity"):
        design_reference(snapshot, "planning/foreshadowing.md", "fs-a", explicit_thread_id=True)
