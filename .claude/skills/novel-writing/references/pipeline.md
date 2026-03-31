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

Per chapter, in sequence:

### 2.1: Pacing
```
Agent prompt:
Read .claude/skills/novel-pacing/SKILL.md and follow.
Read last 5 entries from: {STORY_DIR}/planning/story_log.md (or "first chapter")
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
Read context from: {STORY_DIR}/planning/story_log.md (last 5 entries)
Read character voices from: {STORY_DIR}/world/character_cast.md
Save to: {STORY_DIR}/outputs/chapter_{NNN}.md
Do NOT update story_log.md — that is the main agent's job after judging.

If you introduce any NEW characters not in character_cast.md, you MUST
report them at the end of your output in this format:
NEW_CHARACTERS:
- {name}：{role/identity}，{speaking style in one sentence}
```

After chapter generation, if the sub-agent reports NEW_CHARACTERS,
the main agent appends them to `{STORY_DIR}/world/character_cast.md`
under a "## 新增配角" section.

### 2.3: Judge
```
Agent prompt:
Read .claude/skills/novel-judge/SKILL.md and follow.
Read chapter from: {STORY_DIR}/outputs/chapter_{NNN}.md
Chapter objective: {objective}
Read previous summary from: {STORY_DIR}/planning/story_log.md (last entry)
Return: scores, issues, suggestions, AND a standardized story_log entry.
No file save — return everything to main agent.
```

If score >= 7.0 → proceed to 2.4
If score < 7.0 → launch rewrite:
```
Agent prompt:
Read .claude/skills/novel-rewrite/SKILL.md and follow.
Read chapter from: {STORY_DIR}/outputs/chapter_{NNN}.md
Issues: {from judge}
Suggestions: {from judge}
Save revised to: {STORY_DIR}/outputs/chapter_{NNN}.md (overwrite)
```
Re-judge. Max 2 rewrites, then force-accept.

### 2.4: Update Progress (main agent, not sub-agent)
Take the story_log entry from judge sub-agent's output and append it to
`{STORY_DIR}/planning/story_log.md`. Do NOT write your own summary — use
the judge's standardized entry verbatim. Format:
```
## 第{N}章：{title}
- 摘要：{from judge, under 80 chars}
- 評分：{from judge}/10
- 角色變化：{from judge}
- 伏筆進展：{from judge}
- 情感基調：{from judge}
```
No extra fields. This is an index, not a full record.

If during judging or writing, any issue suggests core settings need revision
(e.g., "this character's motivation doesn't work", "world rule is inconsistent",
"need a new location"), append to `{STORY_DIR}/planning/revision_notes.md`:
```
## 第{N}章發現
- [描述需要修訂的核心設定問題]
```

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
