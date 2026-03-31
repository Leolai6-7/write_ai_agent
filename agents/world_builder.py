"""World builder agent - expands base world setting into a complete world bible."""

from __future__ import annotations

import yaml

from config.models import WorldBible
from agents.base_agent import BaseAgent


class WorldBuilderAgent(BaseAgent):
    """Expands basic world YAML into a comprehensive world bible."""

    def run(
        self,
        world_setting: dict,
        main_goal: str,
        genre: str = "奇幻冒險",
    ) -> WorldBible:
        """Expand world setting into a full world bible.

        Args:
            world_setting: Parsed world_setting.yaml dict.
            main_goal: Story main goal string.
            genre: Novel genre.

        Returns:
            WorldBible with locations, history, factions, magic rules, culture.
        """
        world_yaml = yaml.dump(world_setting, allow_unicode=True, default_flow_style=False)

        messages = self.prompt.render(
            world_setting=world_yaml,
            main_goal=main_goal,
            genre=genre,
        )

        result = self.call_llm(
            messages, response_model=WorldBible,
            temperature=0.8, max_tokens=4000,
        )
        self.logger.info(
            "World bible created: %d locations, %d history events, %d factions",
            len(result.locations), len(result.history_events), len(result.factions),
        )
        return result
