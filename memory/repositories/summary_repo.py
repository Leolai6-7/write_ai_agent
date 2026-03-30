"""Repository for chapter summaries."""

from __future__ import annotations

import json

from config.models import ChapterSummary
from infrastructure.db import Database


class SummaryRepository:
    """CRUD operations for chapter summaries in SQLite."""

    def __init__(self, db: Database):
        self.db = db

    def save(self, summary: ChapterSummary, full_text_path: str = "") -> None:
        self.db.conn.execute(
            """INSERT OR REPLACE INTO chapter_summaries
               (chapter_id, plot_events, character_changes, world_state_changes,
                unresolved_threads, emotional_arc, one_line_summary, full_text_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                summary.chapter_id,
                json.dumps(summary.plot_events, ensure_ascii=False),
                json.dumps(summary.character_changes, ensure_ascii=False),
                json.dumps(summary.world_state_changes, ensure_ascii=False),
                json.dumps(summary.unresolved_threads, ensure_ascii=False),
                summary.emotional_arc,
                summary.one_line_summary,
                full_text_path,
            ),
        )
        self.db.conn.commit()

    def get_by_id(self, chapter_id: int) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM chapter_summaries WHERE chapter_id = ?", (chapter_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_recent(self, before_chapter: int, limit: int = 5) -> list[dict]:
        start = max(1, before_chapter - limit)
        rows = self.db.conn.execute(
            """SELECT chapter_id, one_line_summary, plot_events, emotional_arc
               FROM chapter_summaries
               WHERE chapter_id >= ? AND chapter_id < ?
               ORDER BY chapter_id DESC""",
            (start, before_chapter),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_range(self, start: int, end: int) -> list[dict]:
        rows = self.db.conn.execute(
            """SELECT chapter_id, one_line_summary, plot_events, unresolved_threads
               FROM chapter_summaries
               WHERE chapter_id BETWEEN ? AND ?
               ORDER BY chapter_id""",
            (start, end),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_previous_summary(self, chapter_id: int) -> str:
        """Get one-line summary of the previous chapter."""
        if chapter_id <= 1:
            return ""
        row = self.db.conn.execute(
            "SELECT one_line_summary FROM chapter_summaries WHERE chapter_id = ?",
            (chapter_id - 1,),
        ).fetchone()
        return row["one_line_summary"] if row else ""

    def count(self) -> int:
        return self.db.conn.execute("SELECT COUNT(*) FROM chapter_summaries").fetchone()[0]

    def max_id(self) -> int:
        row = self.db.conn.execute("SELECT MAX(chapter_id) FROM chapter_summaries").fetchone()
        return row[0] if row[0] is not None else 0
