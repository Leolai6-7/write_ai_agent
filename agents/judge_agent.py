"""Judge agent - evaluates chapter quality using LLM-as-Judge pattern.

Supports self-consistency voting and pairwise comparison.
"""

from __future__ import annotations

from config.models import ChapterObjective, JudgementResult
from agents.base_agent import BaseAgent


class JudgeAgent(BaseAgent):
    """Evaluates chapter quality across 6 dimensions."""

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
        """Compare two drafts via pairwise comparison. Returns the better draft."""
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
            temperature=0.3, max_tokens=10,
        )
        choice = result.strip().upper()
        if "A" in choice:
            self.logger.info("Pairwise comparison: draft A selected")
            return draft_a
        self.logger.info("Pairwise comparison: draft B selected")
        return draft_b

    def _single_judge(self, chapter_text, objective, previous_summary):
        events = "、".join(objective.key_events)
        prev_block = f"\n## 前章摘要\n{previous_summary}" if previous_summary else ""

        messages = self.prompt.render(
            chapter_id=objective.chapter_id,
            title=objective.title,
            objective=objective.objective,
            key_events=events,
            emotional_tone=objective.emotional_tone,
            previous_summary_block=prev_block,
            chapter_text=chapter_text,
        )

        result = self.call_llm(messages, response_model=JudgementResult, temperature=0.3, max_tokens=2000)
        self.logger.info("Chapter %d score: %.1f (pass: %s)", objective.chapter_id, result.overall_score, result.pass_threshold)
        return result

    def _voted_judge(self, chapter_text, objective, previous_summary):
        """Run judge N times and average the scores."""
        results: list[JudgementResult] = []
        for i in range(self.voting_rounds):
            try:
                results.append(self._single_judge(chapter_text, objective, previous_summary))
            except Exception as e:
                self.logger.warning("Voting round %d failed: %s", i + 1, e)

        if not results:
            raise RuntimeError("All voting rounds failed")

        n = len(results)
        avg = JudgementResult(
            overall_score=round(sum(r.overall_score for r in results) / n, 1),
            plot_progression=round(sum(r.plot_progression for r in results) / n, 1),
            character_consistency=round(sum(r.character_consistency for r in results) / n, 1),
            writing_quality=round(sum(r.writing_quality for r in results) / n, 1),
            pacing=round(sum(r.pacing for r in results) / n, 1),
            objective_alignment=round(sum(r.objective_alignment for r in results) / n, 1),
            pass_threshold=sum(1 for r in results if r.pass_threshold) > n / 2,
            issues=list({issue for r in results for issue in r.issues}),
            rewrite_suggestions=list({s for r in results for s in r.rewrite_suggestions}),
        )
        self.logger.info("Voted judge (%d rounds): %.1f (pass: %s)", n, avg.overall_score, avg.pass_threshold)
        return avg
