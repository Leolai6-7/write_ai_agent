"""Memory manager: assembles context from four memory layers with token budget control."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from config.models import ChapterContext, ChapterObjective, ChapterSummary, CharacterState
from infrastructure.db import Database
from infrastructure.logger import get_logger
from memory.token_budget import TokenBudget

from memory.retrieval import SemanticRetriever
from memory.world_state import WorldState

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
        retriever: SemanticRetriever | None = None,
        world_state: WorldState | None = None,
    ):
        self.db = db
        self.llm = llm
        self.short_term_window = short_term_window
        self.compression_interval = compression_interval
        self.budget = token_budget or TokenBudget()
        self.retriever = retriever
        self.world_state = world_state

    def assemble_context(self, objective: ChapterObjective) -> ChapterContext:
        """Assemble context for chapter generation within token budget."""
        self.budget.reset()

        short_term = self._get_short_term_memory(objective.chapter_id)
        long_term = self._get_long_term_memory()
        character_ctx = self._get_character_context(objective.characters_involved)
        world_ctx = self._get_world_context(objective.characters_involved)

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

        # Semantic retrieval for relevant memories
        relevant = self._get_relevant_memories(objective)

        context = ChapterContext(
            short_term_memory=short_term_text,
            long_term_memory=long_term_text,
            character_context=character_text,
            world_context=world_text,
            relevant_memories=relevant,
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

    def _get_world_context(self, characters: list[str] | None = None) -> str:
        """Get world setting context from YAML files."""
        if not self.world_state:
            return ""
        return self.world_state.get_context(characters_involved=characters)

    def _get_relevant_memories(self, objective: ChapterObjective) -> list[str]:
        """Use semantic retrieval to find relevant past chapter summaries."""
        if not self.retriever:
            return []

        results = self.retriever.query(objective.objective, n_results=5)
        return [
            f"(第{r['chapter_id']}章) {r['summary']}"
            for r in results
        ]

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
        # Add to semantic index
        if self.retriever:
            self.retriever.add_chapter(
                chapter_id=summary.chapter_id,
                summary=summary.one_line_summary,
            )

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
        """Compress old chapter summaries into long-term memory using LLM."""
        start = max(1, up_to_chapter - self.compression_interval + 1)
        end = up_to_chapter

        rows = self.db.conn.execute(
            """SELECT chapter_id, one_line_summary, plot_events, unresolved_threads
               FROM chapter_summaries
               WHERE chapter_id BETWEEN ? AND ?
               ORDER BY chapter_id""",
            (start, end),
        ).fetchall()

        if not rows:
            return

        # Build input for LLM compression
        summaries = []
        critical_events = []
        for row in rows:
            summaries.append(f"第{row['chapter_id']}章：{row['one_line_summary']}")
            # Collect unresolved threads as critical (never compress these)
            threads = json.loads(row["unresolved_threads"]) if row["unresolved_threads"] else []
            critical_events.extend(threads)

        summaries_text = "\n".join(summaries)

        # Use LLM to compress into a coherent paragraph
        try:
            compressed = self.llm.chat(
                messages=[
                    {"role": "system", "content": (
                        "你是故事記憶壓縮器。請將以下多章摘要壓縮為一段連貫的敘述（100-200字），"
                        "保留關鍵情節轉折和角色發展，省略細節。直接輸出壓縮後的文字。"
                    )},
                    {"role": "user", "content": f"請壓縮第{start}-{end}章的摘要：\n\n{summaries_text}"},
                ],
                model=self.llm.total_usage[-1].model if self.llm.total_usage else "bedrock:us.anthropic.claude-haiku-4-5-20251001-v1:0",
                temperature=0.3,
                max_tokens=500,
            )
        except Exception as e:
            logger.warning("LLM compression failed, using fallback: %s", e)
            compressed = " → ".join(row["one_line_summary"] for row in rows)

        self.db.conn.execute(
            """INSERT INTO compressed_memories (chapter_range, compressed_summary, critical_events)
               VALUES (?, ?, ?)""",
            (f"{start}-{end}", compressed, json.dumps(critical_events, ensure_ascii=False)),
        )
        self.db.conn.commit()
        logger.info("Compressed memories for chapters %d-%d (%d chars)", start, end, len(compressed))

    def get_last_chapter_id(self) -> int:
        """Get the ID of the last completed chapter."""
        row = self.db.conn.execute(
            "SELECT MAX(chapter_id) FROM chapter_summaries"
        ).fetchone()
        return row[0] if row[0] is not None else 0
