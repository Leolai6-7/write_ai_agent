---
name: novel-context-retrieve
description: Retrieve full context sections from source files based on a retrieval plan. Use after /novel-graph-query to assemble the complete context package for chapter generation. This is Layer 2 of the RAG system.
argument-hint: "[retrieval plan]"
---

Execute a retrieval plan to assemble a CHAPTER CONTEXT PACKAGE.

## Input

- **Retrieval plan** (from `/novel-graph-query` or conversation)
- **Source files** in `{STORY_DIR}/`

## Key Principle

**Selective ≠ summarized.** Retrieve the sections identified in the plan, include them IN FULL. Do not compress, paraphrase, or summarize. The writing quality depends on rich, textured source material.

## Process

Follow the retrieval plan step by step:

### 1. Character Profiles
For each character listed in the plan:
- Open `{STORY_DIR}/world/character_cast.md`
- Find that character's FULL section (everything between their heading and the next heading)
- Include: name, role, personality, speaking style, motivation, background, arc, relationships
- Do NOT truncate or summarize

### 2. Location Descriptions
For each location listed in the plan:
- Open `{STORY_DIR}/world/world_bible.md`
- Find that location's FULL section
- Include: sensory details, cultural character, story significance

### 3. Foreshadowing Threads
For each thread listed in the plan:
- Open `{STORY_DIR}/planning/foreshadowing.md`
- Find that thread's FULL design block
- Include: type, description, plant/hint/resolve details, connection to main conflict

### 4. Story Log Entries
- Open `{STORY_DIR}/planning/story_log.md`
- Retrieve the last 5 entries as specified
- ALSO retrieve any specific earlier entries the plan points to (causal chain roots, character key scenes)

### 5. Numerical Values
- List all values from the plan with their exact numbers and source chapters
- These are for the writer to reference and maintain consistency

### 6. Story Brief
- Open `{STORY_DIR}/planning/story_brief.md`
- Extract genre, language, style, emotional core

## Output: CHAPTER CONTEXT PACKAGE

```
=== CHAPTER CONTEXT PACKAGE — Chapter {N}: {title} ===

STORY: {genre, style, language, emotional core}
LINE: {R/S/R+S}
OBJECTIVE: {from structure}
KEY EVENTS: {from structure}
EMOTIONAL TONE: {from structure}

--- CHARACTER PROFILES ---
{full profile of character A}

{full profile of character B}

--- SETTING ---
{full location description}

--- FORESHADOWING THREADS ---
{full thread A design}

{full thread B design}

--- RECENT CHAPTERS ---
{story_log entries as specified in retrieval plan}

--- CAUSAL CONTEXT ---
{specific earlier chapter entries from retrieval plan}

--- NUMERICAL VALUES ---
- {setting}: {value} (ch{X})
- ...

--- DUAL-LINE AWARENESS ---
{mirror relationships from retrieval plan}
===
```

This package is passed directly to the chapter generator sub-agent. The generator should NOT read any source files — everything it needs is in this package.
