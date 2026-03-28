"""Tests for MemoryManager."""

import pytest

from config.models import ChapterSummary, ChapterObjective, CharacterState
from infrastructure.db import Database
from memory.memory_manager import MemoryManager
from tests.conftest import MockLLMClient


@pytest.fixture
def memory(tmp_db):
    db = Database(tmp_db)
    db.initialize()
    llm = MockLLMClient()
    mgr = MemoryManager(db=db, llm=llm, short_term_window=3, compression_interval=5)
    yield mgr
    db.close()


def test_save_and_retrieve_summary(memory):
    summary = ChapterSummary(
        chapter_id=1,
        plot_events=["到達圖書館", "遇見米娜"],
        character_changes={"伊澤": "從緊張變為好奇"},
        world_state_changes=["圖書館大門開啟"],
        unresolved_threads=["父親的線索"],
        emotional_arc="期待",
        one_line_summary="伊澤到達圖書館並遇見守護者米娜",
    )
    memory.save_summary(summary)

    row = memory.db.conn.execute(
        "SELECT * FROM chapter_summaries WHERE chapter_id = 1"
    ).fetchone()
    assert row is not None
    assert row["one_line_summary"] == "伊澤到達圖書館並遇見守護者米娜"


def test_get_last_chapter_id(memory):
    assert memory.get_last_chapter_id() == 0

    for i in range(1, 4):
        memory.save_summary(ChapterSummary(
            chapter_id=i,
            plot_events=[f"event_{i}"],
            character_changes={},
            world_state_changes=[],
            unresolved_threads=[],
            emotional_arc="test",
            one_line_summary=f"Chapter {i}",
        ))

    assert memory.get_last_chapter_id() == 3


def test_assemble_context_empty(memory, sample_objective):
    ctx = memory.assemble_context(sample_objective)
    assert ctx.short_term_memory == ""
    assert ctx.total_tokens == 0


def test_assemble_context_with_data(memory):
    # Insert some summaries
    for i in range(1, 6):
        memory.save_summary(ChapterSummary(
            chapter_id=i,
            plot_events=[f"event_{i}"],
            character_changes={},
            world_state_changes=[],
            unresolved_threads=[],
            emotional_arc="test",
            one_line_summary=f"第{i}章摘要",
        ))

    objective = ChapterObjective(
        chapter_id=6, title="test", objective="test",
        key_events=[], characters_involved=["伊澤"],
        emotional_tone="test",
    )
    ctx = memory.assemble_context(objective)
    assert "摘要" in ctx.short_term_memory
    assert ctx.total_tokens > 0


def test_update_character(memory):
    state = CharacterState(
        name="伊澤",
        current_location="圖書館",
        emotional_state="好奇",
        key_memories=["遇見米娜"],
        last_appeared=1,
    )
    memory.update_character(state)

    row = memory.db.conn.execute(
        "SELECT * FROM character_states WHERE name = '伊澤'"
    ).fetchone()
    assert row is not None
    assert row["current_location"] == "圖書館"


def test_compression_triggers(memory):
    """Compression should trigger every 5 chapters (compression_interval=5)."""
    for i in range(1, 6):
        memory.save_summary(ChapterSummary(
            chapter_id=i,
            plot_events=[f"event_{i}"],
            character_changes={},
            world_state_changes=[],
            unresolved_threads=[],
            emotional_arc="test",
            one_line_summary=f"Chapter {i}",
        ))

    rows = memory.db.conn.execute(
        "SELECT * FROM compressed_memories"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["chapter_range"] == "1-5"


def test_unresolved_threads_tracked(memory):
    memory.save_summary(ChapterSummary(
        chapter_id=1,
        plot_events=["event"],
        character_changes={},
        world_state_changes=[],
        unresolved_threads=["父親的下落", "神秘符文"],
        emotional_arc="test",
        one_line_summary="test",
    ))

    threads = memory.db.conn.execute(
        "SELECT * FROM unresolved_threads"
    ).fetchall()
    assert len(threads) == 2
