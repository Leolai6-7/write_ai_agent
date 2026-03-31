"""Foreshadowing manager - plans and tracks foreshadowing lifecycle."""

from __future__ import annotations

from config.models import VolumeSpec, ArcSpec, ForeshadowPlan, ChapterForeshadowDirective
from agents.base_agent import BaseAgent
from memory.repositories.foreshadow_repo import ForeshadowRepository


class ForeshadowingManager(BaseAgent):
    """Plans foreshadowing across arcs and provides per-chapter directives."""

    def __init__(self, *args, foreshadow_repo: ForeshadowRepository | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.repo = foreshadow_repo

    def plan(
        self,
        volume: VolumeSpec,
        arcs: list[ArcSpec],
        existing_threads: list[str] | None = None,
    ) -> ForeshadowPlan:
        """Create foreshadowing plan for a volume's arcs."""
        volume_info = f"卷名：{volume.name}\n主題：{volume.theme}\n範圍：第{volume.start_chapter}-{volume.end_chapter}章"

        arcs_info = "\n".join(
            f"- {a.arc_name}（第{a.start_chapter}-{a.end_chapter}章）：{a.core_objective}"
            for a in arcs
        )

        threads = "\n".join(f"- {t}" for t in (existing_threads or [])) or "無"

        messages = self.prompt.render(
            volume_info=volume_info,
            arcs_info=arcs_info,
            existing_threads=threads,
        )

        plan = self.call_llm(
            messages, response_model=ForeshadowPlan,
            temperature=0.7, max_tokens=3000,
        )

        # Save to DB
        if self.repo:
            self.repo.save_plan(plan.foreshadows)

        self.logger.info("Foreshadow plan: %d threads created", len(plan.foreshadows))
        return plan

    def get_directive(self, chapter_id: int) -> ChapterForeshadowDirective:
        """Get foreshadowing instructions for a specific chapter."""
        if not self.repo:
            return ChapterForeshadowDirective()
        return self.repo.get_directive(chapter_id)
