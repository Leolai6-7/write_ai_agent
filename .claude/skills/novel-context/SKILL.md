---
name: novel-context
description: Assemble the complete context package for a chapter. Uses beat sheet retrieval tags as primary index, Grep for precise extraction, and story graph only for cross-arc lookups. Use before generating any chapter.
argument-hint: "[chapter number]"
---

Assemble a CHAPTER CONTEXT PACKAGE for chapter generation.

## Input

- **Chapter number** (from $ARGUMENTS or conversation)
- **Story directory**: `{STORY_DIR}`

## Process

### Phase A: Parallel reads (no dependencies)

Launch ALL of these simultaneously:

1. **Beat sheet row** — Grep `{STORY_DIR}/planning/structure.md` for
   `^\| {N} \|` to get the chapter's row. Extract: title, line (R/S),
   objective, key events, emotional tone, and retrieval tags
   (角色, 地點, 伏筆 columns).

2. **Story brief** — Read `{STORY_DIR}/planning/story_brief.md` in full.
   Always needed. (~2KB)

3. **Story log** — Read `{STORY_DIR}/planning/story_log.md`. Take the
   last 5 entries. Always needed.

4. **Semantic search** (if indexed chapters exist) — Run:
   ```
   python scripts/semantic_search.py --story-dir {STORY_DIR} --query "{chapter objective}" --n 3
   ```
   If the script returns results, include them under `--- SEMANTIC RECALL ---`.
   If the DB doesn't exist yet or returns empty, skip silently.

### Phase B: Targeted extraction (after beat sheet row is available)

Use the retrieval tags from the beat sheet row as lookup keys.
Launch ALL of these simultaneously:

4. **Character profiles** — For each character name in the 角色 column:
   Grep `{STORY_DIR}/world/character_cast.md` for `## .*{角色名}`
   to find the heading line number. Then Read from that line to
   the next `## ` heading (typically ~25 lines per character).
   Include FULL profiles, not summaries.

5. **Location descriptions** — For each location in the 地點 column:
   Grep `{STORY_DIR}/world/world_bible.md` for `### .*{地點名}`
   to find the heading line number. Then Read from that line to
   the next `### ` heading.

6. **Foreshadowing threads** — For each thread tagged in the 伏筆 column
   (e.g., ①plant → search for 伏筆一):
   Grep `{STORY_DIR}/planning/foreshadowing.md` for `### 伏筆{漢字數字}`
   to find the heading line number. Then Read the full thread design.

7. **Story graph** (CONDITIONAL — only if needed):
   Read `{STORY_DIR}/planning/story_graph.md` ONLY when:
   - A character hasn't appeared for 5+ chapters (check story_log)
   - The beat sheet references events from a distant chapter
   - Numerical values need consistency checking
   If none of these apply, skip this step entirely.

### Phase C: Assemble

Combine all retrieved content into the output format below.
For pacing: look at the last 2-3 story_log entries' 情感基調
and recommend whether this chapter needs fast/medium/slow pace.

## Grep Patterns Reference

These patterns assume the source files use consistent markdown headings.
If a Grep returns no results, fall back to reading the full file.

```
Beat sheet row:    ^\| {N} \|
Character:         ^## .*{name}
Location:          ^### .*{location}
Foreshadowing:     ^### 伏筆{chinese_numeral}
```

Chinese numerals: 一二三四五六七八九十十一十二

## Output

Return a CHAPTER CONTEXT PACKAGE:

```
=== CHAPTER CONTEXT PACKAGE — Chapter {N}: {title} ===

STORY: {genre, style, language from story_brief}
LINE: {R/S/R+S}
TARGET LENGTH: {章節字數 from story brief}
OBJECTIVE: {objective from beat sheet}
KEY EVENTS: {events — each one should become a full scene}
EMOTIONAL TONE: {tone}

PACING: {recommendation + reasoning in 2-3 lines}

--- CHARACTER PROFILES ---
{full profiles of involved characters, verbatim from source}

--- SETTING ---
{full location descriptions, verbatim from source}

--- FORESHADOWING ---
{full thread designs for this chapter}

--- RECENT CHAPTERS ---
{last 5 story_log entries}

--- CAUSAL CONTEXT ---
{from story_graph if read, otherwise: "N/A — no cross-arc references"}

--- NUMERICAL VALUES ---
{from story_graph if read, otherwise: "Check story_graph if referencing
previously established numbers"}

--- SEMANTIC RECALL ---
{results from semantic_search.py, or "N/A — no indexed chapters yet"}

--- DUAL-LINE AWARENESS ---
{brief note on what the other narrative line did in its last chapter,
derived from story_log}
===
```

Do NOT save any file. Return the package directly.
