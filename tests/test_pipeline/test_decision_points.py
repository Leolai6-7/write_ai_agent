"""Optional decision beats remain source-linked plans in bounded writer input."""

from copy import deepcopy
import json
from pathlib import Path
import re
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import assemble_context as assemble  # noqa: E402
from chapter_context import build_chapter_context  # noqa: E402
from context_bundle import SECTION_TITLES  # noqa: E402
from narrative_state import prepare_narrative_sources  # noqa: E402
from story_graph_nx import StoryGraph  # noqa: E402
from story_snapshot import StorySnapshot, text_hash  # noqa: E402


DECISIONS = [
    {
        "character": "小白",
        "trigger": "收到今晚封門的通知；留到明早便無法進屋。",
        "reasoning": "他相信守衛尚未換班，害怕再次失約，願冒險先救阿青。\n這是他的猜測，不是已確認的消息。",
        "options": ["等到天亮再求援；較安全，但會錯過封門前的機會。", "交出信件求通行；可能暴露阿青。"],
        "choice": "PLANNED_DECISION：獨自翻牆入屋，不交出信件。",
        "accepted_cost": "已預見自己可能受傷，也可能被守衛認出。",
        "uncertainty": "不知道屋內另有守衛，也可能誤判換班時間。",
    },
    {"character": "阿青", "choice": "PLANNED_SECOND_CHOICE：不回應敲門聲。"},
]
RECALL = {
    "selected_backend": "chroma",
    "semantic_recall": {"status": "not_indexed", "results": []},
    "jev_memory": {"status": "disabled"},
}


def make_story(tmp_path, *, decisions=DECISIONS, present=True):
    (tmp_path / "planning").mkdir()
    chapter = {"chapter": 2, "title": "門前", "line": "R", "pov": "小白"}
    if present:
        chapter["decision_points"] = deepcopy(decisions)
    plan = {"chapters": [
        {"chapter": 1, "title": "前章"}, chapter,
        {"chapter": 3, "title": "未來", "key_events": ["FUTURE_BEAT_NOT_THIS_CHAPTER"]},
    ]}
    path = tmp_path / "planning" / "arc_plan_1.yaml"
    path.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return tmp_path


def context(story, *, max_chars=12000):
    snapshot = StorySnapshot(story)
    beat = assemble.load_beat(story, 2, snapshot=snapshot)
    projected = assemble._graph_snapshot(story, snapshot.graph, 2, snapshot=snapshot)
    return beat, build_chapter_context(snapshot, 2, beat, projected, RECALL, max_chars=max_chars)


def included(bundle):
    return {row["key"]: row for row in bundle.metadata["included"]}


def block_body(bundle, key):
    match = re.search(rf"^\[{re.escape(key)}\]\n(.*?)(?=\n\n\[|\n\n## |\Z)",
                      bundle.text, re.MULTILINE | re.DOTALL)
    assert match is not None
    return match.group(1)


def planned_decisions(bundle):
    body = block_body(bundle, "decision_plan")
    data, _ = json.JSONDecoder().raw_decode(body[body.index("[\n"):])
    return data


def section_body(bundle, section):
    return bundle.text.split(f"## {SECTION_TITLES[section]}\n", 1)[1].split("\n\n## ", 1)[0]


def test_actual_yaml_preserves_all_fields_order_and_chapter_scoped_source(tmp_path):
    story = make_story(tmp_path)
    path = story / "planning" / "arc_plan_1.yaml"
    original = path.read_bytes()
    beat, bundle = context(story)
    assert beat["decision_points"] == DECISIONS
    assert planned_decisions(bundle) == DECISIONS
    entry = included(bundle)["decision_plan"]
    assert entry["section"] == "author_intent" and entry["required"] is True
    assert len(entry["sources"]) == 1
    ref = entry["sources"][0]
    assert ref == {**beat["source"], "sha256": text_hash(original.decode("utf-8"))}
    cited = "\n".join(original.decode("utf-8").splitlines()[ref["start_line"] - 1:ref["end_line"]])
    assert "chapter: 2" in cited and "decision_points:" in cited
    assert "chapter: 1" not in cited and "chapter: 3" not in cited
    assert "FUTURE_BEAT_NOT_THIS_CHAPTER" not in bundle.text
    assert "decision_points" not in block_body(bundle, "chapter_intent")
    for decision in DECISIONS:
        assert bundle.text.count(decision["choice"]) == 1
    assert bundle.metadata["char_count"] == len(bundle.text) <= 12000
    assert path.read_bytes() == original


def test_missing_optional_fields_stay_missing_without_quality_or_rationality_rules(tmp_path):
    decisions = [{"character": "小白", "choice": "因恐懼而留在原地，不做最安全的選擇。",
                  "trigger": "", "reasoning": "", "options": []}]
    _, bundle = context(make_story(tmp_path, decisions=decisions))
    result = planned_decisions(bundle)
    assert result == decisions
    assert "accepted_cost" not in result[0] and "uncertainty" not in result[0]


