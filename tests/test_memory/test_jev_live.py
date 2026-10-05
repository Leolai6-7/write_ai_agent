"""Opt-in paid service smoke test; only synthetic story text leaves the machine."""

import os

import pytest

from memory import jev_bridge as bridge
from tests.test_memory.test_jev_bridge import add_chapter, make_story


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("NOVEL_TEST_JEV_LIVE") != "1",
                    reason="Explicit NOVEL_TEST_JEV_LIVE=1 and TypeSafe credentials required")
def test_live_synthetic_memory(tmp_path):
    assert os.environ.get("TYPESAFE_API_KEY")
    story = make_story(tmp_path, mode="active", mock=False, config={
        "encoder_model": os.environ.get("JEV_MEM_ENCODER", bridge.DEFAULT_ENCODER),
        "jev_model": os.environ.get("JEV_MEM_MODEL", "jev-latest"),
        "timeout_seconds": 60,
    })
    for chapter, text in enumerate((
            "Mina puts the brass key in a red box at the harbor.",
            "Mina moves the brass key from the red box to a green bag.",
            "Future secret: Mina throws the brass key into the sea."), 1):
        add_chapter(story, chapter, text)
        result = bridge.sync_chapter(story, chapter)
        assert result["stored"], result
    result = bridge.query_memory(story, 3, "Where did Mina move the brass key?", limit=3)
    assert result["status"] == "ok", result
    assert result["evidence"], result
    assert any(item["chapter"] == 2 for item in result["evidence"]), result
    assert all(item["chapter"] < 3 and "Future secret" not in item["text"]
               for item in result["evidence"])
    assert result["trace"]["controller"] == "jev-mem"
    assert result["trace"]["llm_calls"] == 0
    print({"status": result["status"], "chapters": [r["chapter"] for r in result["evidence"]],
           "trace": result["trace"]})
