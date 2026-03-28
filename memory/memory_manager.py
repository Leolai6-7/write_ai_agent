"""Memory manager: assembles context from four memory layers with token budget control."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from config.models import ChapterContext, ChapterObjective, ChapterSummary, CharacterState
from infrastructure.db import Database
from infrastructure.logger import get_logger
from memory.token_budget import TokenBudget

if TYPE_CHECKING:
    from infrastructure.llm_client import LLMClient

logger = get_logger("memory_manager")


class MemoryManager:
    """Manages four-layer memory system with token budget control.

    Layers:
        1. Short-term: recent N chapter summaries (full detail)
        2. Long-term: compressed summaries (every 10 chapters)
        3. Character: per-character state tracking
        4. World: static settings + dynamic events
    """

    def __init__(
        self,
        db: Database,
        llm: LLMClient,
        short_term_window: int = 5,
        compression_interval: int = 10,
        token_budget: TokenBudget | None = None,
    ):
        self.db = db
        self.llm = llm
        self.short_term_window = short_term_window
        self.compression_interval = compression_interval
        self.budget = token_budget or TokenBudget()

    def assemble_context(self, objective: ChapterObjective) -> ChapterContext:
        """Assemble context for chapter generation within token budget."""
        self.budget.reset()

        short_term = self._get_short_term_memory(objective.chapter_id)
        long_term = self._get_long_term_memory()
        character_ctx = self._get_character_context(objective.characters_involved)
        world_ctx = self._get_world_context()

        # Truncate each layer to fit budget
        short_term_text = self.budget.truncate_text(
            short_term, "short_term", self.llm.count_tokens
        )
        long_term_text = self.budget.truncate_text(
            long_term, "long_term", self.llm.count_tokens
        )
        character_text = self.budget.truncate_text(
            character_ctx, "character", self.llm.count_tokens
        )
        world_text = self.budget.truncate_text(
            world_ctx, "world", self.llm.count_tokens
        )

        context = ChapterContext(
            short_term_memory=short_term_text,
            long_term_memory=long_term_text,
            character_context=character_text,
            world_context=world_text,
            total_tokens=self.budget.total_used(),
        )

        logger.info(
            "Context assembled: %d tokens used (budget: %d)",
            context.total_tokens, self.budget.total,
        )
        return context

    def _get_short_term_memory(self, current_chapter: int) -> str:
        """Get recent N chapter summaries."""
        start = max(1, current_chapter - self.short_term_window)
        rows = self.db.conn.execute(
            """SELECT chapter_id, one_line_summary, plot_events, emotional_arc
               FROM chapter_summaries
               WHERE chapter_id >= ? AND chapter_id < ?
               ORDER BY chapter_id DESC""",
            (start, current_chapter),
        ).fetchall()

        if not rows:
            return ""

        parts = ["## 近期章節摘要\n"]
        for row in rows:
            events = json.loads(row["plot_events"])
            events_str = "、".join(events[:3]) if events else "無"
            parts.append(
                f"第{row['chapter_id']}章: {row['one_line_summary']} "
                f"(事件: {events_str} | 情感: {row['emotional_arc']})"
            )
        return "\n".join(parts)

    def _get_long_term_memory(self) -> str:
        """Get compressed long-term memories."""
        rows = self.db.conn.execute(
            """SELECT chapter_range, compressed_summary
               FROM compressed_memories
               ORDER BY id""",
        ).fetchall()

        if not rows:
            return ""

        parts = ["## 故事回顧\n"]
        for row in rows:
            parts.append(f"[第{row['chapter_range']}章] {row['compressed_summary']}")

        # Also include unresolved threads
        threads = self.db.conn.execute(
            """SELECT description, introduced_chapter
               FROM unresolved_threads
               WHERE resolved_chapter IS NULL
               ORDER BY introduced_chapter""",
        ).fetchall()

        if threads:
            parts.append("\n## 未解決伏筆")
            for t in threads:
                parts.append(f"- (第{t['introduced_chapter']}章起) {t['description']}")

        return "\n".join(parts)

    def _get_character_context(self, characters: list[str]) -> str:
        """Get character states for involved characters."""
        if not characters:
            return ""

        placeholders = ",".join("?" * len(characters))
        rows = self.db.conn.execute(
            f"""SELECT name, current_location, emotional_state, relationships, key_memories
                FROM character_states
                WHERE name IN ({placeholders})""",
            characters,
        ).fetchall()

        if not rows:
            return ""

        parts = ["## 角色狀態\n"]
        for row in rows:
            relationships = json.loads(row["relationships"]) if row["relationships"] else {}
            memories = json.loads(row["key_memories"]) if row["key_memories"] else []
            rel_str = "、".join(f"{k}({v})" for k, v in relationships.items()) if relationships else "無"
            mem_str = "；".join(memories[-3:]) if memories else "無"  # Last 3 memories
            parts.append(
                f"【{row['name']}】位置: {row['current_location']} | "
                f"情緒: {row['emotional_state']} | 關係: {rel_str}\n"
                f"  近期記憶: {mem_str}"
            )
        return "\n".join(parts)

    def _get_world_context(self) -> str:
        """Get world setting context. Returns static world info."""
        # For now, return a minimal world context
        # Phase 3: load from YAML + dynamic world state from DB
        return ""

    # ── Memory Updates ───────────────────────────────────────────

    def save_summary(self, summary: ChapterSummary, full_text_path: str = "") -> None:
        """Save chapter summary to database."""
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
        logger.info("Saved summary for chapter %d", summary.chapter_id)

        # Update unresolved threads
        for thread in summary.unresolved_threads:
            self.db.conn.execute(
                """INSERT INTO unresolved_threads (description, introduced_chapter)
                   SELECT ?, ? WHERE NOT EXISTS (
                       SELECT 1 FROM unresolved_threads WHERE description = ?
                   )""",
                (thread, summary.chapter_id, thread),
            )
        self.db.conn.commit()

        # Check if compression is needed
        count = self.db.conn.execute(
            "SELECT COUNT(*) FROM chapter_summaries"
        ).fetchone()[0]
        if count > 0 and count % self.compression_interval == 0:
            self._compress_memories(count)

    def update_character(self, state: CharacterState) -> None:
        """Update character state in database."""
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

    def _compress_memories(self, up_to_chapter: int) -> None:
        """Compress old chapter summaries into long-term memory."""
        start = max(1, up_to_chapter - self.compression_interval + 1)
        end = up_to_chapter

        rows = self.db.conn.execute(
            """SELECT one_line_summary FROM chapter_summaries
               WHERE chapter_id BETWEEN ? AND ?
               ORDER BY chapter_id""",
            (start, end),
        ).fetchall()

        if not rows:
            return

        summaries = [row["one_line_summary"] for row in rows]
        compressed = " → ".join(summaries)  # Simple compression for now
        # Phase 2.7: Use SummarizerAgent for LLM-based compression

        self.db.conn.execute(
            """INSERT INTO compressed_memories (chapter_range, compressed_summary, critical_events)
               VALUES (?, ?, ?)""",
            (f"{start}-{end}", compressed, "[]"),
        )
        self.db.conn.commit()
        logger.info("Compressed memories for chapters %d-%d", start, end)

    def get_last_chapter_id(self) -> int:
        """Get the ID of the last completed chapter."""
        row = self.db.conn.execute(
            "SELECT MAX(chapter_id) FROM chapter_summaries"
        ).fetchone()
        return row[0] if row[0] is not None else 0
