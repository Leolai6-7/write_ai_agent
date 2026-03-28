"""Volume architect agent - designs overall novel structure."""

from __future__ import annotations

from config.models import VolumeStructure
from agents.base_agent import BaseAgent


class VolumeArchitectAgent(BaseAgent):
    """Designs the multi-volume structure for a novel."""

    def run(
        self,
        main_goal: str,
        genre: str = "奇幻冒險",
        target_volumes: int = 3,
        chapters_per_volume: int = 120,
    ) -> VolumeStructure:
        """Design novel volume structure.

        Returns:
            VolumeStructure with volume specifications.
        """
        system_prompt = (
            "你是一位資深的長篇小說架構師。請為給定的故事主線設計分卷架構。\n\n"
            "要求：\n"
            "- 每卷有明確的主題和核心情節\n"
            "- 卷與卷之間有承接關係\n"
            "- 整體故事節奏由緩到急，最終高潮收尾\n"
            "- 每卷的 core_plot_points 包含 3-5 個核心情節轉折\n"
            "- character_development 描述主角在該卷的成長\n\n"
            "請以 JSON 格式回應。"
        )

        user_prompt = (
            f"## 小說設計需求\n\n"
            f"**故事主線**：{main_goal}\n"
            f"**類型**：{genre}\n"
            f"**目標卷數**：{target_volumes}\n"
            f"**每卷章數**：約{chapters_per_volume}章\n\n"
            f"請設計完整的分卷架構。"
        )

        result = self.call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=VolumeStructure,
            temperature=0.7,
            max_tokens=3000,
        )
        self.logger.info("Designed %d-volume structure: %s", len(result.volumes), result.title)
        return result
