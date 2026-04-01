"""Sync story_graph.md into a NetworkX graph (JSON).

Usage:
    python scripts/sync_graph.py \
        --story-dir data/stories/civilization-disease
"""

from pathlib import Path

from _common import get_args, json_output, json_error
from story_graph_nx import StoryGraph


def main():
    args = get_args()
    story_dir = Path(args.story_dir)

    md_path = story_dir / "runtime" / "story_graph.md"
    if not md_path.exists():
        json_error(f"story_graph.md not found: {md_path}")

    json_path = story_dir / "runtime" / "story_graph.json"
    graph = StoryGraph(json_path)
    stats = graph.sync_from_markdown(md_path)
    graph.save()

    json_output({
        "status": "ok",
        "graph_path": str(json_path),
        **graph.summary(),
    })


if __name__ == "__main__":
    main()
