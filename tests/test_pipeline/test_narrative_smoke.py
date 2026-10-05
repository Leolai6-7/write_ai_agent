"""Offline replay of short-story revisions, not a semantic evaluator.

The prose/diff interpretations require a human reading of the fixture. These
tests verify source provenance, context separation and revision bookkeeping;
matching a phrase or obtaining a receipt does not prove a narrative claim.
"""

import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import assemble_context as assemble  # noqa: E402
import chapter_workflow as workflow  # noqa: E402
from chapter_context import build_chapter_context  # noqa: E402
from narrative_state import normalized_hash, prepare_narrative_sources  # noqa: E402
from story_graph_nx import StoryGraph  # noqa: E402
from story_snapshot import StorySnapshot, chapter_log_entry  # noqa: E402


FIXTURE = Path(__file__).resolve().parents[2] / "examples" / "narrative-smoke"
INITIAL = FIXTURE / "revisions" / "initial"


def fixture_path(chapter, suffix, *, initial):
    name = f"chapter_{chapter:03d}.{suffix}"
    # Chapter 2 is intentionally unchanged, so it has only one source version.
    if initial and chapter in (1, 3):
        return INITIAL / name
    return FIXTURE / ("outputs" if suffix == "md" else "diffs") / name


def load_diff(chapter, *, initial):
    return yaml.safe_load(fixture_path(chapter, "yaml", initial=initial).read_text("utf-8"))


def records(diff):
    return {item["id"]: item for item in diff["narrative_updates"]}


def included(bundle):
    return {item["key"]: item for item in bundle.metadata["included"]}


def manuscript_hash(story, chapter):
    return hashlib.sha256((story / "outputs" / f"chapter_{chapter:03d}.md").read_bytes()).hexdigest()


def assert_source_spans(story, prepared):
    """Check actual source lines and hashes, without judging their meaning."""
    for record in prepared["narrative_updates"]:
        source = record["source"]
        assert source["chapter"] == prepared["chapter"]
        text = (story / "outputs" / f"chapter_{source['chapter']:03d}.md").read_text("utf-8")
        lines = text.splitlines()
        start, end = source["start_line"], source["end_line"]
        assert 1 <= start <= end <= len(lines)
        assert "\n".join(lines[start - 1:end]).strip()
        assert source["sha256"] == normalized_hash(text)


def build_context(story, chapter, *, record=True):
    snapshot = StorySnapshot(story)
    assert snapshot.graph_error is None
    beat = assemble.load_beat(story, chapter, snapshot=snapshot)
    assert beat is not None
    projected = assemble._graph_snapshot(story, snapshot.graph, chapter, snapshot=snapshot)
    assert projected is not None
    # Deliberately bypass every optional retrieval backend, as the CLI would
    # otherwise attempt semantic recall even for a fully local story.
    recall = {
        "selected_backend": "none",
        "semantic_recall": {"status": "disabled", "results": []},
        "jev_memory": {"status": "disabled", "evidence": []},
    }
    bundle = build_chapter_context(
        snapshot, chapter, beat, projected, recall,
        previous_ending=assemble.get_previous_chapter_ending(
            story, chapter, beat["line"], snapshot=snapshot),
        graph_status="ok" if snapshot.graph else "missing",
    )
    assert bundle.metadata["char_count"] == len(bundle.text) <= bundle.metadata["max_chars"]
    for item in bundle.metadata["included"]:
        for source in item["sources"]:
            text = (story / source["path"]).read_text("utf-8")
            assert 1 <= source["start_line"] <= source["end_line"] <= len(text.splitlines())
            assert source["sha256"] == normalized_hash(text)
        if item["key"].startswith("narrative:"):
            assert all(int(Path(source["path"]).stem.split("_")[-1]) < chapter
                       for source in item["sources"])
    assert snapshot.is_current()
    if record:
        workflow.record_context(story, chapter, snapshot=snapshot)
    return bundle, projected


