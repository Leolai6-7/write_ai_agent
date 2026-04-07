"""Shared utilities for bridge scripts between skill pipeline and Python infrastructure."""

import argparse
import json
import re
import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.db import Database  # noqa: E402
from memory.retrieval import SemanticRetriever  # noqa: E402


def get_args(*extra_args: tuple[str, dict]) -> argparse.Namespace:
    """Parse CLI arguments. Always includes --story-dir."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--story-dir", required=True, help="Path to story directory")
    for name, kwargs in extra_args:
        parser.add_argument(name, **kwargs)
    return parser.parse_args()


def get_db(story_dir: Path) -> Database:
    """Create and initialize SQLite database for a story."""
    db = Database(story_dir / "novel.db")
    db.initialize()
    return db


def get_retriever(story_dir: Path) -> SemanticRetriever:
    """Create ChromaDB retriever for a story."""
    chroma_dir = story_dir / "chroma"
    chroma_dir.mkdir(parents=True, exist_ok=True)
    return SemanticRetriever(chroma_dir)


def json_output(data: dict) -> None:
    """Print JSON to stdout and exit cleanly."""
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(0)


def json_error(msg: str) -> None:
    """Print error JSON to stderr and exit with code 1."""
    print(json.dumps({"error": msg}, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


def extract_section(text: str, name: str, heading_level: str = "## ") -> str:
    """Extract a full section from markdown by searching for a name in headings.

    Searches for a heading containing `name`, then returns everything from
    that heading to the next heading of the same level.

    Args:
        text: Full markdown file content
        name: Name to search for in headings
        heading_level: "## " or "### "

    Returns:
        The full section text, or empty string if not found.
    """
    level_pattern = re.escape(heading_level.strip())
    # Find heading containing the name
    pattern = rf"^({level_pattern}\s+.*{re.escape(name)}.*?)$"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return ""

    start = match.start()
    # Find next heading of same or higher level
    rest = text[match.end():]
    next_match = re.search(rf"^{level_pattern}\s", rest, re.MULTILINE)
    if next_match:
        end = match.end() + next_match.start()
    else:
        end = len(text)

    return text[start:end].strip()


