"""Rewrite agent - rewrites chapters based on structured feedback from JudgeAgent."""

from __future__ import annotations

from config.models import JudgementResult, ConsistencyReport
from agents.base_agent import BaseAgent


class RewriteAgent(BaseAgent):
    """Rewrites chapter content based on specific issues and suggestions.

    Unlike the old ExpansionAgent, this agent does NOT judge quality itself.
    It only executes rewrites based on structured instructions.
    """

    def run(
        self,
        chapter_text: str,
        judgement: JudgementResult | None = None,
        consistency: ConsistencyReport | None = None,
    ) -> str:
        """Rewrite chapter based on feedback.

        Args:
            chapter_text: Original chapter text.
            judgement: Quality judgement with issues and suggestions.
            consistency: Consistency report with contradictions.

        Returns:
            Rewritten chapter text.
        """
        system_prompt = (
            "你是一位專業的小說改稿編輯。請根據提供的具體問題和建議，改寫章節內容。\n\n"
            "要求：\n"
            "- 保留原文的核心情節和結構\n"
            "- 針對性地修正指出的問題\n"
            "- 保持或提升字數（3000-5000字）\n"
            "- 直接輸出改寫後的完整章節，不要加說明或標記\n"
        )

        user_prompt = self._build_user_prompt(chapter_text, judgement, consistency)

        result = self.call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=6000,
        )
        return result

    def _build_user_prompt(
        self,
        chapter_text: str,
        judgement: JudgementResult | None,
        consistency: ConsistencyReport | None,
    ) -> str:
        parts = []

        if judgement:
            parts.append("## 品質問題\n")
            for issue in judgement.issues:
                parts.append(f"- {issue}")

            parts.append("\n## 改寫建議\n")
            for suggestion in judgement.rewrite_suggestions:
                parts.append(f"- {suggestion}")

            parts.append(
                f"\n## 各項評分\n"
                f"- 情節推進: {judgement.plot_progression}/10\n"
                f"- 角色一致性: {judgement.character_consistency}/10\n"
                f"- 文筆品質: {judgement.writing_quality}/10\n"
                f"- 節奏感: {judgement.pacing}/10\n"
                f"- 目標吻合度: {judgement.objective_alignment}/10"
            )

        if consistency and not consistency.is_consistent:
            parts.append("\n## 一致性矛盾\n")
            for c in consistency.contradictions:
                parts.append(
                    f"- [{c.type}] {c.description}\n"
                    f"  衝突出處: 第{c.source_chapter}章\n"
                    f"  建議修正: {c.suggested_fix}"
                )

        parts.append(f"\n## 原始章節內容\n\n{chapter_text}")
        parts.append("\n請根據以上問題和建議，輸出改寫後的完整章節。")

        return "\n".join(parts)
