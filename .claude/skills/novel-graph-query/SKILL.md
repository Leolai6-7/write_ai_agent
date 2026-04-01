---
name: novel-graph-query
description: Query the story graph to find what context a chapter needs. Use before writing any chapter to identify which characters, locations, foreshadowing threads, causal chains, and numerical values are relevant. This is Layer 1 of the RAG system.
argument-hint: "[chapter number]"
---

Query the story graph to produce a RETRIEVAL PLAN for a specific chapter.

## Input

- **Chapter number** (from $ARGUMENTS or conversation)
- **Story graph file**: `{STORY_DIR}/planning/story_graph.md`
- **Structure file**: `{STORY_DIR}/planning/structure.md`

## Process

### Step 1: Read the chapter plan
From structure.md, extract chapter N's: title, line (R/S), objective, key events, characters involved, emotional tone.

### Step 2: Query the story graph
Read story_graph.md and answer these questions:

**Characters:**
- Who appears in this chapter? (from structure)
- When did they last appear? (from 角色出場表)
- What happened in their last appearance? (cross-ref with story_log)
- → Output: list of characters + their source chapters

**Locations:**
- What location is this chapter set in? (from structure/events)
- Has this location appeared before? (from 地點使用表)
- → Output: location name + source file section to retrieve

**Foreshadowing:**
- What threads need action this chapter? (from 伏筆追蹤 — check plant/hint/resolve columns)
- Where were these threads last referenced? (trace back through 伏筆追蹤)
- → Output: thread names + full lifecycle to retrieve

**Causal chains:**
- What events caused the current chapter's situation? (from 因果鏈)
- Trace back through the chain — which chapters are the roots?
- → Output: source chapter numbers beyond the last-5 window

**Numerical values:**
- What established values might be referenced? (from 已確立的數值設定)
- → Output: list of values with their source chapters

**Dual-line mirrors:**
- If this is an R chapter, what was the last S chapter doing? (from 雙線鏡像)
- Any planned mirror/parallel with the other line?
- → Output: mirror relationships to be aware of

### Step 3: Output the RETRIEVAL PLAN

```
=== RETRIEVAL PLAN for Chapter {N} ===

RETRIEVE FROM character_cast.md:
- {character A} — full profile (last seen ch{X}, did {event})
- {character B} — full profile (last seen ch{Y})

RETRIEVE FROM world_bible.md:
- {location} — full description

RETRIEVE FROM foreshadowing.md:
- Thread {name} — full design (status: {plant/hint/resolve} this chapter)

RETRIEVE FROM story_log.md:
- Last 5 entries: ch{N-5} through ch{N-1}
- ALSO retrieve ch{X} (causal chain root: {reason})
- ALSO retrieve ch{Y} (character's key scene: {reason})

NUMERICAL VALUES TO VERIFY:
- {setting}: {value} (established ch{X})
- {setting}: {value} (established ch{Y})

DUAL-LINE AWARENESS:
- Last {R/S} chapter: ch{X} — {summary}
- Mirror relationship: {description}
===
```

This retrieval plan is passed to `/novel-context-retrieve` or the context assembly sub-agent.
