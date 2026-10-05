"""Exercise the public chapter CLI contract with a disposable synthetic story."""

import json
from pathlib import Path
import subprocess
import sys
import time

import yaml

from scripts.chapter_workflow import chapter_status

ROOT = Path(__file__).resolve().parents[2]


def run(script, story, *args):
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / script),
                             "--story-dir", str(story), *args],
                            capture_output=True, text=True, check=True, timeout=20)
    return json.loads(result.stdout)


def test_context_write_log_graph_complete_then_recall(tmp_path):
    story = tmp_path / "story"
    for folder in ("planning", "outputs", "runtime"):
        (story / folder).mkdir(parents=True)
    plan = {"chapters": [
        {"chapter": n, "title": f"Test {n}", "line": "A", "objective": "尋找銅鑰匙",
         "key_events": ["回到碼頭"], "characters": ["小林"], "locations": []}
        for n in (1, 2)]}
    (story / "planning" / "arc_plan_1.yaml").write_text(yaml.safe_dump(plan))
    result = run("assemble_context.py", story, "--chapter", "1", "--format", "json")
    assert result["jev_memory"]["mode"] == "off"
    assert not chapter_status(story, 1)["complete"]
    (story / "outputs" / "chapter_001.md").write_text("小林把銅鑰匙留在碼頭。")
    (story / "runtime" / "story_log.md").write_text(
        "## 第1章：碼頭\n- 摘要：小林把銅鑰匙留在碼頭。\n")
    assert not chapter_status(story, 1)["complete"]
    diff = tmp_path / "diff.yaml"
    diff.write_text(yaml.safe_dump({"chapter": 1, "characters_appeared": [
        {"name": "小林", "events": "留下銅鑰匙"}]}))
    applied = run("update_graph.py", story, "--diff", str(diff))
    assert applied["workflow"]["complete"]
    deadline = time.monotonic() + 10
    while chapter_status(story, 1)["index"]["status"] == "pending" and time.monotonic() < deadline:
        time.sleep(0.05)
    assert chapter_status(story, 1)["index"]["status"] in {"ok", "unavailable", "error"}
    state_before = json.loads((story / "runtime" / "story_graph.json").read_text())
    run("update_graph.py", story, "--diff", str(diff))
    assert json.loads((story / "runtime" / "story_graph.json").read_text()) == state_before
    result = run("assemble_context.py", story, "--chapter", "2", "--format", "json")
    assert "小林把銅鑰匙留在碼頭" in result["context_package"]
    assert result["graph_status"] == "ok"
    assert chapter_status(story, 1)["complete"]
    assert chapter_status(story, 2)["missing"] == ["chapter", "story_log", "story_graph"]
