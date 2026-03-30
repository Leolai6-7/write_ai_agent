"""Repository for character states."""

from __future__ import annotations

import json

from config.models import CharacterState
from infrastructure.db import Database


class CharacterRepository:
    """CRUD operations for character states in SQLite."""

    def __init__(self, db: Database, max_memories: int = 10):
        self.db = db
        self.max_memories = max_memories

    def get(self, name: str) -> CharacterState | None:
        row = self.db.conn.execute(
            "SELECT * FROM character_states WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            return None
        return CharacterState(
            name=row["name"],
            current_location=row["current_location"] or "",
            emotional_state=row["emotional_state"] or "",
            power_level=row["power_level"] or "",
            relationships=json.loads(row["relationships"]) if row["relationships"] else {},
            key_memories=json.loads(row["key_memories"]) if row["key_memories"] else [],
            last_appeared=row["last_appeared"] or 0,
        )

    def get_many(self, names: list[str]) -> list[CharacterState]:
        if not names:
            return []
        placeholders = ",".join("?" * len(names))
        rows = self.db.conn.execute(
            f"SELECT * FROM character_states WHERE name IN ({placeholders})", names
        ).fetchall()
        return [
            CharacterState(
                name=r["name"],
                current_location=r["current_location"] or "",
                emotional_state=r["emotional_state"] or "",
                power_level=r["power_level"] or "",
                relationships=json.loads(r["relationships"]) if r["relationships"] else {},
                key_memories=json.loads(r["key_memories"]) if r["key_memories"] else [],
                last_appeared=r["last_appeared"] or 0,
            )
            for r in rows
        ]

    def save(self, state: CharacterState) -> None:
        self.db.conn.execute(
            """INSERT OR REPLACE INTO character_states
               (name, current_location, emotional_state, power_level,
                relationships, key_memories, last_appeared)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                state.name,
                state.current_location,
                state.emotional_state,
                state.power_level,
                json.dumps(state.relationships, ensure_ascii=False),
                json.dumps(state.key_memories, ensure_ascii=False),
                state.last_appeared,
            ),
        )
        self.db.conn.commit()

    def update_with_memory(self, name: str, change_desc: str, chapter_id: int) -> None:
        """Update character with a new memory entry from a chapter."""
        state = self.get(name) or CharacterState(name=name)
        state.key_memories.append(f"第{chapter_id}章: {change_desc}")
        state.key_memories = state.key_memories[-self.max_memories:]
        state.emotional_state = change_desc
        state.last_appeared = chapter_id
        self.save(state)
