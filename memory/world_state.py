"""World state manager - loads and serves world-building context from YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from infrastructure.logger import get_logger

logger = get_logger("world_state")


class WorldState:
    """Loads world-building YAML files and provides context for chapter generation.

    Files expected:
        - world_setting.yaml: geography, magic system, races
        - main_character.yaml: protagonist profile
        - main_goal.yaml: story main goal
    """

    def __init__(self, world_dir: Path):
        self.world_dir = world_dir
        self._world: dict = {}
        self._character: dict = {}
        self._goal: str = ""
        self._loaded = False

    def load(self) -> None:
        """Load all YAML files from world directory."""
        self._world = self._load_yaml("world_setting.yaml")
        self._character = self._load_yaml("main_character.yaml")

        goal_data = self._load_yaml("main_goal.yaml")
        self._goal = goal_data.get("main_goal", "") if isinstance(goal_data, dict) else str(goal_data)

        self._loaded = True
        logger.info(
            "World loaded: %d world keys, character=%s, goal=%d chars",
            len(self._world), self._character.get("name", "?"), len(self._goal),
        )

    def _load_yaml(self, filename: str) -> dict:
        path = self.world_dir / filename
        if not path.exists():
            logger.warning("World file not found: %s", path)
            return {}
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get_context(self, characters_involved: list[str] | None = None) -> str:
        """Build world context string, optionally filtered by relevant characters."""
        if not self._loaded:
            self.load()

        parts = []

        # Story goal
        if self._goal:
            parts.append(f"## 故事主線\n{self._goal}")

        # World setting
        if self._world:
            parts.append(self._format_world())

        # Main character (always include if involved)
        if self._character:
            char_name = self._character.get("name", "")
            if not characters_involved or char_name in characters_involved or not char_name:
                parts.append(self._format_character())

        return "\n\n".join(parts)

    def _format_world(self) -> str:
        lines = ["## 世界設定"]

        if "continent" in self._world:
            lines.append(f"大陸：{self._world['continent']}")
        if "eras" in self._world:
            lines.append(f"時代：{self._world['eras']}")
        if "geography" in self._world:
            places = "、".join(self._world["geography"])
            lines.append(f"主要地點：{places}")

        magic = self._world.get("magic_system", {})
        if magic:
            lines.append(f"\n### 魔法體系")
            if "source" in magic:
                lines.append(f"來源：{magic['source']}")
            for rule in magic.get("rules", []):
                lines.append(f"- {rule}")

        if "races" in self._world:
            races = "、".join(self._world["races"])
            lines.append(f"\n種族：{races}")

        return "\n".join(lines)

    def _format_character(self) -> str:
        c = self._character
        lines = [f"## 主角：{c.get('name', '未知')}"]

        for key, label in [
            ("race", "種族"), ("age", "年齡"), ("gender", "性別"),
            ("occupation", "職業"), ("speaking_style", "說話風格"),
        ]:
            if key in c:
                lines.append(f"{label}：{c[key]}")

        if "personality" in c:
            lines.append(f"性格：{'、'.join(c['personality'])}")
        if "skills" in c:
            lines.append(f"技能：{'、'.join(c['skills'])}")
        if "weaknesses" in c:
            lines.append(f"弱點：{'、'.join(c['weaknesses'])}")
        if "goals" in c:
            lines.append("目標：")
            for g in c["goals"]:
                lines.append(f"  - {g}")
        if "background" in c:
            lines.append(f"背景：{c['background']}")

        return "\n".join(lines)
