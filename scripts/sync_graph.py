"""Sync story_graph.md into SQLite for structured queries.

Usage:
    python scripts/sync_graph.py \
        --story-dir data/stories/civilization-disease
"""

import json
import re
from pathlib import Path

from _common import get_args, get_db, parse_md_table, json_output, json_error, PROJECT_ROOT

import sys
sys.path.insert(0, str(PROJECT_ROOT))

from memory.repositories.character_repo import CharacterRepository
from memory.repositories.foreshadow_repo import ForeshadowRepository
from memory.repositories.world_repo import WorldRepository


def parse_chapter_nums(text: str) -> list[int]:
    """Extract chapter numbers from text like 'ch2,ch4,ch6' or '2,4,6' or '1,3,5,7'."""
    return [int(n) for n in re.findall(r"\d+", text)]


def sync_characters(db, rows: list[dict]) -> int:
    """Sync 角色出場表 into character_states table."""
    repo = CharacterRepository(db)
    count = 0
    for row in rows:
        name = row.get("角色", "").strip()
        if not name:
            continue
        chapters = parse_chapter_nums(row.get("出場章節", ""))
        last_appeared = max(chapters) if chapters else 0
        events = row.get("主要事件", "")

        # Upsert: check if exists, then update or insert
        existing = repo.get(name)
        if existing:
            db.conn.execute(
                "UPDATE character_states SET last_appeared = ?, key_memories = ? WHERE name = ?",
                (last_appeared, json.dumps([events], ensure_ascii=False), name),
            )
        else:
            db.conn.execute(
                """INSERT INTO character_states (name, last_appeared, key_memories)
                   VALUES (?, ?, ?)""",
                (name, last_appeared, json.dumps([events], ensure_ascii=False)),
            )
        count += 1
    db.conn.commit()
    return count


def sync_foreshadows(db, rows: list[dict]) -> int:
    """Sync 伏筆追蹤 into foreshadows table (full replace)."""
    # Clear existing
    db.conn.execute("DELETE FROM foreshadows")

    count = 0
    for row in rows:
        desc = row.get("伏筆", "").strip()
        if not desc:
            continue

        plant_chapters = parse_chapter_nums(row.get("植入", ""))
        hint_chapters = parse_chapter_nums(row.get("暗示", ""))
        resolve_chapters = parse_chapter_nums(row.get("收束", ""))
        status = row.get("狀態", "活躍").strip()

        plant_ch = plant_chapters[0] if plant_chapters else 0
        resolve_ch = resolve_chapters[0] if resolve_chapters else 0
        mapped_status = "resolved" if status == "已收束" else "active"

        db.conn.execute(
            """INSERT INTO foreshadows
               (description, plant_chapter, hint_chapters, resolve_chapter,
                importance, related_characters, status)
               VALUES (?, ?, ?, ?, 'major', '[]', ?)""",
            (desc, plant_ch, json.dumps(hint_chapters), resolve_ch, mapped_status),
        )
        count += 1
    db.conn.commit()
    return count


def sync_causal_chains(db, rows: list[dict]) -> int:
    """Sync 因果鏈 into world_events table."""
    # Clear existing causal events to avoid duplicates
    db.conn.execute("DELETE FROM world_events WHERE event_type = 'causal_link'")

    count = 0
    for row in rows:
        cause = row.get("原因", "").strip()
        result = row.get("結果", "").strip()
        cause_ch = parse_chapter_nums(row.get("章節", ""))

        if not cause:
            continue

        # Use the first chapter column as the chapter_id
        ch_id = cause_ch[0] if cause_ch else 0
        desc = f"{cause} → {result}"

        db.conn.execute(
            "INSERT INTO world_events (description, chapter_id, event_type) VALUES (?, ?, 'causal_link')",
            (desc, ch_id),
        )
        count += 1
    db.conn.commit()
    return count


def sync_numerical_settings(db, rows: list[dict]) -> int:
    """Sync 已確立的數值設定 into world_events table."""
    db.conn.execute("DELETE FROM world_events WHERE event_type = 'numerical_setting'")

    count = 0
    for row in rows:
        setting = row.get("設定", "").strip()
        value = row.get("值", "").strip()
        ch_nums = parse_chapter_nums(row.get("確立章節", ""))

        if not setting:
            continue

        ch_id = ch_nums[0] if ch_nums else 0
        note = row.get("備註", "").strip()
        desc = f"{setting} = {value}" + (f"（{note}）" if note else "")

        db.conn.execute(
            "INSERT INTO world_events (description, chapter_id, event_type) VALUES (?, ?, 'numerical_setting')",
            (desc, ch_id),
        )
        count += 1
    db.conn.commit()
    return count


def main():
    args = get_args()
    story_dir = Path(args.story_dir)

    graph_path = story_dir / "planning" / "story_graph.md"
    if not graph_path.exists():
        json_error(f"story_graph.md not found: {graph_path}")

    graph_text = graph_path.read_text(encoding="utf-8")
    db = get_db(story_dir)

    # Sync each section
    stats = {}

    char_rows = parse_md_table(graph_text, "## 角色出場表")
    stats["characters"] = sync_characters(db, char_rows)

    foreshadow_rows = parse_md_table(graph_text, "## 伏筆追蹤")
    stats["foreshadows"] = sync_foreshadows(db, foreshadow_rows)

    # 因果鏈 has duplicate column name "章節" — parse manually
    causal_rows = parse_md_table(graph_text, "## 因果鏈")
    stats["causal_links"] = sync_causal_chains(db, causal_rows)

    numerical_rows = parse_md_table(graph_text, "## 已確立的數值設定")
    stats["numerical_settings"] = sync_numerical_settings(db, numerical_rows)

    db.close()

    json_output({
        "status": "ok",
        "synced": stats,
        "db_path": str(story_dir / "novel.db"),
    })


if __name__ == "__main__":
    main()
