"""Prompt template system for agent prompts.

Loads prompts from YAML files, supports variable substitution and versioning.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from infrastructure.logger import get_logger

logger = get_logger("prompts")

PROMPTS_DIR = Path(__file__).parent


class PromptTemplate:
    """A prompt template with system and user parts, supporting variable substitution."""

    def __init__(self, system: str, user: str, version: str = "1.0"):
        self.system = system
        self.user = user
        self.version = version

    def render(self, **kwargs) -> list[dict[str, str]]:
        """Render the template with variables, returning messages list.

        Missing variables are left as-is (no KeyError).
        """
        system = self._safe_format(self.system, **kwargs)
        user = self._safe_format(self.user, **kwargs)

        messages = []
        if system.strip():
            messages.append({"role": "system", "content": system})
        if user.strip():
            messages.append({"role": "user", "content": user})
        return messages

    @staticmethod
    def _safe_format(template: str, **kwargs) -> str:
        """Format template, leaving unknown {variables} untouched."""
        for key, value in kwargs.items():
            template = template.replace(f"{{{key}}}", str(value))
        return template


class PromptLoader:
    """Loads prompt templates from YAML files."""

    def __init__(self, prompts_dir: Path | None = None):
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self._cache: dict[str, PromptTemplate] = {}

    def load(self, name: str) -> PromptTemplate:
        """Load a prompt template by agent name.

        Args:
            name: Agent name (e.g., "chapter_generator", "judge").
                  Corresponds to prompts/{name}.yaml

        Returns:
            PromptTemplate instance.
        """
        if name in self._cache:
            return self._cache[name]

        path = self.prompts_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        template = PromptTemplate(
            system=data.get("system", ""),
            user=data.get("user", ""),
            version=data.get("version", "1.0"),
        )
        self._cache[name] = template
        logger.debug("Loaded prompt: %s (v%s)", name, template.version)
        return template

    def load_all(self) -> dict[str, PromptTemplate]:
        """Load all prompt templates from the directory."""
        templates = {}
        for path in self.prompts_dir.glob("*.yaml"):
            name = path.stem
            templates[name] = self.load(name)
        return templates