@pytest.mark.parametrize("present", [False, True])
def test_old_yaml_and_explicit_empty_list_need_no_decision_plan(tmp_path, present):
    story = make_story(tmp_path, decisions=[], present=present)
    beat, bundle = context(story)
    assert ("decision_points" in beat) is present
    assert "decision_plan" not in included(bundle)
    assert not any(row["key"] == "decision_plan" for row in bundle.metadata["omitted"])


def test_legacy_markdown_table_keeps_its_existing_fields_and_source(tmp_path):
    planning = tmp_path / "planning"
    planning.mkdir()
    (planning / "structure.md").write_text(
        "# 計畫\n| 2 | 門前 | R | 入屋 | 翻牆 | 緊張 | 小白 | 舊屋 | |\n", encoding="utf-8")
    beat, bundle = context(tmp_path)
    assert "decision_points" not in beat and "decision_plan" not in included(bundle)
    assert beat["key_events"] == "翻牆"
    assert beat["source"] == {"path": "planning/structure.md", "start_line": 2, "end_line": 2}
    assert included(bundle)["chapter_intent"]["sources"][0]["path"] == "planning/structure.md"


def test_required_decision_plan_fits_exactly_or_uses_existing_budget_error(tmp_path):
    decisions = [{"character": "小白", "choice": "完整開始：" + "風險與情緒。" * 1000 + "完整結束",
                  "options": ["其他可信行動及其代價。" * 50]}]
    story = make_story(tmp_path, decisions=decisions)
    _, full = context(story, max_chars=100000)
    assert all(row["required"] for row in full.metadata["included"])
    exact = len(full.text)
    _, bounded = context(story, max_chars=exact)
    assert bounded.text == full.text and planned_decisions(bounded) == decisions
    assert included(bounded)["decision_plan"]["required"] is True
    with pytest.raises(ValueError, match="Required context needs.*cannot be truncated"):
        context(story, max_chars=exact - 1)


def test_plan_does_not_become_canon_knowledge_or_future_graph_evidence(tmp_path):
    story = make_story(tmp_path)
    (story / "runtime").mkdir()
    (story / "outputs").mkdir()
    (story / "outputs" / "chapter_001.md").write_text(
        "# 前章\nPAST_FACT：門還未封。\nPAST_BELIEF：小白相信守衛不會換班。\n", encoding="utf-8")
    (story / "outputs" / "chapter_002.md").write_text(
        "# 本章\nFUTURE_CANON_NOT_YET：屋內其實另有守衛。\n", encoding="utf-8")
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    for chapter, records in (
        (1, [
            {"id": "past-fact", "kind": "fact", "text": "PAST_FACT：門還未封。",
             "source": {"chapter": 1, "start_line": 2, "end_line": 2}},
            {"id": "past-belief", "kind": "belief", "character": "小白",
             "text": "PAST_BELIEF：小白相信守衛不會換班。",
             "source": {"chapter": 1, "start_line": 3, "end_line": 3}},
        ]),
        (2, [{"id": "future-fact", "kind": "fact", "text": "FUTURE_CANON_NOT_YET：屋內其實另有守衛。",
              "source": {"chapter": 2, "start_line": 2, "end_line": 2}}]),
    ):
        prepared = prepare_narrative_sources({"chapter": chapter, "narrative_updates": records}, story)
        graph.apply_chapter_diff(prepared)
        graph.save_flat()
    original_graph = graph.path.read_bytes()
    _, bundle = context(story)
    entries = included(bundle)
    assert entries["narrative:past-fact"]["section"] == "canon_as_of"
    assert entries["narrative:past-belief"]["section"] == "pov_knowledge"
    assert entries["decision_plan"]["section"] == "author_intent"
    assert {key for key in entries if key.startswith("narrative:")} == {
        "narrative:past-fact", "narrative:past-belief",
    }
    for section in ("canon_as_of", "pov_knowledge"):
        body = section_body(bundle, section)
        for decision in DECISIONS:
            assert decision["choice"] not in body
        assert DECISIONS[0]["reasoning"] not in body
    assert "FUTURE_CANON_NOT_YET" not in bundle.text
    assert "FUTURE_CANON_NOT_YET" not in json.dumps(bundle.metadata, ensure_ascii=False)
    assert planned_decisions(bundle) == DECISIONS
    assert graph.path.read_bytes() == original_graph


def test_valid_inline_yaml_keeps_plan_without_an_unsafe_or_whole_file_citation(tmp_path):
    story = make_story(tmp_path)
    path = story / "planning" / "arc_plan_1.yaml"
    path.write_text("chapters: [{chapter: 2, decision_points: [{character: 小白, choice: 留在門外}]}]\n",
                    encoding="utf-8")
    beat, bundle = context(story)
    assert beat["source"] is None
    assert included(bundle)["decision_plan"]["sources"] == []
    assert "本章計畫來源無安全單獨行段，需針對性核對" in block_body(bundle, "decision_plan")
    assert planned_decisions(bundle) == [{"character": "小白", "choice": "留在門外"}]


