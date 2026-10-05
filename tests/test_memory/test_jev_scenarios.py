"""Small, fictional evidence-recall checks; not a long-novel quality benchmark.

Mock exercises lifecycle/boundaries only. Live runs four writes and three queries
and reports every case separately, including failures. Cached embeddings and an
explicit NOVEL_TEST_JEV_LIVE=1 are required; this module never loads credentials.
"""

import json
import os

import pytest

from memory import jev_bridge as bridge
from tests.test_memory.test_jev_bridge import add_chapter, make_story


CHAPTERS = {
    1: (
        "Mina 把刻有缺口的銅製海燕胸針交給遼安保管。"
        "她讀到舊航海簿的一句暗語：「潮水退盡，北碼頭地窖取信」。"
    ),
    2: (
        "Mina 在南碼頭倉庫見到書記林洛，人稱「夜雀」。"
        "林洛替老師收藏一枚銀製海燕胸針；倉庫裡的航海簿記錄的是南岸貨船排班。"
    ),
    3: (
        "遼安向 Mina 坦承，他就是一直用「夜鷺」署名的匿名人。"
        "追兵逼近時，遼安把銅製海燕胸針交給藥師若彤保管，然後與 Mina 分頭離開。"
    ),
    4: (
        "Mina 得知若彤已把銅製海燕胸針還給遼安。"
        "當晚遼安將北碼頭地窖的密信搬到西山寺塔頂。"
    ),
}

CASES = (
    {
        "id": "early_clue_with_similar_distractor",
        "question": "Mina 按照最早讀到的暗語，要在哪裡、什麼時候拿到信？",
        "limit": 1,
        "expected": {1: ("潮水退盡", "北碼頭地窖取信")},
    },
    {
        "id": "alias_then_earlier_transfer",
        "question": "以「夜鷺」署名的那個人，先前從 Mina 手上接到什麼物品？",
        "limit": 2,
        "expected": {1: ("銅製海燕胸針交給遼安保管",),
                     3: ("他就是一直用「夜鷺」署名的匿名人",)},
    },
    {
        "id": "updated_keeper_before_future_change",
        "question": "離開追兵後，銅製海燕胸針現在由誰保管？",
        "limit": 1,
        "expected": {3: ("銅製海燕胸針交給藥師若彤保管",)},
    },
)


def build_scenario_story(tmp_path, *, mock):
    story = make_story(tmp_path, name="harbor_synthetic", mode="active", mock=mock, config={
        "encoder_model": os.environ.get("JEV_MEM_ENCODER", bridge.DEFAULT_ENCODER),
        "jev_model": os.environ.get("JEV_MEM_MODEL", "jev-latest"),
        "timeout_seconds": 60,
    })
    for chapter, text in CHAPTERS.items():
        add_chapter(story, chapter, text)
        result = bridge.sync_chapter(story, chapter)
        assert result.get("stored") is True, {"chapter": chapter, "result": result}
    return story


@pytest.fixture(scope="module")
def live_scenario_story(tmp_path_factory):
    if os.environ.get("NOVEL_TEST_JEV_LIVE") != "1":
        pytest.skip("Set NOVEL_TEST_JEV_LIVE=1 explicitly for paid synthetic evidence checks")
    assert os.environ.get("JEV_MEM_PYTHON") and os.environ.get("JEV_MEM_SOURCE")
    assert "TYPESAFE_API_KEY" in os.environ, "Supply the API key through the existing environment"
    return build_scenario_story(tmp_path_factory.mktemp("jev-live-scenarios"), mock=False)


@pytest.mark.integration
@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_live_synthetic_evidence(live_scenario_story, case):
    result = bridge.query_memory(live_scenario_story, before_chapter=4,
                                 query=case["question"], limit=case["limit"])
    hits = result.get("evidence", [])
    retrieved = [item["chapter"] for item in hits]
    snippets = {chapter: all(any(item["chapter"] == chapter and snippet in item["text"]
                                for item in hits) for snippet in expected)
                for chapter, expected in case["expected"].items()}
    missing = sorted(set(case["expected"]) - set(retrieved))
    boundary_ok = all(item["chapter"] < 4 and "西山寺塔頂" not in item["text"]
                      and "胸針還給遼安" not in item["text"] for item in hits)
    passed = (result.get("status") == "ok" and bool(hits) and not missing
              and all(snippets.values()) and boundary_ok and 2 not in retrieved)
    report = {"case": case["id"], "passed": passed, "status": result.get("status"),
              "required_chapters": sorted(case["expected"]), "retrieved_chapters": retrieved,
              "missing_chapters": missing, "expected_snippets_found": snippets,
              "future_boundary_ok": boundary_ok, "distractor_returned": 2 in retrieved,
              "trace": result.get("trace", {})}
    if result.get("error"):
        report["error"] = result["error"]
    print("JEV_SCENARIO " + json.dumps(report, ensure_ascii=False))
    assert result.get("status") == "ok", report
    assert hits, report
    assert boundary_ok, report
    assert not missing and all(snippets.values()), report
    assert 2 not in retrieved, report
    assert result["trace"]["controller"] == "jev-mem", report
    assert result["trace"]["llm_calls"] == 0, report


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("NOVEL_TEST_JEV") != "1",
                    reason="Set NOVEL_TEST_JEV=1 for actual upstream mock lifecycle checks")
def test_mock_scenario_lifecycle_not_semantic_quality(tmp_path):
    assert os.environ.get("JEV_MEM_PYTHON") and os.environ.get("JEV_MEM_SOURCE")
    story = build_scenario_story(tmp_path, mock=True)
    status = bridge.memory_status(story)
    assert status["chapters"] == [1, 2, 3, 4]
    assert status["observations"] == 4
    assert bridge.sync_chapter(story, 4)["status"] == "unchanged"
    result = bridge.query_memory(story, 4, CASES[2]["question"], limit=2)
    assert result["status"] == "ok", result
    # Mock's lexical encoder and fixed decisions cannot validate Chinese meaning.
    assert all(hit["chapter"] < 4 for hit in result["evidence"]), result
    assert result["trace"]["eligible_chapters"] == [1, 2, 3], result
    assert result["trace"]["excluded_nodes"] == 1, result
    assert result["trace"]["mock"] is True, result
    assert bridge.memory_status(story)["generation"] == status["generation"]
