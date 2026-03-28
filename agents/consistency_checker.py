"""Consistency checker agent - detects contradictions across chapters."""

from __future__ import annotations

from config.models import ConsistencyReport
from agents.base_agent import BaseAgent


class ConsistencyChecker(BaseAgent):
    """Checks new chapter content against historical memory for contradictions.

    Checks: character consistency, timeline, settings, item tracking.
    """

    def run(
        self,
        chapter_text: str,
        chapter_id: int,
        character_context: str = "",
        relevant_history: str = "",
    ) -> ConsistencyReport:
        """Check chapter for consistency issues.

        Returns:
            ConsistencyReport with contradictions and warnings.
        """
        system_prompt = (
            "你是一位小說校對員，專門檢查故事一致性。請檢查新章節內容是否與已有故事存在矛盾。\n\n"
            "## 檢查維度\n"
            "1. **character**（角色一致性）：性格、說話風格、能力是否與前文矛盾\n"
            "2. **timeline**（時間線）：事件順序是否合理，有無時間跳躍錯誤\n"
            "3. **setting**（設定）：魔法規則、地理位置等是否矛盾\n"
            "4. **item**（物品追蹤）：重要物品的位置和狀態是否正確\n\n"
            "## 回應格式\n"
            "- is_consistent: 是否一致（true/false）\n"
            "- contradictions: 矛盾列表（每項含 type, description, source_chapter, conflicting_text, suggested_fix）\n"
            "- warnings: 不確定但值得注意的問題（字串陣列）\n\n"
            "如果沒有發現矛盾，is_consistent 設為 true，contradictions 為空陣列。\n"
            "請以 JSON 格式回應。"
        )

        parts = [f"## 新章節（第{chapter_id}章）\n\n{chapter_text}"]

        if character_context:
            parts.append(f"\n## 角色狀態（截至上一章）\n{character_context}")

        if relevant_history:
            parts.append(f"\n## 相關歷史章節摘要\n{relevant_history}")

        user_prompt = "\n".join(parts)

        result = self.call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=ConsistencyReport,
            temperature=0.3,
            max_tokens=2000,
        )

        if result.contradictions:
            self.logger.warning(
                "Chapter %d: found %d contradictions", chapter_id, len(result.contradictions)
            )
        else:
            self.logger.info("Chapter %d: consistent", chapter_id)

        return result
