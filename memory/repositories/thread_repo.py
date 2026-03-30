"""Repository for unresolved story threads."""

from __future__ import annotations

from infrastructure.db import Database


class ThreadRepository:
    """CRUD operations for unresolved story threads."""

    def __init__(self, db: Database):
        self.db = db

    def add(self, description: str, introduced_chapter: int) -> None:
        """Add a thread if it doesn't already exist."""
        self.db.conn.execute(
            """INSERT INTO unresolved_threads (description, introduced_chapter)
               SELECT ?, ? WHERE NOT EXISTS (
                   SELECT 1 FROM unresolved_threads WHERE description = ?
               )""",
            (description, introduced_chapter, description),
        )
        self.db.conn.commit()

    def resolve(self, description: str, resolved_chapter: int) -> None:
        self.db.conn.execute(
            "UPDATE unresolved_threads SET resolved_chapter = ? WHERE description = ?",
            (resolved_chapter, description),
        )
        self.db.conn.commit()

    def get_unresolved(self) -> list[dict]:
        rows = self.db.conn.execute(
            """SELECT description, introduced_chapter
               FROM unresolved_threads
               WHERE resolved_chapter IS NULL
               ORDER BY introduced_chapter""",
        ).fetchall()
        return [dict(r) for r in rows]

    def count_unresolved(self) -> int:
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM unresolved_threads WHERE resolved_chapter IS NULL"
        ).fetchone()[0]
