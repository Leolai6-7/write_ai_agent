"""Arc planner agent - splits a volume into story arcs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from config.models import VolumeSpec, ArcSpec
from agents.base_agent import BaseAgent


class ArcPlanResult(BaseModel):
    """Wrapper for arc planning output."""
    arcs: list[ArcSpec] = Field(min_length=1)


class ArcPlannerAgent(BaseAgent):
    """Plans story arcs within a volume."""

    def run(
        self,
        volume: VolumeSpec,
        existing_arcs_summary: str = "",
    ) -> list[ArcSpec]:
        """Split a volume into 3-5 arcs of 20-30 chapters each.

        Returns:
            List of ArcSpec.
        """
        system_prompt = (
            "你是一位故事弧線規劃師。請將一卷小說拆分為 3-5 個弧線，每個弧線 20-30 章。\n\n"
            "每個弧線需要：\n"
            "- 明確的核心衝突和目標\n"
            "- 結尾有轉折或懸念連接下一弧線\n"
            "- 列出關鍵出場角色\n\n"
            "請以 JSON 格式回應，包含 arcs 陣列。"
        )

        user_prompt = (
            f"## 卷級資訊\n\n"
            f"**卷名**：{volume.name}\n"
            f"**主題**：{volume.theme}\n"
            f"**章節範圍**：第{volume.start_chapter}章 - 第{volume.end_chapter}章\n"
            f"**核心情節**：{'、'.join(volume.core_plot_points)}\n"
        )

        if existing_arcs_summary:
            user_prompt += f"\n## 已有弧線（避免重複）\n{existing_arcs_summary}\n"

        result = self.call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=ArcPlanResult,
            temperature=0.7,
            max_tokens=3000,
        )

        self.logger.info("Planned %d arcs for volume: %s", len(result.arcs), volume.name)
        return result.arcs
