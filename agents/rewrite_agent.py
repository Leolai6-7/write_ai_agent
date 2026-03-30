"""Rewrite agent - rewrites chapters based on structured feedback."""

from __future__ import annotations

from config.models import JudgementResult, ConsistencyReport
from agents.base_agent import BaseAgent


class RewriteAgent(BaseAgent):
    """Rewrites chapter content based on specific issues and suggestions."""

    def run(
        self,
        chapter_text: str,
        judgement: JudgementResult | None = None,
        consistency: ConsistencyReport | None = None,
    ) -> str:
        """Rewrite chapter based on feedback."""
        feedback_parts = []

        if judgement:
            feedback_parts.append("## 品質問題\n")
            for issue in judgement.issues:
                feedback_parts.append(f"- {issue}")
            feedback_parts.append("\n## 改寫建議\n")
            for suggestion in judgement.rewrite_suggestions:
                feedback_parts.append(f"- {suggestion}")
            feedback_parts.append(
                f"\n## 各項評分\n"
                f"- 情節推進: {judgement.plot_progression}/10\n"
                f"- 角色一致性: {judgement.character_consistency}/10\n"
                f"- 文筆品質: {judgement.writing_quality}/10\n"
                f"- 節奏感: {judgement.pacing}/10\n"
                f"- 目標吻合度: {judgement.objective_alignment}/10"
            )

        if consistency and not consistency.is_consistent:
            feedback_parts.append("\n## 一致性矛盾\n")
            for c in consistency.contradictions:
                feedback_parts.append(
                    f"- [{c.type}] {c.description}\n"
                    f"  衝突出處: 第{c.source_chapter}章\n"
                    f"  建議修正: {c.suggested_fix}"
                )

        feedback_block = "\n".join(feedback_parts)
        messages = self.prompt.render(
            feedback_block=feedback_block,
            chapter_text=chapter_text,
        )
        return self.call_llm(messages, temperature=0.7, max_tokens=6000)
