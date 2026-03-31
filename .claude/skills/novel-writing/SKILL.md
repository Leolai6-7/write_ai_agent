---
name: novel-writing
description: Complete novel writing pipeline - from world building to chapter generation to editing. Use when the user wants to write a novel, create a complete story, start a fiction project, or run the full novel creation workflow. This is the master skill that orchestrates all novel-writing sub-skills.
argument-hint: "[story premise]"
---

# AI 小說寫作流水線

Complete pipeline for writing a long-form novel. This skill orchestrates the full workflow from conception to creation.

## Overview

The pipeline has 4 stages. Execute them in order, confirming with the user between stages.

```
Stage 1: Conception (構思) — one-time setup
  → World Building → Character Design → Structure Architecture → Foreshadowing Plan

Stage 2: Creation (創作) — per-chapter loop
  → Pacing Advice → Chapter Generation → Quality Judgement → (Rewrite if needed)

Stage 3: Editing (編輯) — per-volume
  → Style Audit across chapters

Stage 4: Assembly (組裝) — final
  → Combine chapters into complete document
```

## Input

From $ARGUMENTS or conversation, gather:
- **Story premise**: the core conflict/goal (1-2 sentences)
- **Genre**: 奇幻冒險、都市、科幻、武俠、etc.
- **Scale**: how many volumes? chapters per volume?
- **Any existing materials**: world setting, character ideas, outlines

If the user only gives a premise, that's enough to start.

---

## Stage 1: Conception (構思)

Execute these steps in order. After each step, show the result to the user and confirm before proceeding.

### Step 1.1: World Building
Read the instructions from `.claude/skills/novel-worldbuilding/SKILL.md` and follow them to create a complete world bible.

**Input**: user's premise + genre + any world details they provided
**Output**: World Bible (locations, history, factions, magic system, culture)
**Save to**: `data/world/world_bible.md`

→ Show result to user. Ask: "世界觀設定是否滿意？要調整什麼嗎？"

### Step 1.2: Character Design
Read the instructions from `.claude/skills/novel-characters/SKILL.md` and follow them to design the character cast.

**Input**: world bible + premise + protagonist details
**Output**: Character profiles + relationship map + dialogue voice test
**Save to**: `data/world/character_cast.md`

→ Show result to user. Ask: "角色設計是否滿意？"

### Step 1.3: Structure Architecture
Read the instructions from `.claude/skills/novel-architect/SKILL.md` and follow them to design the novel structure.

**Input**: premise + world + characters + target scale
**Output**: Volume breakdown + arc decomposition + first arc's chapter beats
**Save to**: `data/planning/structure.md`

→ Show result to user. Ask: "結構設計是否滿意？"

### Step 1.4: Foreshadowing Plan
Read the instructions from `.claude/skills/novel-foreshadowing/SKILL.md` and follow them to plan foreshadowing threads.

**Input**: structure + characters + world
**Output**: Foreshadowing plan table + per-chapter directives
**Save to**: `data/planning/foreshadowing.md`

→ Show result to user. Ask: "伏筆規劃是否滿意？準備好開始寫第一章了嗎？"

---

## Stage 2: Creation (創作)

For each chapter in the planned arc:

### Step 2.1: Pacing Check
Read `.claude/skills/novel-pacing/SKILL.md` and analyze recent chapters' rhythm.

**Input**: last 5 chapters' emotional arcs (or "first chapter" if starting)
**Output**: Pacing advice for this chapter

### Step 2.2: Chapter Generation
Read `.claude/skills/novel-chapter/SKILL.md` and generate the chapter.

**Input**: chapter objective + pacing advice + world/character context + foreshadowing directives for this chapter
**Output**: Chapter text (3000-5000 chars)
**Save to**: `data/outputs/chapter_NNN.md`

### Step 2.3: Quality Judgement
Read `.claude/skills/novel-judge/SKILL.md` and evaluate the chapter.

**Input**: chapter text + chapter objective
**Output**: Scores + issues + suggestions

If overall score ≥ 7.0: proceed to next chapter
If overall score < 7.0: rewrite based on suggestions (max 2 attempts), then proceed

### Step 2.4: Update Context
After each chapter, update the running context:
- Summarize the chapter (1-2 sentences)
- Note character changes
- Track foreshadowing progress
- Append to `data/planning/story_log.md`

→ After every 5 chapters, pause and ask: "前5章寫完了，要檢查一下再繼續嗎？"

---

## Stage 3: Editing (編輯)

After completing a volume (or a significant batch of chapters):

Read `.claude/skills/novel-style-audit/SKILL.md` and audit all chapters.

**Input**: all chapter files in `data/outputs/`
**Output**: Style report with issues and suggestions

→ Show report to user. Apply fixes if agreed.

---

## Stage 4: Assembly (組裝)

Combine all chapters into a single document:

1. Create table of contents
2. Add volume/chapter headers
3. Include word count and metadata
4. Save to `data/outputs/novel_complete.md`

---

## User Interaction Guidelines

- **Always confirm between stages** — don't auto-proceed to Stage 2 without user approval of Stage 1
- **Show progress** — after each chapter, briefly report: chapter number, score, one-line summary
- **Be interruptible** — if the user says "stop" or "let me review", pause immediately
- **Save everything** — every output should be saved to a file so work is never lost
- **Track progress** — maintain `data/planning/story_log.md` as a running log

## File Structure

```
data/
├── world/
│   ├── world_bible.md          # Stage 1.1 output
│   └── character_cast.md       # Stage 1.2 output
├── planning/
│   ├── structure.md            # Stage 1.3 output
│   ├── foreshadowing.md        # Stage 1.4 output
│   └── story_log.md            # Running progress log
└── outputs/
    ├── chapter_001.md
    ├── chapter_002.md
    ├── ...
    └── novel_complete.md        # Stage 4 output
```
