"""SQLite database management for novel memory storage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from infrastructure.logger import get_logger

logger = get_logger("db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS chapter_summaries (
    chapter_id INTEGER PRIMARY KEY,
    plot_events TEXT NOT NULL,
    character_changes TEXT NOT NULL,
    world_state_changes TEXT NOT NULL,
    unresolved_threads TEXT NOT NULL,
    emotional_arc TEXT NOT NULL,
    one_line_summary TEXT NOT NULL,
    full_text_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS compressed_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_range TEXT NOT NULL,
    compressed_summary TEXT NOT NULL,
    critical_events TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS character_states (
    name TEXT PRIMARY KEY,
    current_location TEXT DEFAULT '',
    emotional_state TEXT DEFAULT '',
    power_level TEXT DEFAULT '',
    relationships TEXT DEFAULT '{}',
    key_memories TEXT DEFAULT '[]',
    last_appeared INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS unresolved_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    introduced_chapter INTEGER NOT NULL,
    resolved_chapter INTEGER,
    related_characters TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS character_profiles (
    name TEXT PRIMARY KEY,
    role TEXT DEFAULT 'ally',
    age TEXT DEFAULT '',
    personality TEXT DEFAULT '[]',
    speaking_style TEXT DEFAULT '',
    motivation TEXT DEFAULT '',
    background TEXT DEFAULT '',
    arc_summary TEXT DEFAULT '',
    relationships TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS foreshadows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    plant_chapter INTEGER NOT NULL,
    hint_chapters TEXT DEFAULT '[]',
    resolve_chapter INTEGER NOT NULL,
    importance TEXT DEFAULT 'minor',
    related_characters TEXT DEFAULT '[]',
    status TEXT DEFAULT 'planned'
);

CREATE TABLE IF NOT EXISTS world_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    chapter_id INTEGER NOT NULL,
    event_type TEXT DEFAULT 'world_change',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """SQLite database wrapper for novel memory storage."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def initialize(self) -> None:
        """Create tables if they don't exist."""
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        logger.info("Database initialized at %s", self.db_path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, *args):
        self.close()
