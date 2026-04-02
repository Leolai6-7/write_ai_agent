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

## Architecture: Sub-Agent Isolation

Every content-generation step MUST use the Agent tool (sub-agent). The main agent only:
1. Talks to the user
2. Tracks progress (< 500 tokens of state)
3. Routes tasks to sub-agents via files
4. Never generates novel content itself

## Stage 0: Brainstorm (腦力激盪)

Runs in MAIN agent context — this is a conversation.

### 0.1: Seed
Ask: "你想寫一個什麼樣的故事？可以是一句話、一個畫面、一個角色、甚至只是一種感覺。"

If $ARGUMENTS provided, use as seed and go to 0.2.

### 0.2: Explore
React to user's answer. Ask 2-3 follow-up questions (conversational, not a form):

- "這個故事的核心衝突是什麼？主角想要什麼，什麼在阻擋他？"
- "你想讓讀者看完有什麼感受？熱血？心痛？思考人生？"
- "有沒有特別喜歡的小說/動漫/遊戲，想要類似的感覺？"
- "主角是什麼樣的人？你最想寫他的哪一面？"
- "這個世界有什麼特別的？"
- "有沒有特別想寫或想避免的橋段？"

Feel like two writers chatting, not filling a form.

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

### 1.3: Structure
```
Agent prompt:
Read skills/novel-architect/SKILL.md and follow completely.
Read story brief from: {STORY_DIR}/planning/story_brief.md
Read world bible from: {STORY_DIR}/world/world_bible.md
Read character cast from: {STORY_DIR}/world/character_cast.md
Save output to: {STORY_DIR}/planning/structure.md
Output in 繁體中文.
```
→ Volume/arc overview. "結構設計完成，滿意嗎？"

### 1.3.5: Validate Structure (optional debug tool)
If needed, run `python scripts/validate_structure.py --story-dir {STORY_DIR}`
to check that all beat sheet characters exist in character_cast.md.
This should not be necessary if novel-characters SKILL.md naming rules are followed.

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

### Execution Protocol

For each chapter, follow these steps EXACTLY. Do not combine, skip, or reorder.
Copy the prompts below and fill in {N} and {STORY_DIR}. One sub-agent per step.

---

**STEP 1 — Context Assembly**
Run the assembly tool (no sub-agent needed):
```
python scripts/assemble_context.py --story-dir {STORY_DIR} --chapter {N}
```

This performs three-path recall in < 10 seconds:
1. Structured lookup (beat sheet tags + keyword extraction → source files)
2. Graph traversal (causal chains, absent characters, numerical values)
3. Semantic search (ChromaDB vector similarity)

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

Main agent reads chapter + current log + current graph, then launches
**progress-updater plugin agent** (Write only):

```
subagent_type: novel-agents:progress-updater
```

Paste ALL content into the prompt:

> === CHAPTER TEXT ===
> {full content of chapter_{NNN}.md}
>
> === CURRENT STORY LOG ===
> {full content of runtime/story_log.md}
>
> === CURRENT STORY GRAPH ===
> {full content of runtime/story_graph.md}
>
> Chapter {N}: {title}
> Update both files based on what happened in the chapter.
>
> Write updated story_log to: /tmp/story_log_updated.md
> Write updated story_graph to: /tmp/story_graph_updated.md

After agent completes, main agent:
1. Copies /tmp/story_log_updated.md → {STORY_DIR}/runtime/story_log.md
2. Copies /tmp/story_graph_updated.md → {STORY_DIR}/runtime/story_graph.md
3. Hook auto-triggers post-processing (index + sync)

---

**COMPLETION GATE — Do NOT proceed until ALL 3 steps are done:**
- [ ] Step 1 (context) completed
- [ ] Step 2 (chapter) completed and saved to file
- [ ] Step 3 (story_log + story_graph) updated by main agent

If ANY step is missing, the chapter is NOT complete.
Only after all 4 checkmarks → proceed to next chapter with {N+1}.

Quality control is at the ARC level via `/novel-style-audit`, not per-chapter.

Report: "第{N}章完成：{summary}"
Every 5 chapters: "前5章寫完了，要檢查再繼續嗎？"
Every 10 chapters (arc boundary):
  - Ask: "弧線完成。要回顧這 10 章中出現的新設定，把重要的加入 world_bible 嗎？"
  - Check revision_notes.md — if it has 3+ entries, ask:
    "累積了一些設定修訂建議，要暫停來更新世界觀/角色設定嗎？"
    If yes → re-run worldbuilding/character sub-agents with revision notes as input

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
