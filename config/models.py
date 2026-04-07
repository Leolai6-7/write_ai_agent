"""Pydantic models for structured data types used by memory and pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Foreshadowing ──────────────────────────────────────────────

class Foreshadow(BaseModel):
    """A single foreshadowing thread with lifecycle tracking."""
    description: str
    plant_chapter: int
    hint_chapters: list[int] = Field(default_factory=list)
    resolve_chapter: int
    importance: str = "minor"  # "major" | "minor"
    related_characters: list[str] = Field(default_factory=list)


class ChapterForeshadowDirective(BaseModel):
    """Per-chapter foreshadowing instructions."""
    plant: list[str] = Field(default_factory=list)
    hint: list[str] = Field(default_factory=list)
    resolve: list[str] = Field(default_factory=list)


# ── Chapter ────────────────────────────────────────────────────

class ChapterObjective(BaseModel):
    """Objective for a single chapter."""
    chapter_id: int
    title: str
    objective: str
    key_events: list[str]
    characters_involved: list[str]
    emotional_tone: str
    foreshadow_directive: ChapterForeshadowDirective | None = None
    subplot_milestones: list[str] = Field(default_factory=list)


class ChapterSummary(BaseModel):
    """Structured summary of a chapter."""
    chapter_id: int
    plot_events: list[str]
    character_changes: dict[str, str]
    world_state_changes: list[str]
    unresolved_threads: list[str]
    emotional_arc: str
    one_line_summary: str


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


# ── Character ──────────────────────────────────────────────────

class CharacterProfile(BaseModel):
    """Full character profile for design phase."""
    name: str
    role: str = "ally"
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


class CharacterState(BaseModel):
    """Current runtime state of a character."""
    name: str
    current_location: str = ""
    emotional_state: str = ""
    power_level: str = ""
    relationships: dict[str, str] = Field(default_factory=dict)
    key_memories: list[str] = Field(default_factory=list, max_length=10)
    last_appeared: int = 0
