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
        """Split a volume into 3-5 arcs of 20-30 chapters each."""
        existing_block = f"\n## 已有弧線（避免重複）\n{existing_arcs_summary}" if existing_arcs_summary else ""

        messages = self.prompt.render(
            volume_name=volume.name,
            volume_theme=volume.theme,
            start_chapter=volume.start_chapter,
            end_chapter=volume.end_chapter,
            core_plot_points="、".join(volume.core_plot_points),
            existing_arcs_block=existing_block,
        )
        result = self.call_llm(messages, response_model=ArcPlanResult, temperature=0.7, max_tokens=3000)
        self.logger.info("Planned %d arcs for volume: %s", len(result.arcs), volume.name)
        return result.arcs
