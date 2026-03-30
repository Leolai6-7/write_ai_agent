"""Repository for compressed long-term memories."""

from __future__ import annotations

import json

from infrastructure.db import Database


class CompressedRepository:
    """CRUD operations for compressed memory summaries."""

    def __init__(self, db: Database):
        self.db = db

    def save(self, chapter_range: str, compressed_summary: str, critical_events: list[str]) -> None:
        self.db.conn.execute(
            """INSERT INTO compressed_memories (chapter_range, compressed_summary, critical_events)
               VALUES (?, ?, ?)""",
            (chapter_range, compressed_summary, json.dumps(critical_events, ensure_ascii=False)),
        )
        self.db.conn.commit()

    def get_all(self) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT chapter_range, compressed_summary FROM compressed_memories ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        return self.db.conn.execute("SELECT COUNT(*) FROM compressed_memories").fetchone()[0]
