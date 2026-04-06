"""Index a chapter into ChromaDB for semantic search.

Usage:
    python scripts/index_chapter.py \
        --story-dir data/stories/civilization-disease \
        --chapter-num 2 \
        --chapter-file data/stories/civilization-disease/outputs/chapter_002.md
"""

import re
from pathlib import Path

from _common import get_args, get_retriever, json_output, json_error


def parse_story_log_entry(story_log_text: str, chapter_num: int) -> dict | None:
    """Parse a chapter entry from story_log.md."""
    pattern = rf"## 第{chapter_num}章[：:](.+?)(?=\n## |\Z)"
    match = re.search(pattern, story_log_text, re.DOTALL)
    if not match:
        return None

    entry_text = match.group(0)
    title = match.group(1).strip().split("\n")[0]

    def extract_field(field_name: str) -> str:
        m = re.search(rf"- {field_name}[：:](.+?)(?=\n-|\Z)", entry_text)
        return m.group(1).strip() if m else ""

    return {
        "title": title,
        "summary": extract_field("摘要"),
        "character_changes": extract_field("角色變化"),
        "foreshadow": extract_field("伏筆進展"),
        "emotional_arc": extract_field("情感基調"),
    }


def extract_character_names(character_changes: str) -> list[str]:
    """Extract character names from the 角色變化 field."""
    names = []
    for part in re.split(r"[；;]", character_changes):
        m = re.match(r"\s*([一-龥]{2,4}?)(?:的|從|展現|開始|登場|首次|建立|以|在|把|被|和|與|跟)", part)
        if m:
            names.append(m.group(1))
    return list(set(names)) if names else []


def main():
    args = get_args(
        ("--chapter-num", {"type": int, "required": True}),
        ("--chapter-file", {"type": str, "required": True}),
    )

    story_dir = Path(args.story_dir)
    chapter_num = args.chapter_num
    chapter_file = Path(args.chapter_file)

    if not story_dir.exists():
        json_error(f"Story directory not found: {story_dir}")

    # Read story_log.md
    story_log_path = story_dir / "runtime" / "story_log.md"
    if not story_log_path.exists():
        json_error(f"story_log.md not found: {story_log_path}")

    story_log_text = story_log_path.read_text(encoding="utf-8")
    entry = parse_story_log_entry(story_log_text, chapter_num)

    if not entry or not entry["summary"]:
        if chapter_file.exists():
            first_lines = chapter_file.read_text(encoding="utf-8").split("\n")[:5]
            title_line = next((line for line in first_lines if line.strip()), "")
            entry = {
                "title": title_line.strip("# ").strip(),
                "summary": f"第{chapter_num}章",
                "character_changes": "",
                "foreshadow": "",
                "emotional_arc": "",
            }
        else:
            json_error(f"No story_log entry for chapter {chapter_num} and chapter file not found")

    characters = extract_character_names(entry["character_changes"])

    # Save to ChromaDB only
    retriever = get_retriever(story_dir)
    retriever.add_chapter(
        chapter_id=chapter_num,
        summary=entry["summary"],
        characters=characters,
    )

    json_output({
        "status": "ok",
        "chapter_id": chapter_num,
        "title": entry["title"],
        "summary": entry["summary"],
        "characters": characters,
        "chroma_path": str(story_dir / "chroma"),
    })


if __name__ == "__main__":
    main()
