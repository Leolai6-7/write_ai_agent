# Novel Writing Pipeline — Complete Workflow

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
- **主角**: [name, key trait, goal]
- **核心衝突**: [what stands in the way]
- **世界觀基調**: [what makes this world special]
- **情感核心**: [what readers should feel]
- **規模**: [volumes × chapters]
- **參考作品**: [similar works]
- **特別要求**: [include or avoid]
```

Show to user: "這個方向對嗎？要調整什麼？"

### 0.4: Confirm
Save approved brief to `data/planning/story_brief.md`. Proceed to Stage 1.

---

## Stage 1: Conception (構思)

Each step via Agent tool. Show BRIEF summary after each, confirm before next.

### 1.1: World Building
```
Agent prompt:
Read .claude/skills/novel-worldbuilding/SKILL.md and follow completely.
Read story brief from: data/planning/story_brief.md
Read any existing world YAML from: data/world/ (if exists)
Save output to: data/world/world_bible.md
Output in 繁體中文.
```
→ 3-line summary. "世界觀設定完成，要看詳情或調整嗎？"

### 1.2: Character Design
```
Agent prompt:
Read .claude/skills/novel-characters/SKILL.md and follow completely.
Read story brief from: data/planning/story_brief.md
Read world bible from: data/world/world_bible.md
Save output to: data/world/character_cast.md
Output in 繁體中文.
```
→ 3-line summary. "角色設計完成，要看詳情或調整嗎？"

### 1.3: Structure
```
Agent prompt:
Read .claude/skills/novel-architect/SKILL.md and follow completely.
Read story brief from: data/planning/story_brief.md
Read world bible from: data/world/world_bible.md
Read character cast from: data/world/character_cast.md
Save output to: data/planning/structure.md
Output in 繁體中文.
```
→ Volume/arc overview. "結構設計完成，滿意嗎？"

### 1.4: Foreshadowing
```
Agent prompt:
Read .claude/skills/novel-foreshadowing/SKILL.md and follow completely.
Read structure from: data/planning/structure.md
Read character cast from: data/world/character_cast.md
Read world bible from: data/world/world_bible.md
Save output to: data/planning/foreshadowing.md
Output in 繁體中文.
```
→ Count summary. "伏筆規劃完成。準備開始寫第一章了嗎？"

---

## Stage 2: Creation (創作)

Per chapter, in sequence:

### 2.1: Pacing
```
Agent prompt:
Read .claude/skills/novel-pacing/SKILL.md and follow.
Read last 5 entries from: data/planning/story_log.md (or "first chapter")
Current chapter objective: {from structure.md}
Output ONLY 3-line pacing recommendation. No file save.
```

### 2.2: Generate Chapter
```
Agent prompt:
Read .claude/skills/novel-chapter/SKILL.md and follow.
Chapter {N}: {title}
Objective: {objective}
Key events: {events}
Characters: {characters}
Emotional tone: {tone}
Pacing advice: {from 2.1}
Foreshadowing directives: {from foreshadowing.md for this chapter}
Read context from: data/planning/story_log.md (last 5 entries)
Read character voices from: data/world/character_cast.md
Save to: data/outputs/chapter_{NNN}.md
```

### 2.3: Judge
```
Agent prompt:
Read .claude/skills/novel-judge/SKILL.md and follow.
Read chapter from: data/outputs/chapter_{NNN}.md
Chapter objective: {objective}
Read previous summary from: data/planning/story_log.md (last entry)
Return scores and issues. No file save.
```

If score ≥ 7.0 → proceed to 2.4
If score < 7.0 → launch rewrite:
```
Agent prompt:
Read .claude/skills/novel-rewrite/SKILL.md and follow.
Read chapter from: data/outputs/chapter_{NNN}.md
Issues: {from judge}
Suggestions: {from judge}
Save revised to: data/outputs/chapter_{NNN}.md (overwrite)
```
Re-judge. Max 2 rewrites, then force-accept.

### 2.4: Update Progress (main agent, not sub-agent)
Append to `data/planning/story_log.md`:
```
## 第{N}章：{title}
- 摘要：{summary}
- 評分：{score}/10
- 角色變化：{notes}
- 伏筆進展：{planted/hinted/resolved}
- 情感基調：{tone}
```

Report: "第{N}章完成（{score}/10）：{summary}"
Every 5 chapters: "前5章寫完了，要檢查再繼續嗎？"

---

## Stage 3: Editing
```
Agent prompt:
Read .claude/skills/novel-style-audit/SKILL.md and follow.
Read all chapters from: data/outputs/
Read character voices from: data/world/character_cast.md
Save report to: data/planning/style_report.md
```
→ Show summary. Apply fixes if agreed.

## Stage 4: Assembly
Main agent combines chapters:
1. Read all `data/outputs/chapter_*.md`
2. Create TOC + metadata
3. Save to `data/outputs/novel_complete.md`

## Recovery
1. Read `data/planning/story_log.md` — last chapter
2. Read `data/planning/structure.md` — next objective
3. Resume from next unwritten chapter
