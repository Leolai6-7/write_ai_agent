"""Chapter planner agent - generates per-chapter objectives for an arc."""

from __future__ import annotations

from pydantic import BaseModel, Field

from config.models import ArcSpec, ChapterObjective
from agents.base_agent import BaseAgent


class ChapterPlanResult(BaseModel):
    """Wrapper for chapter planning output."""
    chapters: list[ChapterObjective] = Field(min_length=1)


class ChapterPlannerAgent(BaseAgent):
    """Plans detailed chapter objectives within an arc."""

    def run(
        self,
        arc: ArcSpec,
        memory_context: str = "",
    ) -> list[ChapterObjective]:
        """Generate per-chapter objectives for an arc.

        Returns:
            List of ChapterObjective.
        """
        total_chapters = arc.end_chapter - arc.start_chapter + 1

        system_prompt = (
            "你是一位章節規劃師。請為故事弧線生成每章的詳細目標。\n\n"
            "每章需要：\n"
            "- 簡短標題\n"
            "- 明確的章節目標\n"
            "- 2-3個關鍵事件\n"
            "- 出場角色列表\n"
            "- 情感基調（如：緊張、溫馨、悲壯、輕鬆）\n\n"
            "注意事項：\n"
            "- 章節間要有連貫性\n"
            "- 節奏要有起伏，不要每章都高潮\n"
            "- 弧線結尾的章節要收束該弧線的衝突\n\n"
            "請以 JSON 格式回應，包含 chapters 陣列。"
        )

        user_prompt = (
            f"## 弧線資訊\n\n"
            f"**弧線名稱**：{arc.arc_name}\n"
            f"**章節範圍**：第{arc.start_chapter}章 - 第{arc.end_chapter}章（共{total_chapters}章）\n"
            f"**核心目標**：{arc.core_objective}\n"
            f"**主要衝突**：{arc.main_conflict}\n"
            f"**結尾轉折**：{arc.ending_twist}\n"
            f"**關鍵角色**：{'、'.join(arc.key_characters)}\n"
        )

        if memory_context:
            user_prompt += f"\n## 故事上下文\n{memory_context}\n"

        result = self.call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=ChapterPlanResult,
            temperature=0.7,
            max_tokens=4000,
        )

        self.logger.info(
            "Planned %d chapters for arc: %s", len(result.chapters), arc.arc_name
        )
        return result.chapters
