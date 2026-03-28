"""Central configuration management using Pydantic Settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class LLMConfig(BaseSettings):
    """LLM provider configuration."""
    # Model assignments per agent role
    planning_model: str = "gpt-4-turbo"
    generation_model: str = "claude-sonnet-4-20250514"
    judge_model: str = "gpt-4-turbo"
    rewrite_model: str = "claude-sonnet-4-20250514"
    summary_model: str = "gpt-3.5-turbo"
    consistency_model: str = "gpt-3.5-turbo"

    # API keys (loaded from env)
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    model_config = {"env_prefix": ""}


class MemoryConfig(BaseSettings):
    """Memory management configuration."""
    short_term_window: int = 5  # chapters to keep in short-term memory
    compression_interval: int = 10  # compress every N chapters
    max_character_memories: int = 10  # per character

    # Token budget for context assembly
    context_token_budget: int = 6000
    short_term_budget: int = 2000
    long_term_budget: int = 1000
    character_budget: int = 1000
    world_budget: int = 500
    instruction_budget: int = 1500


class GenerationConfig(BaseSettings):
    """Chapter generation configuration."""
    batch_size: int = 10
    max_rewrite_attempts: int = 2
    judge_pass_threshold: float = 7.0
    target_words_per_chapter: int = 3000


class NovelConfig(BaseSettings):
    """Top-level configuration for the novel writing system."""
    # Novel metadata
    title: str = "未命名小說"
    author: str = "AI 小說家"
    genre: str = "奇幻冒險"

    # Sub-configs
    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)

    # Paths
    project_root: Path = Field(default_factory=lambda: Path.cwd())

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "novel.db"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def planning_dir(self) -> Path:
        return self.data_dir / "planning"

    @property
    def world_dir(self) -> Path:
        return self.data_dir / "world"

    def ensure_dirs(self) -> None:
        """Create all required directories."""
        for d in [self.data_dir, self.outputs_dir, self.planning_dir,
                  self.world_dir, self.chroma_dir]:
            d.mkdir(parents=True, exist_ok=True)
