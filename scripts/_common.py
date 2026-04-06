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

    lines = [line.strip() for line in section_text.strip().split("\n") if line.strip()]

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


def extract_sections_from_files(files: list[Path], name: str, heading_level: str = "## ") -> str:
    """Search multiple files for sections matching a name, combine results."""
    results = []
    for f in files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        section = extract_section(text, name, heading_level)
        if section:
            results.append(section)
    return "\n\n".join(results)
