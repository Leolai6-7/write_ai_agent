# Novel Writing Pipeline — Complete Workflow

## Multi-Story Path Convention

All file paths use the active story directory:
```
STORY_DIR = data/stories/{active_story}/
```

Before starting any work:
1. Read `data/active_story.txt` to get the active story name
2. If starting a new story, create the directory and update active_story.txt:
   ```
   mkdir -p data/stories/{story-name}/{world,planning,outputs}
   echo "{story-name}" > data/active_story.txt
   ```
3. All sub-agent prompts below use `{STORY_DIR}` — replace with the actual path

## Stage 0: Brainstorm (腦力激盪)

Runs in MAIN agent context — this is a conversation.

### 0.1: Seed
Ask: "你想寫一個什麼樣的故事？可以是一句話、一個畫面、一個角色、甚至只是一種感覺。"

If $ARGUMENTS provided, use as seed and go to 0.2.

### 0.2: Explore
Ask 2-3 follow-up questions about conflict, emotion, world, characters. Conversational, not a form.

### 0.3: Shape
Synthesize into Story Brief:

```markdown
## 故事概要
- **一句話概述**: [核心故事線]
- **類型**: [genre]
- **主角**: [name (REQUIRED — must have a name), key trait, goal]
- **核心衝突**: [what stands in the way]
- **世界觀基調**: [what makes this world special]
- **情感核心**: [what readers should feel]
- **規模**: [volumes × chapters]
- **章節字數**: [target word count per chapter, e.g. 5,000-8,000 字]
- **參考作品**: [similar works]
- **特別要求**: [include or avoid]
```

Show to user: "這個方向對嗎？要調整什麼？"

### 0.4: Confirm
Create story directory and save:
```
mkdir -p {STORY_DIR}/{world,planning,outputs}
echo "{story-name}" > data/active_story.txt
Save brief to: {STORY_DIR}/planning/story_brief.md
```
Proceed to Stage 1.

---

## Stage 1: Conception (構思)

Each step via Agent tool. Show BRIEF summary after each, confirm before next.

### 1.1: World Building
```
Agent prompt:
Read skills/novel-worldbuilding/SKILL.md and follow completely.
Read story brief from: {STORY_DIR}/planning/story_brief.md
Save output to: {STORY_DIR}/world/world_bible.md
Output in 繁體中文.
```
→ 3-line summary. "世界觀設定完成，要看詳情或調整嗎？"

### 1.2: Character Design
```
Agent prompt:
Read skills/novel-characters/SKILL.md and follow completely.
Read story brief from: {STORY_DIR}/planning/story_brief.md
Read world bible from: {STORY_DIR}/world/world_bible.md
Save output to: {STORY_DIR}/world/character_cast.md
Output in 繁體中文.
```
→ 3-line summary. "角色設計完成，要看詳情或調整嗎？"

### 1.3: Structure (卷級弧線，不含章級 beat sheet)
```
Agent prompt:
Read skills/novel-architect/SKILL.md and follow completely.
Read story brief from: {STORY_DIR}/planning/story_brief.md
Read world bible from: {STORY_DIR}/world/world_bible.md
Read character cast from: {STORY_DIR}/world/character_cast.md
Save output to: {STORY_DIR}/planning/structure.md
Output in 繁體中文.

IMPORTANT: Only output volume architecture and arc decomposition.
Do NOT generate chapter-level beat sheets — those are created per-volume
by the volume-planner agent just before writing begins.
```
→ Volume/arc overview. "結構設計完成，滿意嗎？"

### 1.4: Foreshadowing
```
Agent prompt:
Read skills/novel-foreshadowing/SKILL.md and follow completely.
Read structure from: {STORY_DIR}/planning/structure.md
Read character cast from: {STORY_DIR}/world/character_cast.md
Read world bible from: {STORY_DIR}/world/world_bible.md
Save output to: {STORY_DIR}/planning/foreshadowing.md
Output in 繁體中文.
```
→ Count summary. "伏筆規劃完成。準備開始寫第一章了嗎？"

---

## Stage 2: Creation (創作)

### 2.0a: World Expansion (每弧線開始前，如需要)

Before planning chapters, check if the next arc needs new settings:

1. Read structure.md → what's the next arc's core conflict?
2. Does it introduce new locations, factions, characters, or world systems?
3. If yes, expand design docs:
   - Re-run `novel-worldbuilding` skill with new requirements → Edit world_bible.md
   - Re-run `novel-characters` skill for new major characters → Edit character_cast.md
   - Or: conversational expansion with the user → main agent Edits directly
4. If no new settings needed → skip to 2.0b

For the FIRST arc of a story, this step is skipped (Stage 1 covers it).

---

### 2.0b: Arc Planning (每弧線開始前)

After world expansion is complete, generate the chapter-level beat sheet.

