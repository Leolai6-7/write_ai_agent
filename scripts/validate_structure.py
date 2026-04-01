"""Validate that all characters in the beat sheet exist in character_cast.md.

Usage:
    python scripts/validate_structure.py \
        --story-dir data/stories/civilization-disease

Checks:
1. Every character name in structure.md's 角色 column exists in character_cast.md
2. Reports missing characters with the chapters they appear in
"""

import re
from pathlib import Path

from _common import get_args, json_output, json_error


def extract_beat_sheet_characters(structure_text: str) -> dict[str, list[int]]:
    """Extract all character names from the beat sheet and which chapters they appear in."""
    characters: dict[str, list[int]] = {}

    for line in structure_text.split("\n"):
        # Match beat sheet rows: | N | title | line | objective | events | tone | characters | location | foreshadow |
        m = re.match(r"^\|\s*(\d+)\s*\|", line)
        if not m:
            continue

        chapter_num = int(m.group(1))

        # Split by | and find the 角色 column (7th column, index 6)
        cells = [c.strip() for c in line.split("|")]
        # cells after split by |: ['', '章', '標題', '線', '目標', '關鍵事件', '情感', '角色', '地點', '伏筆', '']
        # 角色 is at index 7
        if len(cells) < 9:
            continue

        character_cell = cells[7]  # 角色 column
        names = [n.strip() for n in character_cell.split(",") if re.match(r'^[\u4e00-\u9fff]', n.strip())]
        for name in names:
            name = re.sub(r'[（(].*?[）)]', '', name).strip()  # Remove parenthetical notes
            if len(name) < 2:
                continue
            if name not in characters:
                characters[name] = []
            characters[name].append(chapter_num)

    return characters


def check_character_exists(character_cast_text: str, name: str) -> bool:
    """Check if a character name exists anywhere in character_cast.md."""
    return name in character_cast_text


def main():
    args = get_args()
    story_dir = Path(args.story_dir)

    structure_path = story_dir / "planning" / "structure.md"
    cast_path = story_dir / "world" / "character_cast.md"

    if not structure_path.exists():
        json_error(f"structure.md not found: {structure_path}")
    if not cast_path.exists():
        json_error(f"character_cast.md not found: {cast_path}")

    structure_text = structure_path.read_text(encoding="utf-8")
    cast_text = cast_path.read_text(encoding="utf-8")

    characters = extract_beat_sheet_characters(structure_text)

    found = []
    missing = []

    for name, chapters in sorted(characters.items()):
        if check_character_exists(cast_text, name):
            # Also check if it's in a heading (Grep-findable)
            in_heading = bool(re.search(rf"^## .*{re.escape(name)}", cast_text, re.MULTILINE))
            found.append({
                "name": name,
                "chapters": chapters,
                "in_heading": in_heading,
            })
        else:
            missing.append({
                "name": name,
                "chapters": chapters,
            })

    # Characters in headings but not searchable by name
    not_in_heading = [c for c in found if not c["in_heading"]]

    json_output({
        "status": "ok" if not missing else "missing_characters",
        "total_characters": len(characters),
        "found": len(found),
        "missing": len(missing),
        "missing_characters": missing,
        "not_in_heading": [{"name": c["name"], "chapters": c["chapters"]} for c in not_in_heading],
    })


if __name__ == "__main__":
    main()
