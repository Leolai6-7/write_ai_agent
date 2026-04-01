---
name: novel-context
description: Assemble the complete context package for a chapter. Reads the story graph, retrieves full sections from source files, and includes pacing advice. Use before generating any chapter. This is the unified RAG layer for the novel writing system.
argument-hint: "[chapter number]"
---

Assemble a CHAPTER CONTEXT PACKAGE for chapter generation.

This skill combines graph-based retrieval, full section extraction,
and pacing analysis into one step.

## Input

- **Chapter number** (from $ARGUMENTS or conversation)
- **Story directory**: `{STORY_DIR}`

## Process

### Step 1: Identify what to retrieve

Read `{STORY_DIR}/planning/structure.md` — find chapter N's row.

If the beat sheet has retrieval tags (角色, 地點, 伏筆, 概念),
use them as direct lookup keys. If not, infer from the objective
and key events.

Extract: title, line (R/S), objective, key events, characters,
emotional tone, and any tagged retrieval keys.

### Step 2: Enrich with story graph

Read `{STORY_DIR}/planning/story_graph.md` to add context
beyond what the chapter row provides:

- **Characters**: when did they last appear? What happened?
  Trace 角色出場表 for last appearance chapters.
- **Foreshadowing**: what threads are active for this chapter?
  Check 伏筆追蹤 for plant/hint/resolve status.
- **Causal chains**: what events led to this chapter's situation?
  Trace 因果鏈 back to find source chapters beyond the last-5 window.
- **Numerical values**: what established numbers might be referenced?
  List from 已確立的數值設定.
- **Dual-line awareness**: what's the other narrative line doing?
  Check 雙線鏡像 for mirror relationships.

### Step 3: Retrieve full sections

Based on Steps 1+2, retrieve FULL sections (not summaries) from:

- `{STORY_DIR}/world/character_cast.md` → full profiles of
  characters in this chapter
- `{STORY_DIR}/world/world_bible.md` → full descriptions of
  locations used in this chapter
- `{STORY_DIR}/planning/foreshadowing.md` → full thread designs
  for active foreshadowing
- `{STORY_DIR}/planning/story_log.md` → last 5 entries PLUS
  any earlier entries the causal chains point to
- `{STORY_DIR}/planning/story_brief.md` → genre, language, style

**Key principle: selective ≠ summarized.** Select which sections
to include, but include them IN FULL.

### Step 4: Pacing advice

Based on the recent story_log entries, assess the rhythm pattern
of the last few chapters and include a brief pacing recommendation:

- What pace does this chapter need? (fast/medium/slow)
- What scene types to favor or avoid?
- Any rhythm concerns? (e.g., too many consecutive tense chapters)

### Step 5: Output

Return a CHAPTER CONTEXT PACKAGE:

```
=== CHAPTER CONTEXT PACKAGE — Chapter {N}: {title} ===

STORY: {genre, style, language}
LINE: {R/S/R+S}
OBJECTIVE: {objective}
KEY EVENTS: {events}
EMOTIONAL TONE: {tone}

PACING: {pace recommendation + reasoning in 2-3 lines}

--- CHARACTER PROFILES ---
{full profiles of involved characters}

--- SETTING ---
{full location descriptions}

--- FORESHADOWING ---
{full thread designs for this chapter}

--- RECENT CHAPTERS ---
{last 5 story_log entries}

--- CAUSAL CONTEXT ---
{earlier entries from causal chain, if any}

--- NUMERICAL VALUES ---
{established values to maintain}

--- DUAL-LINE AWARENESS ---
{what the other line is doing, if applicable}
===
```

Do NOT save any file. Return the package directly.
The chapter generator and judge will receive this package.
