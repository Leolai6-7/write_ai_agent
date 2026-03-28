"""Chapter generation agent - produces novel chapter drafts."""

from __future__ import annotations

from config.models import ChapterObjective, ChapterContext
from agents.base_agent import BaseAgent


class ChapterGeneratorAgent(BaseAgent):
    """Generates a chapter draft based on objective and memory context."""

    def run(
        self,
        objective: ChapterObjective,
        context: ChapterContext,
    ) -> str:
        """Generate a chapter draft.

        Returns:
            Chapter text (3000-5000 Chinese characters).
        """
        system_prompt = self._build_system_prompt(context)
        user_prompt = self._build_user_prompt(objective)

        result = self.call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=6000,
        )
        return result

    def _build_system_prompt(self, context: ChapterContext) -> str:
        parts = [
            "你是一位專業的中文網路小說作家。請根據提供的章節目標和上下文，撰寫一個精彩的章節。",
            "要求：",
            "- 字數目標：3000-5000字",
            "- 包含生動的環境描寫、角色對話和內心戲",
            "- 保持與前文的連貫性",
            "- 章節結尾留下懸念或推動下一章的動力",
            "- 直接輸出章節正文，不要加任何格式標記或說明",
        ]

        if context.short_term_memory:
            parts.append(f"\n{context.short_term_memory}")
        if context.long_term_memory:
            parts.append(f"\n{context.long_term_memory}")
        if context.character_context:
            parts.append(f"\n{context.character_context}")
        if context.world_context:
            parts.append(f"\n{context.world_context}")

        return "\n".join(parts)

    def _build_user_prompt(self, objective: ChapterObjective) -> str:
        events = "、".join(objective.key_events) if objective.key_events else "無特定事件"
        characters = "、".join(objective.characters_involved) if objective.characters_involved else "無"

        return (
            f"## 第{objective.chapter_id}章：{objective.title}\n\n"
            f"**章節目標**：{objective.objective}\n"
            f"**關鍵事件**：{events}\n"
            f"**出場角色**：{characters}\n"
            f"**情感基調**：{objective.emotional_tone}\n\n"
            f"請開始撰寫本章內容。"
        )
