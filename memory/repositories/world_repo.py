"""Repository for world events and dynamic state."""

from __future__ import annotations

from infrastructure.db import Database


class WorldRepository:
    """CRUD for world events tracked during story progression."""

    def __init__(self, db: Database):
        self.db = db

    def add_event(self, description: str, chapter_id: int, event_type: str = "world_change") -> None:
        self.db.conn.execute(
            "INSERT INTO world_events (description, chapter_id, event_type) VALUES (?, ?, ?)",
            (description, chapter_id, event_type),
        )
        self.db.conn.commit()

    def get_events(self, limit: int = 20) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT * FROM world_events ORDER BY chapter_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_events_for_chapter(self, chapter_id: int) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT * FROM world_events WHERE chapter_id = ?", (chapter_id,)
        ).fetchall()
        return [dict(r) for r in rows]
