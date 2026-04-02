"""Apply a chapter diff to story_graph.json (incremental update).

Usage:
    python scripts/update_graph.py \
        --story-dir data/stories/civilization-disease \
        --diff /tmp/chapter_6_diff.yaml
"""

import json
from pathlib import Path

import yaml

from _common import get_args, json_output, json_error
from story_graph_nx import StoryGraph


def main():
    args = get_args(
        ("--diff", {"type": str, "required": True, "help": "Path to chapter diff YAML"}),
    )

    story_dir = Path(args.story_dir)
    diff_path = Path(args.diff)

    if not diff_path.exists():
        json_error(f"Diff file not found: {diff_path}")

    json_path = story_dir / "runtime" / "story_graph.json"

    # Load existing graph
    graph = StoryGraph(json_path)
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            raw = json.load(f)
        if "characters" in raw:
            graph.load_flat(raw)
        else:
            graph.load()

    # Load and apply diff
    diff = yaml.safe_load(diff_path.read_text(encoding="utf-8"))
    stats = graph.apply_chapter_diff(diff)

    # Save as flat JSON
    graph.save_flat()

    json_output({
        "status": "ok",
        "chapter": diff.get("chapter"),
        "graph_path": str(json_path),
        **stats,
        **graph.summary(),
    })


if __name__ == "__main__":
    main()
