"""Judge agent - evaluates chapter quality using LLM-as-Judge pattern."""

from __future__ import annotations

from config.models import ChapterObjective, JudgementResult
from agents.base_agent import BaseAgent


class JudgeAgent(BaseAgent):
    """Evaluates chapter quality across 6 dimensions.

    Uses a different model than the generator to avoid self-evaluation bias.
    """

    def run(
        self,
        chapter_text: str,
        objective: ChapterObjective,
        previous_summary: str = "",
    ) -> JudgementResult:
        """Evaluate chapter quality.

        Returns:
            JudgementResult with scores and feedback.
        """
        system_prompt = (
            "你是一位資深的小說編輯和品質審查員。請根據以下六個維度對章節進行評分（0-10分），\n"
            "並提供具體的問題和改寫建議。\n\n"
            "## 評分維度\n"
            "1. **plot_progression**（情節推進）：章節是否有效推動故事發展\n"
            "2. **character_consistency**（角色一致性）：角色行為是否符合其設定和前文表現\n"
            "3. **writing_quality**（文筆品質）：描寫是否生動、對話是否自然\n"
            "4. **pacing**（節奏感）：敘事節奏是否恰當，不過快或拖沓\n"
            "5. **objective_alignment**（目標吻合度）：是否完成了章節目標中的關鍵事件\n"
            "6. **overall_score**（綜合分數）：整體品質評分\n\n"
            "## 評分標準\n"
            "- 9-10: 出色，幾乎無需修改\n"
            "- 7-8: 良好，小問題不影響閱讀\n"
            "- 5-6: 一般，需要改進\n"
            "- 3-4: 較差，需要大幅改寫\n"
            "- 1-2: 很差，需要完全重寫\n\n"
            "pass_threshold 設為 true 當 overall_score >= 7.0\n\n"
            "請以 JSON 格式回應。"
        )

        user_prompt = self._build_user_prompt(chapter_text, objective, previous_summary)

        result = self.call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=JudgementResult,
            temperature=0.3,  # Low temperature for consistent scoring
            max_tokens=2000,
        )
        self.logger.info(
            "Chapter %d score: %.1f (pass: %s)",
            objective.chapter_id, result.overall_score, result.pass_threshold,
        )
        return result

    def _build_user_prompt(
        self,
        chapter_text: str,
        objective: ChapterObjective,
        previous_summary: str,
    ) -> str:
        events = "、".join(objective.key_events)
        parts = [
            f"## 章節目標\n",
            f"- 標題：第{objective.chapter_id}章：{objective.title}",
            f"- 目標：{objective.objective}",
            f"- 關鍵事件：{events}",
            f"- 情感基調：{objective.emotional_tone}",
        ]

        if previous_summary:
            parts.append(f"\n## 前章摘要\n{previous_summary}")

        parts.append(f"\n## 待評審章節內容\n\n{chapter_text}")

        return "\n".join(parts)
