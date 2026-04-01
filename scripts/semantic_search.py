"""Query ChromaDB for semantically similar past chapters.

Usage:
    python scripts/semantic_search.py \
        --story-dir data/stories/civilization-disease \
        --query "沈逸對前妻的記憶" \
        --n 3
"""

from pathlib import Path

from _common import get_args, get_retriever, json_output, json_error


def main():
    args = get_args(
        ("--query", {"type": str, "required": True}),
        ("--characters", {"type": str, "default": ""}),
        ("--n", {"type": int, "default": 5}),
    )

    story_dir = Path(args.story_dir)
    chroma_dir = story_dir / "chroma"

    if not chroma_dir.exists():
        json_output({"results": [], "message": "no chapters indexed yet"})

    retriever = get_retriever(story_dir)
    count = retriever.get_count()

    if count == 0:
        json_output({"results": [], "message": "no chapters indexed yet"})

    characters = [c.strip() for c in args.characters.split(",") if c.strip()] if args.characters else None

    results = retriever.query(
        query_text=args.query,
        n_results=args.n,
        max_distance=1.0,  # Don't filter by distance; let the caller decide relevance
        filter_characters=characters,
    )

    json_output({
        "results": results,
        "total_indexed": count,
    })


if __name__ == "__main__":
    main()
