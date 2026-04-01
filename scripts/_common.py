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


def parse_md_table(text: str, section_heading: str) -> list[dict]:
    """Parse a markdown table under a given heading into list of dicts.

    Args:
        text: Full markdown file content
        section_heading: The heading to search for (e.g., "## 角色出場表")

    Returns:
        List of dicts keyed by column headers
    """
    # Find the section
    pattern = rf"^{re.escape(section_heading)}\s*$"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return []

    # Extract lines after heading until next heading or end
    rest = text[match.end():]
    next_heading = re.search(r"^##\s", rest, re.MULTILINE)
    section_text = rest[:next_heading.start()] if next_heading else rest

    lines = [l.strip() for l in section_text.strip().split("\n") if l.strip()]

    # Need at least header + separator + 1 data row
    if len(lines) < 3:
        return []

    # Parse header
    headers = [h.strip() for h in lines[0].split("|") if h.strip()]

    # Skip separator line (lines[1])
    rows = []
    for line in lines[2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= len(headers):
            rows.append(dict(zip(headers, cells[:len(headers)])))

    return rows
