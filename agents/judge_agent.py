"""Judge agent - evaluates chapter quality using LLM-as-Judge pattern.

Supports self-consistency voting (run N times, average scores) and
pairwise comparison (compare two drafts, pick the better one).
"""

from __future__ import annotations

from config.models import ChapterObjective, JudgementResult
from agents.base_agent import BaseAgent

SYSTEM_PROMPT = (
    "你是一位資深的網路小說編輯，專精中文網文品質審查。\n"
    "請根據以下六個維度對章節進行評分（0-10分），並提供具體的問題和改寫建議。\n\n"
    "## 評分維度\n"
    "1. **plot_progression**（情節推進）：是否有效推動故事，有無「爽點」或情節轉折\n"
    "2. **character_consistency**（角色一致性）：行為和說話風格是否符合設定，有無OOC\n"
    "3. **writing_quality**（文筆品質）：長短句節奏、描寫生動度、對話自然度、成語運用是否恰當\n"
    "4. **pacing**（節奏感）：是否有張弛有度的節奏，有無拖沓或過於倉促\n"
    "5. **objective_alignment**（目標吻合度）：是否完成章節目標中的關鍵事件\n"
    "6. **overall_score**（綜合分數）：作為網文讀者，是否想繼續讀下一章\n\n"
    "## 評分標準\n"
    "- 9-10: 出色，讓人忍不住想翻下一章\n"
    "- 7-8: 良好，閱讀流暢，有吸引力\n"
    "- 5-6: 一般，能讀但缺乏吸引力\n"
    "- 3-4: 較差，多處拖沓或不合理\n"
    "- 1-2: 很差，需要完全重寫\n\n"
    "## 網文特殊檢查\n"
    "- 章節結尾是否有斷章（cliffhanger）？沒有則扣 pacing 1-2 分\n"
    "- 是否有水字數的嫌疑（重複描述、無意義對話）？有則扣 writing_quality\n"
    "- 角色是否都用同一種說話方式？有則扣 character_consistency\n\n"
    "pass_threshold 設為 true 當 overall_score >= 7.0\n\n"
    "請以 JSON 格式回應。"
)


class JudgeAgent(BaseAgent):
    """Evaluates chapter quality across 6 dimensions.

    Features:
        - Self-consistency voting: run N times and average scores
        - Pairwise comparison: compare two drafts and pick the better one
    """

    def __init__(self, *args, voting_rounds: int = 1, **kwargs):
        super().__init__(*args, **kwargs)
        self.voting_rounds = voting_rounds

    def run(
        self,
        chapter_text: str,
        objective: ChapterObjective,
        previous_summary: str = "",
    ) -> JudgementResult:
        """Evaluate chapter quality with optional self-consistency voting."""
        if self.voting_rounds <= 1:
            return self._single_judge(chapter_text, objective, previous_summary)

        return self._voted_judge(chapter_text, objective, previous_summary)

    def compare(
        self,
        draft_a: str,
        draft_b: str,
        objective: ChapterObjective,
    ) -> str:
        """Compare two drafts and return the better one (pairwise comparison).

        Returns:
            The better draft text ("a" or "b").
        """
        prompt = (
            f"你是一位資深網文編輯。以下是同一章節目標的兩個草稿版本。\n"
            f"請選擇品質更高的版本，考慮：情節推進、角色一致性、文筆、節奏、斷章效果。\n\n"
            f"## 章節目標\n{objective.objective}\n\n"
            f"## 草稿 A\n{draft_a}\n\n"
            f"## 草稿 B\n{draft_b}\n\n"
            f"請只回答 A 或 B（一個字母）。"
        )

        result = self.call_llm(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=10,
        )
        choice = result.strip().upper()

        if "A" in choice:
            self.logger.info("Pairwise comparison: draft A selected")
            return draft_a
        else:
            self.logger.info("Pairwise comparison: draft B selected")
            return draft_b

    def _single_judge(
        self, chapter_text: str, objective: ChapterObjective, previous_summary: str,
    ) -> JudgementResult:
        user_prompt = self._build_user_prompt(chapter_text, objective, previous_summary)
        result = self.call_llm(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_model=JudgementResult,
            temperature=0.3,
            max_tokens=2000,
        )
        self.logger.info(
            "Chapter %d score: %.1f (pass: %s)",
            objective.chapter_id, result.overall_score, result.pass_threshold,
        )
        return result

    def _voted_judge(
        self, chapter_text: str, objective: ChapterObjective, previous_summary: str,
    ) -> JudgementResult:
        """Run judge N times and average the scores."""
        results: list[JudgementResult] = []
        for i in range(self.voting_rounds):
            try:
                r = self._single_judge(chapter_text, objective, previous_summary)
                results.append(r)
            except Exception as e:
                self.logger.warning("Voting round %d failed: %s", i + 1, e)

        if not results:
            raise RuntimeError("All voting rounds failed")

        # Average scores
        n = len(results)
        avg = JudgementResult(
            overall_score=round(sum(r.overall_score for r in results) / n, 1),
            plot_progression=round(sum(r.plot_progression for r in results) / n, 1),
            character_consistency=round(sum(r.character_consistency for r in results) / n, 1),
            writing_quality=round(sum(r.writing_quality for r in results) / n, 1),
            pacing=round(sum(r.pacing for r in results) / n, 1),
            objective_alignment=round(sum(r.objective_alignment for r in results) / n, 1),
            pass_threshold=sum(1 for r in results if r.pass_threshold) > n / 2,  # Majority vote
            issues=list({issue for r in results for issue in r.issues}),
            rewrite_suggestions=list({s for r in results for s in r.rewrite_suggestions}),
        )

        self.logger.info(
            "Voted judge (%d rounds): %.1f (pass: %s, scores: %s)",
            n, avg.overall_score, avg.pass_threshold,
            [r.overall_score for r in results],
        )
        return avg

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