def write_chapter(story, chapter, log_entries, *, initial, replace=False):
    """Write only this chapter's real artifacts, after its context was built."""
    shutil.copyfile(fixture_path(chapter, "md", initial=initial),
                    story / "outputs" / f"chapter_{chapter:03d}.md")
    log_source = INITIAL / "story_log.md" if initial else FIXTURE / "runtime" / "story_log.md"
    log_entry = chapter_log_entry(log_source.read_text("utf-8"), chapter)
    assert log_entry is not None
    log_entries[chapter] = log_entry
    (story / "runtime" / "story_log.md").write_text(
        "# 故事紀錄\n\n" + "\n\n".join(log_entries[n] for n in sorted(log_entries)) + "\n",
        encoding="utf-8",
    )
    diff_path = story / "diffs" / f"chapter_{chapter:03d}.yaml"
    shutil.copyfile(fixture_path(chapter, "yaml", initial=initial), diff_path)
    snapshot = StorySnapshot(story)
    prepared = prepare_narrative_sources(yaml.safe_load(diff_path.read_text("utf-8")), snapshot)
    assert_source_spans(story, prepared)
    graph = StoryGraph(story / "runtime" / "story_graph.json")
    graph.load_flat(snapshot.graph)
    graph.apply_chapter_diff(prepared, replace=replace)
    graph.save_flat()
    assert workflow.record_graph(story, chapter)["lifecycle"] == "complete"
    return graph