@pytest.mark.parametrize("invalid", [
    None, {}, "小白留下", ["小白留下"], [None], [{}],
    [{"character": "小白"}], [{"choice": "留下"}],
    [{"character": "  ", "choice": "留下"}], [{"character": "小白", "choice": "\n"}],
    [{"character": 1, "choice": "留下"}], [{"character": "小白", "choice": False}],
    [{"character": "小白", "choice": "留下", "trigger": None}],
    [{"character": "小白", "choice": "留下", "reasoning": {"belief": "未換班"}}],
    [{"character": "小白", "choice": "留下", "accepted_cost": 5}],
    [{"character": "小白", "choice": "留下", "uncertainty": ["未知"]}],
    [{"character": "小白", "choice": "留下", "options": "求援"}],
    [{"character": "小白", "choice": "留下", "options": [True]}],
    [{"character": "小白", "choice": "留下", "reasonnig": "害怕"}],
])
def test_malformed_new_fields_fail_shape_validation_not_silent_loss(tmp_path, invalid):
    story = make_story(tmp_path, decisions=invalid)
    # The loader preserves optional input; bounded writer construction validates
    # it rather than silently dropping a malformed field or inventing a value.
    beat = assemble.load_beat(story, 2)
    assert beat["decision_points"] == invalid
    with pytest.raises(ValueError, match="decision_points"):
        context(story)


def capture_recall_queries(story, beat):
    semantic_calls, optional_calls = [], []

    class FakeRetriever:
        def query(self, **kwargs):
            semantic_calls.append(kwargs)
            return []

    def fake_query(story_dir, **kwargs):
        assert story_dir == story
        optional_calls.append(kwargs)
        return {"mode": "active", "status": "ok", "evidence": []}

    snapshot = StorySnapshot(story)
    assemble.recall_semantic_candidates(story, 2, beat, retriever=FakeRetriever(), snapshot=snapshot)
    assemble.recall_optional_memory(story, 2, beat, query_fn=fake_query, snapshot=snapshot)
    assert len(semantic_calls) == len(optional_calls) == 1
    assert semantic_calls[0] == {
        "query_text": optional_calls[0]["query"], "n_results": 3,
        "max_distance": 1.0, "before_chapter": 2,
    }
    assert optional_calls[0] == {
        "before_chapter": 2, "query": semantic_calls[0]["query_text"], "limit": 3,
        "snapshot": snapshot,
    }
    return semantic_calls[0]["query_text"]


def test_both_existing_recall_callbacks_receive_bounded_decision_clues_despite_long_events(tmp_path):
    story = make_story(tmp_path)
    beat = assemble.load_beat(story, 2)
    beat.update({"objective": "找到舊通知的來源", "key_events": "LONG_EVENT_CONTENT。" * 1000})
    original = deepcopy(beat)
    query = capture_recall_queries(story, beat)
    assert len(query) == 1200
    assert query == assemble.build_recall_query(beat)
    for decision in DECISIONS:
        for field in ("character", "choice", "trigger", "reasoning", "uncertainty"):
            if field in decision:
                assert decision[field] in query
    assert "找到舊通知的來源" in query and "LONG_EVENT_CONTENT。" in query
    assert "不是已發生事實或角色知情" in query
    assert beat == original


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize("long_events", [False, True])
def test_old_beats_and_empty_decisions_keep_the_exact_existing_query_for_both_backends(
    tmp_path, present, long_events,
):
    story = make_story(tmp_path, present=present, decisions=[])
    beat = assemble.load_beat(story, 2)
    beat.update({"objective": "查一封信", "key_events": "完整事件。" * (1000 if long_events else 1),
                 "characters": ["小白", "阿青"], "locations": ["舊屋"]})
    legacy = "\n".join(str(beat.get(key, "")) for key in
                       ("objective", "key_events", "characters", "locations"))
    expected = legacy[:1199] + "…" if len(legacy) > 1200 else legacy
    assert capture_recall_queries(story, beat) == expected
    assert assemble.build_recall_query(beat) == expected


def test_oversized_decision_field_is_skipped_as_one_item_without_losing_other_clues(tmp_path):
    decisions = [{"character": "小白", "choice": "先等阿青回話", "trigger": "收到封門通知",
                  "reasoning": "OVERSIZED_REASON_START。" + "過長推理。" * 1000 + "OVERSIZED_REASON_END。",
                  "uncertainty": "不知道屋內是否有人：UNCERTAIN_CLUE"}]
    story = make_story(tmp_path, decisions=decisions)
    beat = assemble.load_beat(story, 2)
    beat["key_events"] = "很長的事件背景。" * 1000
    query = capture_recall_queries(story, beat)
    assert len(query) == 1200
    assert decisions[0]["choice"] in query and decisions[0]["trigger"] in query
    assert decisions[0]["uncertainty"] in query
    assert "OVERSIZED_REASON_START" not in query and "OVERSIZED_REASON_END" not in query
