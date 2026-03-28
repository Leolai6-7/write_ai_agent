"""Pydantic models for all structured LLM outputs and data types."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Planning Models ──────────────────────────────────────────────

class VolumeSpec(BaseModel):
    """Specification for a single volume of the novel."""
    name: str
    theme: str
    start_chapter: int
    end_chapter: int
    core_plot_points: list[str]
    character_development: str


class VolumeStructure(BaseModel):
    """Overall novel volume structure."""
    title: str
    genre: str
    total_volumes: int
    volumes: list[VolumeSpec]


class ArcSpec(BaseModel):
    """Specification for a story arc within a volume."""
    arc_name: str
    start_chapter: int
    end_chapter: int
    core_objective: str
    main_conflict: str
    ending_twist: str
    key_characters: list[str]


class ChapterObjective(BaseModel):
    """Objective for a single chapter."""
    chapter_id: int
    title: str
    objective: str
    key_events: list[str]
    characters_involved: list[str]
    emotional_tone: str  # e.g. "緊張", "溫馨", "悲壯"


# ── Judgement Models ─────────────────────────────────────────────

class JudgementResult(BaseModel):
    """Structured quality judgement from JudgeAgent."""
    overall_score: float = Field(ge=0, le=10)
    plot_progression: float = Field(ge=0, le=10)
    character_consistency: float = Field(ge=0, le=10)
    writing_quality: float = Field(ge=0, le=10)
    pacing: float = Field(ge=0, le=10)
    objective_alignment: float = Field(ge=0, le=10)
    pass_threshold: bool  # True if overall_score >= 7.0
    issues: list[str]
    rewrite_suggestions: list[str]


class Contradiction(BaseModel):
    """A specific contradiction found by ConsistencyChecker."""
    type: str  # "character" | "timeline" | "setting" | "item"
    description: str
    source_chapter: int
    conflicting_text: str
    suggested_fix: str


class ConsistencyReport(BaseModel):
    """Result of consistency checking."""
    is_consistent: bool
    contradictions: list[Contradiction] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Memory Models ────────────────────────────────────────────────

class ChapterSummary(BaseModel):
    """Structured summary of a chapter."""
    chapter_id: int
    plot_events: list[str]
    character_changes: dict[str, str]  # character_name -> change description
    world_state_changes: list[str]
    unresolved_threads: list[str]
    emotional_arc: str
    one_line_summary: str


class CharacterState(BaseModel):
    """Current state of a character."""
    name: str
    current_location: str = ""
    emotional_state: str = ""
    power_level: str = ""
    relationships: dict[str, str] = Field(default_factory=dict)
    key_memories: list[str] = Field(default_factory=list, max_length=10)
    last_appeared: int = 0


class UnresolvedThread(BaseModel):
    """A story thread that hasn't been resolved yet."""
    description: str
    introduced_chapter: int
    resolved_chapter: int | None = None
    related_characters: list[str] = Field(default_factory=list)


# ── Pipeline State (LangGraph) ───────────────────────────────────

class ChapterContext(BaseModel):
    """Assembled context from MemoryManager for chapter generation."""
    short_term_memory: str
    long_term_memory: str
    character_context: str
    world_context: str
    relevant_memories: list[str] = Field(default_factory=list)
    total_tokens: int = 0