@pytest.fixture
def offline_story(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("The narrative smoke replay must not call retrieval or queue indexing")

    monkeypatch.setattr(assemble, "recall_chapter_memory", forbidden)
    monkeypatch.setattr(assemble, "recall_semantic_candidates", forbidden)
    monkeypatch.setattr(assemble, "recall_optional_memory", forbidden)
    monkeypatch.setattr(assemble, "get_retriever", forbidden)
    monkeypatch.setattr(workflow, "queue_index", forbidden)
    story = tmp_path / "narrative-smoke"
    for directory in ("outputs", "runtime", "diffs"):
        (story / directory).mkdir(parents=True)
    for directory in ("planning", "world"):
        shutil.copytree(FIXTURE / directory, story / directory)
    shutil.copyfile(INITIAL / "arc_plan_1.yaml", story / "planning" / "arc_plan_1.yaml")
    return story


@pytest.mark.parametrize("initial,chapter", [(True, 1), (True, 3), (False, 1), (False, 2), (False, 3)])
def test_real_manuscripts_have_requested_length_and_existing_source_lines(tmp_path, initial, chapter):
    text = fixture_path(chapter, "md", initial=initial).read_text("utf-8")
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    # Count Han characters only: title, punctuation and spaces do not inflate it.
    assert 500 <= len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", body)) <= 800
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs" / f"chapter_{chapter:03d}.md").write_text(text, encoding="utf-8")
    prepared = prepare_narrative_sources(load_diff(chapter, initial=initial), StorySnapshot(tmp_path))
    assert_source_spans(tmp_path, prepared)


def test_real_story_replays_context_completion_and_selective_revision(offline_story):
    story = offline_story
    log_entries = {}
    contexts = {}
    projections = {}
    for chapter in (1, 2, 3):
        assert not (story / "outputs" / f"chapter_{chapter:03d}.md").exists()
        contexts[chapter], projections[chapter] = build_context(story, chapter)
        graph = write_chapter(story, chapter, log_entries, initial=True)
        assert all(workflow.chapter_status(story, n)["complete"] for n in range(1, chapter + 1))

    initial_one = records(load_diff(1, initial=True))
    chapter_two = included(contexts[2])
    assert contexts[2].metadata["pov"] == ["小白"]
    assert chapter_two["narrative:key-location"]["section"] == "canon_as_of"
    assert projections[2]["narrative_state"]["key-location"]["text"] == initial_one["key-location"]["text"]
    assert chapter_two["narrative:xiaobai-key-redbox"]["section"] == "pov_knowledge"
    assert initial_one["xiaobai-key-redbox"]["kind"] == "belief"
    assert {key for key, item in chapter_two.items()
            if key.startswith("narrative:") and item["section"] == "pov_knowledge"} == {
                "narrative:xiaobai-key-redbox",
            }
    assert "narrative:linqing-key-location" not in chapter_two
    assert {"id": "linqing-key-location", "reason": "wrong_pov"} in contexts[2].metadata["narrative_excluded"]
    assert not any(item["kind"] == "knowledge" and item.get("character") == "小白"
                   for item in projections[2]["narrative_state"].values())

    chapter_three = included(contexts[3])
    assert projections[3]["narrative_state"]["xiaobai-key-redbox"]["status"] == "retired"
    assert "narrative:xiaobai-key-redbox" not in chapter_three
    assert {"id": "xiaobai-key-redbox", "reason": "retired"} in contexts[3].metadata["narrative_excluded"]
    assert "narrative:xiaobai-key-location" not in chapter_three
    assert "xiaobai-key-location" not in projections[3].get("narrative_state", {})
    empty_box = projections[3]["narrative_state"]["xiaobai-redbox-empty"]
    assert (empty_box["kind"], empty_box["character"], empty_box["source"]["chapter"]) == (
        "knowledge", "小白", 2,
    )
    assert chapter_three["narrative:xiaobai-redbox-empty"]["section"] == "pov_knowledge"

    original_hashes = {chapter: manuscript_hash(story, chapter) for chapter in (1, 2, 3)}
    unchanged_hash = original_hashes[2]
    unchanged_diff = (story / "diffs" / "chapter_002.yaml").read_bytes()
    unchanged_log = log_entries[2]
    original_three_log = log_entries[3]
    initial_location = graph.to_flat()["narrative_state"]["key-location"]["text"]
    shutil.copyfile(FIXTURE / "planning" / "arc_plan_1.yaml", story / "planning" / "arc_plan_1.yaml")
    build_context(story, 1)
    write_chapter(story, 1, log_entries, initial=False, replace=True)
    assert manuscript_hash(story, 1) != original_hashes[1]
    for chapter in (2, 3):
        status = workflow.chapter_status(story, chapter)
        assert status["lifecycle"] == "needs_review"
        assert status["review_allowed"] and not status["complete"]

    # This replays the fixture author's separate semantic review, not a review
    # decision inferred from identical hashes or fabricated by this test.
    reviewed = workflow.acknowledge_review(
        story, 2,
        "已人工覆核第二章3、5–7、13–17、33–39行：只依賴紅盒舊習慣、"
        "盒空、未被告知且林青在樓上；無茶罐／藍布袋細節，新藏處不影響正文與 diff。",
        snapshot=StorySnapshot(story),
    )
    assert reviewed["complete"]
    assert manuscript_hash(story, 2) == unchanged_hash
    assert (story / "diffs" / "chapter_002.yaml").read_bytes() == unchanged_diff
    assert chapter_log_entry((story / "runtime" / "story_log.md").read_text("utf-8"), 2) == unchanged_log
    assert workflow.chapter_status(story, 3)["lifecycle"] == "needs_review"

    revised_context, projected = build_context(story, 3)
    new_location = records(load_diff(1, initial=False))["key-location"]["text"]
    assert new_location != initial_one["key-location"]["text"]
    assert projected["narrative_state"]["key-location"]["text"] == new_location
    assert "narrative:key-location" in included(revised_context)
    assert "narrative:xiaobai-key-location" not in included(revised_context)
    assert workflow.chapter_status(story, 3)["lifecycle"] == "writing"
    graph = write_chapter(story, 3, log_entries, initial=False, replace=True)
    assert manuscript_hash(story, 3) != original_hashes[3]
    assert log_entries[3] != original_three_log
    state = graph.to_flat()["narrative_state"]
    revised_three = records(load_diff(3, initial=False))
    assert state["key-location"]["text"] == revised_three["key-location"]["text"]
    assert state["key-location"]["text"] != initial_location
    assert state["key-location"]["source"]["chapter"] == 3
    knowledge = state["xiaobai-key-location"]
    assert (knowledge["kind"], knowledge["character"], knowledge["status"]) == ("knowledge", "小白", "active")
    assert knowledge["introduced_in"] == knowledge["updated_in"] == knowledge["source"]["chapter"] == 3
    assert knowledge["source"]["sha256"] == normalized_hash((story / "outputs" / "chapter_003.md").read_text("utf-8"))
    assert all(workflow.chapter_status(story, n)["complete"] for n in (1, 2, 3))
    assert manuscript_hash(story, 2) == unchanged_hash
    workflow_data = json.loads((story / "runtime" / "chapter_workflow.json").read_text("utf-8"))
    assert len(workflow_data["chapters"]["2"]["reviews"]) == 1
    assert not workflow_data["chapters"]["3"].get("reviews")
    assert not (story / "chroma").exists()
    assert not (story / "runtime" / "jev_memory").exists()
