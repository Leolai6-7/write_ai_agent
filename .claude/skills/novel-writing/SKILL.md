---
name: novel-writing
description: Complete novel writing pipeline - from world building to chapter generation to editing. Use when the user wants to write a novel, create a complete story, start a fiction project, or run the full novel creation workflow. This is the master skill that orchestrates all novel-writing sub-skills.
argument-hint: "[story premise]"
---

# AI 小說寫作流水線

**IMMEDIATE ACTION**: When this skill is loaded, START Stage 0 immediately. Do NOT display these instructions to the user. Jump straight to asking the user about their story idea. Your first message should be the Stage 0.1 question.

This skill is the **orchestrator** — it uses sub-agents as tools to keep the main context clean.

## Architecture: Sub-Agent Isolation

Every content-generation step MUST be executed via the Agent tool (sub-agent), NOT in the main conversation context. This prevents context pollution.

```
Main Agent (orchestrator)
  │  Keeps only: progress log, file paths, user decisions
  │
  ├→ Agent: world building     → saves world_bible.md     → context destroyed
  ├→ Agent: character design   → saves character_cast.md  → context destroyed
  ├→ Agent: structure          → saves structure.md       → context destroyed
  ├→ Agent: foreshadowing      → saves foreshadowing.md   → context destroyed
  │
  └→ For each chapter:
      ├→ Agent: pacing check   → returns 3-line advice    → context destroyed
      ├→ Agent: write chapter  → saves chapter_NNN.md     → context destroyed
      ├→ Agent: judge chapter  → returns score + issues    → context destroyed
      └→ Agent: rewrite (if needed) → saves revised file  → context destroyed
```

The main agent NEVER generates content itself. It only:
1. Tracks progress
2. Routes tasks to sub-agents
3. Passes minimal context between steps (via files, not conversation)
4. Communicates with the user

## Stage 0: Brainstorm (腦力激盪)

**This stage runs in the MAIN agent context — it's a conversation, not a sub-agent task.**

Before generating anything, have a creative brainstorming session with the user. This shapes everything.

### 0.1: Seed (種子)

Start by asking what sparked this story idea. Open-ended:

"你想寫一個什麼樣的故事？可以是一句話、一個畫面、一個角色、甚至只是一種感覺。"

If the user provided $ARGUMENTS, use that as the seed and skip to 0.2.

### 0.2: Explore (探索)

Ask probing questions to expand the idea. Pick 2-3 that feel relevant, conversational pace:

- "這個故事的核心衝突是什麼？主角想要什麼，什麼在阻擋他？"
- "你想讓讀者看完有什麼感受？熱血？心痛？思考人生？"
- "有沒有特別喜歡的小說/動漫/遊戲，想要類似的感覺？"
- "主角是什麼樣的人？你最想寫他的哪一面？"
- "這個世界有什麼特別的？魔法？科技？社會制度？"
- "有沒有特別想寫或想避免的橋段？"

Don't dump all questions at once. React to answers, dig deeper on interesting threads. This should feel like two writers chatting at a coffee shop, not a form.

### 0.3: Shape (定型)

When enough material emerges, synthesize into a **Story Brief**:

```markdown
## 故事概要
- **一句話概述**: [核心故事線]
- **類型**: [genre]
- **主角**: [name, key trait, goal]
- **核心衝突**: [what stands in the way]
- **世界觀基調**: [what makes this world special]
- **情感核心**: [what readers should feel]
- **規模**: [volumes × chapters]
- **參考作品**: [similar works for tone/style]
- **特別要求**: [things to include or avoid]
```

Show to user: "這個方向對嗎？要調整什麼？"

### 0.4: Confirm (確認)

Once approved, save it:

Save Story Brief to `data/planning/story_brief.md`

This file is the **source of truth** for all subsequent sub-agents. Now proceed to Stage 1.

---

## Stage 1: Conception (構思)

Execute each step via Agent tool. After each, read the saved file and show a BRIEF summary to the user (not the full output — they can read the file if interested).

### Step 1.1: World Building

Launch Agent with this prompt:
```
Read the skill instructions at .claude/skills/novel-worldbuilding/SKILL.md and follow them completely.

Input:
- Read story brief from: data/planning/story_brief.md
- Read any existing world YAML from: data/world/ (if exists)

Save the complete output to data/world/world_bible.md
Output in 繁體中文.
```

→ After agent completes, read `data/world/world_bible.md`, show user a 3-line summary. Ask: "世界觀設定完成，要看詳情或調整嗎？"

### Step 1.2: Character Design

Launch Agent with this prompt:
```
Read the skill instructions at .claude/skills/novel-characters/SKILL.md and follow them completely.

Input:
- Read story brief from: data/planning/story_brief.md
- Read world bible from: data/world/world_bible.md

Save the complete output to data/world/character_cast.md
Output in 繁體中文.
```

→ Show 3-line summary. Ask: "角色設計完成，要看詳情或調整嗎？"

### Step 1.3: Structure Architecture

Launch Agent with this prompt:
```
Read the skill instructions at .claude/skills/novel-architect/SKILL.md and follow them completely.

Input:
- Read story brief from: data/planning/story_brief.md
- Read world bible from: data/world/world_bible.md
- Read character cast from: data/world/character_cast.md

Save the complete output to data/planning/structure.md
Output in 繁體中文.
```

