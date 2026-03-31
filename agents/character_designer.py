"""Character designer agent - creates a full cast of characters."""

from __future__ import annotations

import yaml

from config.models import CharacterCast, WorldBible, VolumeStructure
from agents.base_agent import BaseAgent


class CharacterDesignerAgent(BaseAgent):
    """Designs supporting characters based on story needs."""

    def run(
        self,
        protagonist: dict,
        world_bible: WorldBible,
        volume_structure: VolumeStructure,
        main_goal: str,
    ) -> CharacterCast:
        """Design a complete character cast.

        Args:
            protagonist: Parsed main_character.yaml dict.
            world_bible: Expanded world bible.
            volume_structure: Volume/arc structure.
            main_goal: Story main goal.

        Returns:
            CharacterCast with profiles and relationship map.
        """
        protagonist_yaml = yaml.dump(protagonist, allow_unicode=True, default_flow_style=False)

        # Summarize world for context
        world_summary = self._summarize_world(world_bible)

        # Summarize volumes
        vol_summary = "\n".join(
            f"- {v.name}：{v.theme}"
            for v in volume_structure.volumes
        )

        messages = self.prompt.render(
            protagonist=protagonist_yaml,
            world_summary=world_summary,
            volume_structure=vol_summary,
            main_goal=main_goal,
        )

        result = self.call_llm(
            messages, response_model=CharacterCast,
            temperature=0.8, max_tokens=4000,
        )
        self.logger.info(
            "Character cast designed: %d characters", len(result.characters),
        )
        return result

    def _summarize_world(self, bible: WorldBible) -> str:
        parts = []
        if bible.locations:
            parts.append("地點：" + "、".join(loc.name for loc in bible.locations))
        if bible.factions:
            parts.append("勢力：" + "、".join(f.name for f in bible.factions))
        if bible.magic_rules:
            parts.append("魔法規則：" + "；".join(bible.magic_rules[:3]))
        return "\n".join(parts)
