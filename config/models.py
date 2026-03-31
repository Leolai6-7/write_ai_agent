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


# ── Foreshadowing Models ────────────────────────────────────────

class Foreshadow(BaseModel):
    """A single foreshadowing thread with lifecycle tracking."""
    description: str
    plant_chapter: int
    hint_chapters: list[int] = Field(default_factory=list)
    resolve_chapter: int
    importance: str = "minor"  # "major" | "minor"
    related_characters: list[str] = Field(default_factory=list)


class ForeshadowPlan(BaseModel):
    """Complete foreshadowing plan for a volume/arc."""
    foreshadows: list[Foreshadow]


class ChapterForeshadowDirective(BaseModel):
    """Per-chapter foreshadowing instructions."""
    plant: list[str] = Field(default_factory=list)   # 本章要埋的伏筆
    hint: list[str] = Field(default_factory=list)    # 本章要暗示的伏筆
    resolve: list[str] = Field(default_factory=list) # 本章要收束的伏筆


# ── Pacing Models ────────────────────────────────────────────────

class PacingAdvice(BaseModel):
    """Pacing recommendation for a chapter."""
    suggested_pace: str = "medium"  # "fast" | "medium" | "slow"
    scene_types: list[str] = Field(default_factory=list)  # ["action", "dialogue", "introspection"]
    avoid: list[str] = Field(default_factory=list)  # things to avoid this chapter
    chapter_length_target: int = 3000


# ── Chapter Objective (expanded) ─────────────────────────────────

class ChapterObjective(BaseModel):
    """Objective for a single chapter."""
    chapter_id: int
    title: str
    objective: str
    key_events: list[str]
    characters_involved: list[str]
    emotional_tone: str
    # Extended fields for full workflow
    foreshadow_directive: ChapterForeshadowDirective | None = None
    pacing_advice: PacingAdvice | None = None
    subplot_milestones: list[str] = Field(default_factory=list)


# ── World Building Models ────────────────────────────────────────

class Location(BaseModel):
    """A location in the story world."""
    name: str
    description: str
    culture: str = ""
    significance: str = ""  # why it matters to the story


class HistoryEvent(BaseModel):
    """A historical event that affects the story."""
    name: str
    description: str
    era: str = ""
    impact: str = ""  # how it affects current story


class Faction(BaseModel):
    """A faction or power group in the world."""
    name: str
    description: str
    leader: str = ""
    stance: str = ""  # "ally" | "enemy" | "neutral"
    goals: list[str] = Field(default_factory=list)


class WorldBible(BaseModel):
    """Complete world-building reference."""
    locations: list[Location] = Field(default_factory=list)
    history_events: list[HistoryEvent] = Field(default_factory=list)
    factions: list[Faction] = Field(default_factory=list)
    magic_rules: list[str] = Field(default_factory=list)
    cultural_details: dict[str, str] = Field(default_factory=dict)


# ── Character Models ─────────────────────────────────────────────

class CharacterProfile(BaseModel):
    """Full character profile for design phase."""
    name: str
    role: str = "ally"  # "protagonist" | "antagonist" | "ally" | "mentor" | "rival"
    age: str = ""
    personality: list[str] = Field(default_factory=list)
    speaking_style: str = ""
    motivation: str = ""
    background: str = ""
    arc_summary: str = ""
    relationships: dict[str, str] = Field(default_factory=dict)


class CharacterCast(BaseModel):
    """Complete cast of characters."""
    characters: list[CharacterProfile]
    relationship_map: dict[str, dict[str, str]] = Field(default_factory=dict)


# ── Judgement Models ─────────────────────────────────────────────

class JudgementResult(BaseModel):
    """Structured quality judgement from JudgeAgent."""
    overall_score: float = Field(ge=0, le=10)
    plot_progression: float = Field(ge=0, le=10)
    character_consistency: float = Field(ge=0, le=10)
    writing_quality: float = Field(ge=0, le=10)
    pacing: float = Field(ge=0, le=10)
    objective_alignment: float = Field(ge=0, le=10)
    pass_threshold: bool
    issues: list[str]
    rewrite_suggestions: list[str]


class Contradiction(BaseModel):
    """A specific contradiction found by ConsistencyChecker."""
    type: str
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
    character_changes: dict[str, str]
    world_state_changes: list[str]
    unresolved_threads: list[str]
    emotional_arc: str
    one_line_summary: str


class CharacterState(BaseModel):
    """Current runtime state of a character."""
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


# ── Story Bible Update ──────────────────────────────────────────

class StoryBibleUpdate(BaseModel):
    """Update instructions from StoryBibleKeeper after each chapter."""
    character_updates: dict[str, str] = Field(default_factory=dict)
    world_changes: list[str] = Field(default_factory=list)
    new_locations_mentioned: list[str] = Field(default_factory=list)
    foreshadow_progress: list[str] = Field(default_factory=list)
    relationship_changes: list[str] = Field(default_factory=list)


# ── Style Editing ────────────────────────────────────────────────

class StyleIssue(BaseModel):
    """A style inconsistency found by StyleEditorAgent."""
    chapter_id: int
    paragraph_index: int
    issue_type: str  # "voice_shift" | "tone_mismatch" | "dialogue_ooc" | "repetition"
    description: str
    suggestion: str


class StyleReport(BaseModel):
    """Style audit report for a volume."""
    volume_name: str
    total_chapters: int
    issues: list[StyleIssue] = Field(default_factory=list)
    overall_consistency_score: float = Field(ge=0, le=10)
    summary: str = ""


# ── Pipeline State (LangGraph) ───────────────────────────────────

class ChapterContext(BaseModel):
    """Assembled context from MemoryManager for chapter generation."""
    short_term_memory: str
    long_term_memory: str
    character_context: str
    world_context: str
    relevant_memories: list[str] = Field(default_factory=list)
    pacing_advice: str = ""
    foreshadow_directive: str = ""
    total_tokens: int = 0
