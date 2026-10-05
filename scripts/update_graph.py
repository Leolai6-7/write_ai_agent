"""Apply a chapter diff to story_graph.json (incremental update).

Usage:
    python scripts/update_graph.py \
        --story-dir data/stories/civilization-disease \
        --diff /tmp/chapter_6_diff.yaml
"""

import fcntl
from pathlib import Path

import yaml

from _common import get_args, json_output, json_error
from story_graph_nx import StoryGraph
from chapter_workflow import record_graph, queue_index, chapter_status
from narrative_state import prepare_narrative_sources
from story_snapshot import StorySnapshot


def main():
    args = get_args(
        ("--diff", {"type": str, "required": True, "help": "Path to chapter diff YAML"}),
        ("--replace", {"action": "store_true", "help": "Replace a tracked chapter diff and replay its successors"}),
    )

    story_dir = Path(args.story_dir)
    diff_path = Path(args.diff)

    if not diff_path.exists():
        json_error(f"Diff file not found: {diff_path}")

    json_path = story_dir / "runtime" / "story_graph.json"

    try:
        diff = yaml.safe_load(diff_path.read_text(encoding="utf-8"))
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with (json_path.parent / ".story_graph.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            snapshot = StorySnapshot(story_dir)
            if snapshot.graph_error:
                raise ValueError(snapshot.graph_error)
            graph = StoryGraph(json_path)
            if json_path.exists():
                raw = snapshot.graph
                if "nodes" in raw and ("links" in raw or "edges" in raw):
                    graph.load()
                else:
                    graph.load_flat(raw)
            diff = prepare_narrative_sources(diff, snapshot)
            stats = graph.apply_chapter_diff(diff, replace=args.replace)
            if not snapshot.is_current():
                raise ValueError("Story changed while preparing graph update; retry with current sources")
            graph.save_flat()
            workflow = record_graph(story_dir, diff["chapter"])
        if workflow["complete"]:
            queue_index(story_dir, diff["chapter"])
            workflow = chapter_status(story_dir, diff["chapter"])
    except (ValueError, OSError, yaml.YAMLError) as error:
        json_error(str(error))

    json_output({
        "status": "ok",
        "chapter": diff.get("chapter"),
        "graph_path": str(json_path),
        **stats,
        **graph.summary(),
        "workflow": workflow,
    })


if __name__ == "__main__":
    main()
