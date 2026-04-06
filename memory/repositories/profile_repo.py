"""Repository for character profiles (design-phase, distinct from runtime CharacterState)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from config.models import CharacterProfile
from infrastructure.db import Database

if TYPE_CHECKING:
    from config.models import CharacterCast


class ProfileRepository:
    """CRUD for character profiles designed during conception phase."""

    def __init__(self, db: Database):
        self.db = db

    def save(self, profile: CharacterProfile) -> None:
        self.db.conn.execute(
            """INSERT OR REPLACE INTO character_profiles
               (name, role, age, personality, speaking_style, motivation,
                background, arc_summary, relationships)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile.name,
                profile.role,
                profile.age,
                json.dumps(profile.personality, ensure_ascii=False),
                profile.speaking_style,
                profile.motivation,
                profile.background,
                profile.arc_summary,
                json.dumps(profile.relationships, ensure_ascii=False),
            ),
        )
        self.db.conn.commit()

    def save_cast(self, cast: "CharacterCast") -> None:
        for char in cast.characters:
            self.save(char)

    def get(self, name: str) -> CharacterProfile | None:
        row = self.db.conn.execute(
            "SELECT * FROM character_profiles WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            return None
        return CharacterProfile(
            name=row["name"],
            role=row["role"],
            age=row["age"] or "",
            personality=json.loads(row["personality"]) if row["personality"] else [],
            speaking_style=row["speaking_style"] or "",
            motivation=row["motivation"] or "",
            background=row["background"] or "",
            arc_summary=row["arc_summary"] or "",
            relationships=json.loads(row["relationships"]) if row["relationships"] else {},
        )

    def get_all(self) -> list[CharacterProfile]:
        rows = self.db.conn.execute("SELECT * FROM character_profiles ORDER BY name").fetchall()
        return [
            CharacterProfile(
                name=r["name"], role=r["role"], age=r["age"] or "",
                personality=json.loads(r["personality"]) if r["personality"] else [],
                speaking_style=r["speaking_style"] or "",
                motivation=r["motivation"] or "",
                background=r["background"] or "",
                arc_summary=r["arc_summary"] or "",
                relationships=json.loads(r["relationships"]) if r["relationships"] else {},
            )
            for r in rows
        ]

    def get_by_names(self, names: list[str]) -> list[CharacterProfile]:
        if not names:
            return []
        placeholders = ",".join("?" * len(names))
        rows = self.db.conn.execute(
            f"SELECT * FROM character_profiles WHERE name IN ({placeholders})", names
        ).fetchall()
        return [
            CharacterProfile(
                name=r["name"], role=r["role"], age=r["age"] or "",
                personality=json.loads(r["personality"]) if r["personality"] else [],
                speaking_style=r["speaking_style"] or "",
                motivation=r["motivation"] or "",
                background=r["background"] or "",
                arc_summary=r["arc_summary"] or "",
                relationships=json.loads(r["relationships"]) if r["relationships"] else {},
            )
            for r in rows
        ]
