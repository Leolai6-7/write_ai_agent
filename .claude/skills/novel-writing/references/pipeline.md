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
Read .claude/skills/novel-worldbuilding/SKILL.md and follow completely.
Read story brief from: {STORY_DIR}/planning/story_brief.md
Save output to: {STORY_DIR}/world/world_bible.md
Output in 繁體中文.
```
→ 3-line summary. "世界觀設定完成，要看詳情或調整嗎？"

### 1.2: Character Design
```
Agent prompt:
Read .claude/skills/novel-characters/SKILL.md and follow completely.
Read story brief from: {STORY_DIR}/planning/story_brief.md
Read world bible from: {STORY_DIR}/world/world_bible.md
Save output to: {STORY_DIR}/world/character_cast.md
Output in 繁體中文.
```
→ 3-line summary. "角色設計完成，要看詳情或調整嗎？"

### 1.3: Structure
```
Agent prompt:
Read .claude/skills/novel-architect/SKILL.md and follow completely.
Read story brief from: {STORY_DIR}/planning/story_brief.md
Read world bible from: {STORY_DIR}/world/world_bible.md
Read character cast from: {STORY_DIR}/world/character_cast.md
Save output to: {STORY_DIR}/planning/structure.md
Output in 繁體中文.
```
→ Volume/arc overview. "結構設計完成，滿意嗎？"

### 1.4: Foreshadowing
```
Agent prompt:
Read .claude/skills/novel-foreshadowing/SKILL.md and follow completely.
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
Launch ONE sub-agent with this EXACT prompt:

> Read .claude/skills/novel-context/SKILL.md and follow.
> Chapter: {N}
> Story directory: {STORY_DIR}
> Return a CHAPTER CONTEXT PACKAGE. No file save.

Wait for completion. Store the returned context package.

---

**STEP 2 — Chapter Generation**
Launch ONE sub-agent with this EXACT prompt:

> Read .claude/skills/novel-chapter/SKILL.md and follow.
>
> {paste the CHAPTER CONTEXT PACKAGE from Step 1 here}
>
> Save to: {STORY_DIR}/outputs/chapter_{NNN}.md
> Do NOT update story_log.md.
> Do NOT read any planning or world files.
>
> If you introduce NEW characters, report at the end:
> NEW_CHARACTERS:
> - {name}：{role}，{speaking style}

Wait for completion. If NEW_CHARACTERS reported, append to character_cast.md.

---

**STEP 3 — Update Progress (main agent, no sub-agent)**
Read the generated chapter's first and last paragraphs. Append to story_log.md:

```
## 第{N}章：{title}
- 摘要：{one-line, under 80 chars}
- 角色變化：{who appeared, what changed}
- 伏筆進展：{planted/hinted/resolved}
- 情感基調：{tone}
```

---

**STEP 4 — Update Story Graph**
Launch ONE sub-agent with this EXACT prompt:

> Read {STORY_DIR}/outputs/chapter_{NNN}.md (the chapter just written).
> Read {STORY_DIR}/planning/story_graph.md (the current graph).
>
> Update the graph:
> - 角色出場表: add/update character appearances
> - 地點使用表: add/update locations
> - 伏筆追蹤: update thread status
> - 因果鏈: add new causal links
> - 數值設定: add any new established values
>
> Save updated graph to: {STORY_DIR}/planning/story_graph.md

Wait for completion.

---

**THEN** proceed to the next chapter. Start from Step 1 again with {N+1}.

Quality control is at the ARC level via `/novel-style-audit`, not per-chapter.

Report: "第{N}章完成（{score}/10）：{summary}"
Every 5 chapters: "前5章寫完了，要檢查再繼續嗎？"
Every 10 chapters: check revision_notes.md — if it has 3+ entries, ask:
  "累積了一些設定修訂建議，要暫停來更新世界觀/角色設定嗎？"
  If yes → re-run worldbuilding/character sub-agents with revision notes as input

---

## Stage 3: Editing
```
Agent prompt:
Read .claude/skills/novel-style-audit/SKILL.md and follow.
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
2. Read `{STORY_DIR}/planning/story_log.md` — last chapter
3. Read `{STORY_DIR}/planning/structure.md` — next objective
4. Resume from next unwritten chapter
