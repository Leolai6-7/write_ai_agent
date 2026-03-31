"""Repository for foreshadowing threads."""

from __future__ import annotations

import json

from config.models import Foreshadow, ChapterForeshadowDirective
from infrastructure.db import Database


class ForeshadowRepository:
    """CRUD for foreshadowing lifecycle tracking."""

    def __init__(self, db: Database):
        self.db = db

    def save_plan(self, foreshadows: list[Foreshadow]) -> None:
        """Save a batch of foreshadowing plans."""
        for f in foreshadows:
            self.db.conn.execute(
                """INSERT INTO foreshadows
                   (description, plant_chapter, hint_chapters, resolve_chapter,
                    importance, related_characters, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'planned')""",
                (
                    f.description,
                    f.plant_chapter,
                    json.dumps(f.hint_chapters),
                    f.resolve_chapter,
                    f.importance,
                    json.dumps(f.related_characters, ensure_ascii=False),
                ),
            )
        self.db.conn.commit()

    def get_directive(self, chapter_id: int) -> ChapterForeshadowDirective:
        """Get foreshadowing instructions for a specific chapter."""
        plant = []
        hint = []
        resolve = []

        # Chapters where we plant
        rows = self.db.conn.execute(
            "SELECT description FROM foreshadows WHERE plant_chapter = ?", (chapter_id,)
        ).fetchall()
        plant = [r["description"] for r in rows]

        # Chapters where we hint
        all_rows = self.db.conn.execute(
            "SELECT description, hint_chapters FROM foreshadows WHERE status != 'resolved'"
        ).fetchall()
        for r in all_rows:
            hints = json.loads(r["hint_chapters"]) if r["hint_chapters"] else []
            if chapter_id in hints:
                hint.append(r["description"])

        # Chapters where we resolve
        rows = self.db.conn.execute(
            "SELECT description FROM foreshadows WHERE resolve_chapter = ?", (chapter_id,)
        ).fetchall()
        resolve = [r["description"] for r in rows]

        return ChapterForeshadowDirective(plant=plant, hint=hint, resolve=resolve)

    def mark_resolved(self, description: str) -> None:
        self.db.conn.execute(
            "UPDATE foreshadows SET status = 'resolved' WHERE description = ?",
            (description,),
        )
        self.db.conn.commit()

    def get_all(self) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT * FROM foreshadows ORDER BY plant_chapter"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_unresolved(self) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT * FROM foreshadows WHERE status != 'resolved' ORDER BY plant_chapter"
        ).fetchall()
        return [dict(r) for r in rows]
