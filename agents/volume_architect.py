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
        """Design novel volume structure."""
        messages = self.prompt.render(
            main_goal=main_goal,
            genre=genre,
            target_volumes=target_volumes,
            chapters_per_volume=chapters_per_volume,
        )
        result = self.call_llm(messages, response_model=VolumeStructure, temperature=0.7, max_tokens=3000)
        self.logger.info("Designed %d-volume structure: %s", len(result.volumes), result.title)
        return result
