"""Tests for SQLite database module."""

from infrastructure.db import Database


def test_database_initializes(tmp_db):
    with Database(tmp_db) as db:
        # Tables should exist
        cursor = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "chapter_summaries" in tables
        assert "compressed_memories" in tables
        assert "character_states" in tables
        assert "unresolved_threads" in tables


def test_database_insert_and_query(tmp_db):
    with Database(tmp_db) as db:
        db.conn.execute(
            """INSERT INTO chapter_summaries
               (chapter_id, plot_events, character_changes, world_state_changes,
                unresolved_threads, emotional_arc, one_line_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1, '["event1"]', '{}', '[]', '[]', "tense", "Chapter 1 summary"),
        )
        db.conn.commit()

        row = db.conn.execute(
            "SELECT * FROM chapter_summaries WHERE chapter_id = 1"
        ).fetchone()
        assert row is not None
        assert row["one_line_summary"] == "Chapter 1 summary"


def test_database_creates_parent_dirs(tmp_path):
    deep_path = tmp_path / "a" / "b" / "c" / "test.db"
    with Database(deep_path) as db:
        assert deep_path.exists()
