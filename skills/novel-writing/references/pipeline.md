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

### 2.0: Volume Planning (每卷開始前)

Before writing ANY chapter in a new volume, generate the chapter-level beat sheet for that volume.

1. Determine which volume is next (read structure.md for volume ranges)
2. Launch **volume-planner plugin agent** (has Read + Write):

```
subagent_type: novel-agents:volume-planner
```

Prompt (agent reads files itself):

> Story directory: {STORY_DIR}
> Generate the chapter beat sheet for Volume {V} (弧線：{arc_name}).
>
> Read these files:
> - {STORY_DIR}/planning/structure.md (this volume's arc)
> - {STORY_DIR}/planning/story_brief.md
> - {STORY_DIR}/planning/foreshadowing.md
> - {STORY_DIR}/world/world_bible.md
> - {STORY_DIR}/world/character_cast.md
> - {STORY_DIR}/runtime/story_log.md (if exists)
> - {STORY_DIR}/runtime/story_graph.json (if exists)
>
> Write to: /tmp/volume_plan_{V}.yaml

3. Main agent copies `/tmp/volume_plan_{V}.yaml` → `{STORY_DIR}/planning/volume_plan_{V}.yaml`
4. Show beat sheet summary to user: "第{V}卷章節規劃完成，要看詳情或調整嗎？"
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

Main agent reads `skills/novel-chapter/SKILL.md` and `{STORY_DIR}/planning/story_brief.md`,
then launches the **chapter-writer plugin agent** (Write-only, cannot read files):

```
subagent_type: novel-agents:chapter-writer
```

Paste ALL content into the prompt (the agent has no Read tool):

> === WRITING SKILL ===
> {full content of novel-chapter/SKILL.md}
>
> === STORY BRIEF ===
> {full content of story_brief.md}
>
> === CHAPTER CONTEXT PACKAGE ===
> {CHAPTER CONTEXT PACKAGE from Step 1}
>
> Write the chapter based on the skill, brief, and context above.
> Save to: {STORY_DIR}/outputs/chapter_{NNN}.md
>
> If you introduce NEW characters, report at the end:
> NEW_CHARACTERS:
> - {name}：{role}，{speaking style}

The agent can ONLY Write. It cannot read chapter files, search directories,
or access any information not in the prompt. This prevents cross-line contamination.
If NEW_CHARACTERS reported, main agent appends to character_cast.md.

---

**STEP 3 — Update Progress + Graph**

Launch **progress-updater plugin agent** (has Read + Write):

```
subagent_type: novel-agents:progress-updater
```

Prompt (agent reads files and edits in place):

> Story directory: {STORY_DIR}
> Chapter {N}: {title}
>
> Read these files:
> - {STORY_DIR}/outputs/chapter_{NNN}.md (the chapter just written)
> - {STORY_DIR}/runtime/story_log.md (current progress)
> - {STORY_DIR}/runtime/story_graph.json (current graph — flat JSON format)
>
> Edit story_log.md IN PLACE — append a new entry at the end.
> Write updated story_graph.json to: /tmp/story_graph_updated.json

After agent completes, main agent:
1. story_log.md already updated (Edit in place, hook auto-triggers post-processing)
2. Copies /tmp/story_graph_updated.json → {STORY_DIR}/runtime/story_graph.json

---

**COMPLETION GATE**: All 3 steps must complete before proceeding to chapter {N+1}.

Report: "第{N}章完成：{summary}"
Every 5 chapters: "前5章寫完了，要檢查再繼續嗎？"

---

### 2.9: Arc Review (每卷結束後)

When all chapters in a volume are complete, run the arc review.

1. Main agent reads story_log.md (small file, chapter summaries)
2. Launch **arc-reviewer plugin agent** (has Read + Edit + Write):

```
subagent_type: novel-agents:arc-reviewer
```

Prompt — paste story_log, tell agent where to find files:

> Story directory: {STORY_DIR}
> Review Volume {V} (chapters {start}-{end}).
>
> === STORY LOG (chapter summaries — use as primary source) ===
> {full content of story_log.md}
>
> Edit these files IN PLACE (use Edit tool, not Write):
> - {STORY_DIR}/world/world_bible.md (add new settings)
> - {STORY_DIR}/world/character_cast.md (update 當前狀態 sections)
>
> Write this NEW file:
> - {STORY_DIR}/planning/arc_review_{V}.md (review report)
>
> Files you can Read for detail checks:
> - {STORY_DIR}/outputs/chapter_{NNN}.md
> - {STORY_DIR}/runtime/story_graph.json
> - {STORY_DIR}/planning/structure.md
> - {STORY_DIR}/planning/volume_plan_{V}.yaml

3. Main agent reviews changes (`git diff`) and arc_review report
4. If structure adjustments are recommended, discuss with user before modifying
5. Proceed to next volume → back to 2.0 Volume Planning

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
