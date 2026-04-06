"""Memory manager: assembles context from four memory layers with token budget control.

All database operations are delegated to repository classes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from config.models import ChapterContext, ChapterObjective, ChapterSummary
from infrastructure.logger import get_logger
from memory.repositories import SummaryRepository, CharacterRepository, ThreadRepository, CompressedRepository
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
        summary_repo: SummaryRepository,
        character_repo: CharacterRepository,
        thread_repo: ThreadRepository,
        compressed_repo: CompressedRepository,
        llm: LLMClient,
        short_term_window: int = 5,
        compression_interval: int = 10,
        token_budget: TokenBudget | None = None,
        retriever: SemanticRetriever | None = None,
        world_state: WorldState | None = None,
    ):
        self.summaries = summary_repo
        self.characters = character_repo
        self.threads = thread_repo
        self.compressed = compressed_repo
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
        short_term_text = self.budget.truncate_text(short_term, "short_term", self.llm.count_tokens)
        long_term_text = self.budget.truncate_text(long_term, "long_term", self.llm.count_tokens)
        character_text = self.budget.truncate_text(character_ctx, "character", self.llm.count_tokens)
        world_text = self.budget.truncate_text(world_ctx, "world", self.llm.count_tokens)

        relevant = self._get_relevant_memories(objective)

        context = ChapterContext(
            short_term_memory=short_term_text,
            long_term_memory=long_term_text,
            character_context=character_text,
            world_context=world_text,
            relevant_memories=relevant,
            total_tokens=self.budget.total_used(),
        )

        logger.info("Context assembled: %d tokens used (budget: %d)", context.total_tokens, self.budget.total)
        return context

    def _get_short_term_memory(self, current_chapter: int) -> str:
        rows = self.summaries.get_recent(current_chapter, self.short_term_window)
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
        rows = self.compressed.get_all()
        if not rows:
            return ""

        parts = ["## 故事回顧\n"]
        for row in rows:
            parts.append(f"[第{row['chapter_range']}章] {row['compressed_summary']}")

        threads = self.threads.get_unresolved()
        if threads:
            parts.append("\n## 未解決伏筆")
            for t in threads:
                parts.append(f"- (第{t['introduced_chapter']}章起) {t['description']}")

        return "\n".join(parts)

    def _get_character_context(self, characters: list[str]) -> str:
        states = self.characters.get_many(characters)
        if not states:
            return ""

        parts = ["## 角色狀態\n"]
        for s in states:
            rel_str = "、".join(f"{k}({v})" for k, v in s.relationships.items()) if s.relationships else "無"
            mem_str = "；".join(s.key_memories[-3:]) if s.key_memories else "無"
            parts.append(
                f"【{s.name}】位置: {s.current_location} | "
                f"情緒: {s.emotional_state} | 關係: {rel_str}\n"
                f"  近期記憶: {mem_str}"
            )
        return "\n".join(parts)

    def _get_world_context(self, characters: list[str] | None = None) -> str:
        if not self.world_state:
            return ""
        return self.world_state.get_context(characters_involved=characters)

    def _get_relevant_memories(self, objective: ChapterObjective) -> list[str]:
        if not self.retriever:
            return []
        results = self.retriever.query(
            objective.objective, n_results=5, max_distance=0.5,
            filter_characters=objective.characters_involved or None,
            exclude_chapters=[objective.chapter_id],
        )
        return [f"(第{r['chapter_id']}章, 相關度:{1-r['distance']:.0%}) {r['summary']}" for r in results]

    # ── Memory Updates ───────────────────────────────────────────

    def save_summary(self, summary: ChapterSummary, full_text_path: str = "") -> None:
        """Save chapter summary and update related stores."""
        self.summaries.save(summary, full_text_path)

        # Add to semantic index
        if self.retriever:
            self.retriever.add_chapter(
                chapter_id=summary.chapter_id,
                summary=summary.one_line_summary,
                characters=list(summary.character_changes.keys()) if summary.character_changes else [],
            )

        # Track unresolved threads
        for thread in summary.unresolved_threads:
            self.threads.add(thread, summary.chapter_id)

        # Check if compression is needed
        count = self.summaries.count()
        if count > 0 and count % self.compression_interval == 0:
            self._compress_memories(count)

        logger.info("Saved summary for chapter %d", summary.chapter_id)

    def update_character(self, name: str, change_desc: str, chapter_id: int) -> None:
        """Update character state with a new memory from a chapter."""
        self.characters.update_with_memory(name, change_desc, chapter_id)

    def get_last_chapter_id(self) -> int:
        return self.summaries.max_id()

    def get_previous_summary(self, chapter_id: int) -> str:
        return self.summaries.get_previous_summary(chapter_id)

    def _compress_memories(self, up_to_chapter: int) -> None:
        """Compress old chapter summaries into long-term memory using LLM."""
        start = max(1, up_to_chapter - self.compression_interval + 1)
        end = up_to_chapter

        rows = self.summaries.get_range(start, end)
        if not rows:
            return

        summaries = [f"第{r['chapter_id']}章：{r['one_line_summary']}" for r in rows]
        summaries_text = "\n".join(summaries)

        # Collect critical events (unresolved threads)
        critical_events = []
        for row in rows:
            threads = json.loads(row.get("unresolved_threads", "[]"))
            critical_events.extend(threads)

        try:
            compressed = self.llm.chat(
                messages=[
                    {"role": "system", "content": (
                        "你是故事記憶壓縮器。請將以下多章摘要壓縮為一段連貫的敘述（100-200字），"
                        "保留關鍵情節轉折和角色發展，省略細節。直接輸出壓縮後的文字。"
                    )},
                    {"role": "user", "content": f"請壓縮第{start}-{end}章的摘要：\n\n{summaries_text}"},
                ],
                temperature=0.3, max_tokens=500,
            )
        except Exception as e:
            logger.warning("LLM compression failed, using fallback: %s", e)
            compressed = " → ".join(r["one_line_summary"] for r in rows)

        self.compressed.save(f"{start}-{end}", compressed, critical_events)
        logger.info("Compressed memories for chapters %d-%d", start, end)