structure.md 把每卷分成 2-3 個弧線（例如弧線一 ch1-5、弧線二 ch6-10）。**按弧線規劃，不是按卷。**

1. Determine which arc is next (read structure.md for arc ranges)
2. Launch **volume-planner plugin agent**:

```
subagent_type: novel-agents:volume-planner
```

> Story directory: {STORY_DIR}
> Generate the chapter beat sheet for Arc {A}: {arc_name} (chapters {start}-{end}).
>
> Read design files in {STORY_DIR}/ (structure, story_brief, foreshadowing, world_bible, character_cast, story_log, story_graph.json).
>
> Write to: /tmp/arc_plan_{A}.yaml

3. Main agent copies to `{STORY_DIR}/planning/arc_plan_{A}.yaml`
4. Show summary: "弧線{A}章節規劃完成，要看詳情或調整嗎？"
5. After user confirms → proceed to chapter writing loop

---

### Chapter Writing Loop

For each chapter, follow these steps EXACTLY. Do not combine, skip, or reorder.
Copy the prompts below and fill in {N} and {STORY_DIR}. One sub-agent per step.

---

**STEP 1 — Context Assembly**
```
python scripts/assemble_context.py --story-dir {STORY_DIR} --chapter {N}
```
Store the output as the CHAPTER CONTEXT PACKAGE.

---

**STEP 2 — Chapter Generation**

Launch **chapter-writer plugin agent** (has Read + Write):

```
subagent_type: novel-agents:chapter-writer
```

Prompt — agent reads files itself, context package is navigation only:

> Story directory: {STORY_DIR}
> Chapter {N}: {title}
>
> Read skills/novel-chapter/SKILL.md for writing guidelines.
> Read {STORY_DIR}/planning/story_brief.md for story overview.
>
> {CHAPTER CONTEXT PACKAGE from Step 1 — navigation references + graph warnings}
>
> Write chapter to: {STORY_DIR}/outputs/chapter_{NNN}.md

New characters are detected by progress-updater in Step 3.

---

**STEP 3 — Update Progress + Graph**

Launch **progress-updater plugin agent** (has Read + Write):

```
subagent_type: novel-agents:progress-updater
```

Prompt (agent reads files, edits story_log, writes diff):

> Story directory: {STORY_DIR}
> Chapter {N}: {title}
>
> Read the chapter: {STORY_DIR}/outputs/chapter_{NNN}.md
> Read story_log: {STORY_DIR}/runtime/story_log.md
>
> Edit story_log.md IN PLACE — append a new entry.
> Write chapter diff to: /tmp/chapter_{N}_diff.yaml

After agent completes, main agent runs:
```
python scripts/update_graph.py --story-dir {STORY_DIR} --diff /tmp/chapter_{N}_diff.yaml
```
Hook auto-triggers ChromaDB indexing when story_log.md is edited.

---

**COMPLETION GATE**: All 3 steps must complete before proceeding to chapter {N+1}.

Report: "第{N}章完成：{summary}"
Every 5 chapters: "前5章寫完了，要檢查再繼續嗎？"

---

### 2.9: Arc Review (每弧線結束後)

When all chapters in an arc are complete, run the arc review **before planning the next arc**.

This ensures expanded settings, updated characters, and new foreshadowing are incorporated into the next arc's planning.

1. Main agent reads story_log.md (chapter summaries)
2. Launch **arc-reviewer plugin agent**:

```
subagent_type: novel-agents:arc-reviewer
```

> Story directory: {STORY_DIR}
> Review Arc {A} (chapters {start}-{end}).
>
> === STORY LOG ===
> {full content of story_log.md}
>
> Edit IN PLACE: world_bible.md, character_cast.md, foreshadowing.md, structure.md
> Write NEW: {STORY_DIR}/planning/arc_review_{A}.md
> Read for details: chapter files, story_graph.json, arc_plan_{A}.yaml

3. Main agent reviews changes (`git diff`) and arc_review report
4. Proceed to next arc → back to 2.0 Arc Planning

---

## Stage 3: Editing
```
Agent prompt:
Read skills/novel-style-audit/SKILL.md and follow.
Read all chapters from: {STORY_DIR}/outputs/
Read character voices from: {STORY_DIR}/world/character_cast.md
Save report to: {STORY_DIR}/planning/style_report.md
```
→ Show summary. Apply fixes if agreed.

## Stage 4: Assembly
Main agent combines chapters:
1. Read all `{STORY_DIR}/outputs/chapter_*.md`
2. Create TOC + metadata
3. Save to `{STORY_DIR}/outputs/novel_complete.md`

## Recovery
1. Read `data/active_story.txt` — which story
2. Read `{STORY_DIR}/runtime/story_log.md` — last chapter
3. Read `{STORY_DIR}/planning/structure.md` — next objective
4. Resume from next unwritten chapter
