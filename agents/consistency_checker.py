"""Consistency checker agent - detects contradictions across chapters."""

from __future__ import annotations

from config.models import ConsistencyReport
from agents.base_agent import BaseAgent


class ConsistencyChecker(BaseAgent):
    """Checks new chapter content against historical memory for contradictions."""

    def run(
        self,
        chapter_text: str,
        chapter_id: int,
        character_context: str = "",
        relevant_history: str = "",
    ) -> ConsistencyReport:
        """Check chapter for consistency issues."""
        history_parts = []
        if character_context:
            history_parts.append(f"\n## 角色狀態（截至上一章）\n{character_context}")
        if relevant_history:
            history_parts.append(f"\n## 相關歷史章節摘要\n{relevant_history}")
        history_block = "\n".join(history_parts)

        messages = self.prompt.render(
            chapter_id=chapter_id,
            chapter_text=chapter_text,
            history_block=history_block,
        )

        result = self.call_llm(messages, response_model=ConsistencyReport, temperature=0.3, max_tokens=2000)

        if result.contradictions:
            self.logger.warning("Chapter %d: found %d contradictions", chapter_id, len(result.contradictions))
        else:
            self.logger.info("Chapter %d: consistent", chapter_id)
        return result
