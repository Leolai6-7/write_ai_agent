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
            "你是一位頂尖的中文網路小說作家，擅長寫出讓讀者欲罷不能的章節。",
            "",
            "## 寫作風格要求",
            "- 字數目標：3000-5000字",
            "- 長短句交替使用，營造節奏感（短句加速緊張、長句鋪陳氛圍）",
            "- 適度使用成語和四字詞（每段1-2個，不要堆砌）",
            "- 對話要符合角色性格，避免所有人說話方式相同",
            "- 內心獨白用近距離敘事，讓讀者感受角色情緒",
            "",
            "## 網文結構要求",
            "- 開頭：用動作或對話切入，不要大段描寫（黃金三行法則）",
            "- 中段：製造「爽感節奏」— 挫折→逆轉→小高潮，讓讀者有代入感",
            "- 結尾：必須有斷章（cliffhanger）— 懸念、反轉、或即將到來的危機",
            "- 每個場景要有衝突或張力，避免平淡流水帳",
            "",
            "## 格式",
            "- 直接輸出章節正文，不要加任何標記、標題或說明",
            "- 保持與前文的連貫性",
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