→ Show volume/arc overview. Ask: "結構設計完成，滿意嗎？"

### Step 1.4: Foreshadowing Plan

Launch Agent with this prompt:
```
Read the skill instructions at .claude/skills/novel-foreshadowing/SKILL.md and follow them completely.

Input:
- Read structure from: data/planning/structure.md
- Read character cast from: data/world/character_cast.md
- Read world bible from: data/world/world_bible.md

Save the complete output to data/planning/foreshadowing.md
```

→ Show foreshadow count summary. Ask: "伏筆規劃完成。準備開始寫第一章了嗎？"

---

## Stage 2: Creation (創作)

For each chapter in the planned arc, execute these sub-agents in sequence.

### Step 2.1: Pacing Check

Launch Agent with this prompt:
```
Read the skill instructions at .claude/skills/novel-pacing/SKILL.md and follow them.

Input:
- Read the last 5 entries from: data/planning/story_log.md (or "first chapter" if empty)
- Current chapter objective: {objective from structure.md}

Output ONLY a 3-line pacing recommendation (pace, scene types, avoid). Do NOT save a file.
```

Store the 3-line result for the next step.

### Step 2.2: Chapter Generation

Launch Agent with this prompt:
```
Read the skill instructions at .claude/skills/novel-chapter/SKILL.md and follow them.

Input:
- Chapter {N}: {title}
- Objective: {objective}
- Key events: {events}
- Characters: {characters}
- Emotional tone: {tone}
- Pacing advice: {pacing result from 2.1}
- Foreshadowing directives for this chapter: {from foreshadowing.md}
- Read recent context from: data/planning/story_log.md (last 5 entries)
- Read character voices from: data/world/character_cast.md (dialogue voice test section only)

Save the chapter to: data/outputs/chapter_{NNN}.md
```

### Step 2.3: Quality Judgement

Launch Agent with this prompt:
```
Read the skill instructions at .claude/skills/novel-judge/SKILL.md and follow them.

Input:
- Read chapter from: data/outputs/chapter_{NNN}.md
- Chapter objective: {objective}
- Read previous chapter summary from: data/planning/story_log.md (last entry)

Output the evaluation report. Do NOT save a file — return the scores and issues.
```

**If overall score ≥ 7.0**: proceed to Step 2.4.
**If overall score < 7.0**: launch rewrite agent:

```
Read the skill instructions at .claude/skills/novel-rewrite/SKILL.md and follow them.

Input:
- Read chapter from: data/outputs/chapter_{NNN}.md
- Issues: {issues from judge}
- Suggestions: {suggestions from judge}

Save the revised chapter to: data/outputs/chapter_{NNN}.md (overwrite)
```

Re-judge after rewrite. Max 2 rewrite attempts, then force-accept.

### Step 2.4: Update Progress

This step runs in the MAIN agent (not sub-agent) — it's lightweight:

Append to `data/planning/story_log.md`:
```
## 第{N}章：{title}
- 摘要：{one-line summary}
- 評分：{score}/10
- 角色變化：{brief notes}
- 伏筆進展：{planted/hinted/resolved}
- 情感基調：{tone}
```

→ Report to user: "第{N}章完成（{score}/10）：{summary}"
→ After every 5 chapters: "前5章寫完了，要檢查再繼續嗎？"

---

## Stage 3: Editing (編輯)

After completing a volume, launch Agent:
```
Read the skill instructions at .claude/skills/novel-style-audit/SKILL.md and follow them.

Input:
- Read all chapter files from: data/outputs/
- Read character voice references from: data/world/character_cast.md

Save the style report to: data/planning/style_report.md
```

→ Show summary to user. Apply fixes if agreed.

---

## Stage 4: Assembly (組裝)

In the main agent, combine chapters:
1. Read all `data/outputs/chapter_*.md` files
2. Create table of contents
3. Add metadata (word count, character list)
4. Save to `data/outputs/novel_complete.md`

---

## Context Budget Rules

The main agent's context should NEVER exceed these limits:
- **Current state**: chapter number, last score, next objective (~100 tokens)
- **Pacing result**: 3 lines from latest pacing check (~50 tokens)
- **User decisions**: accumulated preferences (~200 tokens)
- **File paths**: what's been saved where (~100 tokens)

Total main context: < 500 tokens of working state. Everything else lives in files.

## File Structure

```
data/
├── world/
│   ├── world_bible.md          # Stage 1.1 — world building output
│   └── character_cast.md       # Stage 1.2 — character design output
├── planning/
│   ├── structure.md            # Stage 1.3 — volume/arc structure
│   ├── foreshadowing.md        # Stage 1.4 — foreshadow plan
│   ├── story_log.md            # Running progress (appended each chapter)
│   └── style_report.md         # Stage 3 — style audit results
└── outputs/
    ├── chapter_001.md
    ├── chapter_002.md
    ├── ...
    └── novel_complete.md        # Stage 4 — final assembled novel
```

## Recovery

If a conversation is interrupted:
1. Read `data/planning/story_log.md` — last completed chapter
2. Read `data/planning/structure.md` — next chapter's objective
3. Resume from the next unwritten chapter
