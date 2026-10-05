# Novel Writing Pipeline — Complete Workflow

## Platform adapters

The required artifacts and Python completion checks are shared by Codex and Claude.
`novel-agents:*` below names the Claude adapter; with Codex, use the matching role
instructions in `agents/` through available delegation, or execute the roles in
sequence. Agent names/tool restrictions are not prerequisites of the core CLI.
The Codex entry is `codex-skills/novel-writing/SKILL.md`; resume the existing stage
instead of restarting brainstorming. Honor the user's requested scope and review
cadence rather than introducing extra confirmation pauses.

## Multi-Story Path Convention

All file paths use the active story directory:
```
STORY_DIR = data/stories/{active_story}/
```

Before starting any work:
1. Use the user's explicit story directory first; otherwise read `data/active_story.txt` and verify that the directory exists. A missing pointer is not permission to guess or create a replacement story.
2. If starting a new story, create the directory and update active_story.txt:
   Create its `world`, `planning`, `runtime` and `outputs` directories and update
   the active-story pointer through the file-editing tool. Preserve existing stories.
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
Create {STORY_DIR}/{world,planning,runtime,outputs} and update data/active_story.txt
Save brief to: {STORY_DIR}/planning/story_brief.md
```
Proceed to Stage 1.

---

## Stage 1: Conception (構思)

Use delegation or perform the roles sequentially. Show brief progress summaries;
pause for choices that materially change the story, or at the user's requested
checkpoints. The sample questions below are optional prompts, not mandatory stops.

### 1.1: World Building
```
Agent prompt:
Read skills/novel-worldbuilding/SKILL.md and follow completely.
Read story brief from: {STORY_DIR}/planning/story_brief.md
Save output to: {STORY_DIR}/world/world_bible.md
Output in 繁體中文.
```
→ 3-line summary. "世界觀設定完成，要看詳情或調整嗎？"

**1.1b: Wiki Expansion (after user confirms world bible)**
Main agent splits `world_bible.md` into wiki structure:
```
mkdir -p {STORY_DIR}/world/{locations,setting,history}
```
For each location in world_bible → create `{STORY_DIR}/world/locations/{name}.md`
For setting sections → create `{STORY_DIR}/world/setting/{name}.md`
For history → create `{STORY_DIR}/world/history/{name}.md`
Create `{STORY_DIR}/world/_index.md` with summary table linking all articles.
Keep `world_bible.md` as fallback source.
`assemble_context.py` auto-matches beat sheet locations to wiki articles.

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

### 1.2.5: Story Expansion

Expand the one-line premise into a one-page story overview:
- 3-5 major turning points across the full story
- Character arc directions (where each major character starts → ends)
- Emotional trajectory of the overall narrative

This is a conversation with the user, not a sub-agent task. Main agent writes the result.
Save to: `{STORY_DIR}/planning/story_expansion.md`

"故事走向概述完成，這些轉折點對嗎？"

### 1.3: Structure (彈性卷級弧線，不含章級 beat sheet)
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
   - **Wiki sync**: create new wiki articles under `{STORY_DIR}/world/locations/` etc. for any new settings, update `_index.md`
4. If no new settings needed → skip to 2.0b

For the FIRST arc of a story, this step is skipped (Stage 1 covers it).

---

### 2.0b: Arc Planning (每弧線開始前)

After world expansion is complete, generate the chapter-level beat sheet.

依 structure.md 已確認的弧線與章號範圍規劃；弧線數量由故事決定。**按當前弧線細化，不預先鎖定整卷逐章安排。**

1. Determine which arc is next (read structure.md for arc ranges)
2. Launch **volume-planner plugin agent**:

```
subagent_type: novel-agents:volume-planner
```

> Story directory: {STORY_DIR}
> Generate the chapter beat sheet for Arc {A}: {arc_name} (chapters {start}-{end}).
>
> Read relevant sections of the structure, brief, foreshadowing, world and character files. Use scoped chapter-bounded graph/log references for history, not the whole living graph as past knowledge.
>
> Write BOTH outputs: {STORY_DIR}/planning/arc_synopsis_{A}.md and {STORY_DIR}/planning/arc_plan_{A}.yaml.
> For consequential choices, establish the character's basis, trigger, credible alternatives and expected costs; optional decision_points carries that plan to the writer. Follow docs/character-decisions.md as needed, without imposing a decision template on ordinary scenes.

3. Main agent verifies both outputs and the intended arc/chapter range; preserve any plan outside the authorized scope.
4. Show summary: "弧線{A}章節規劃完成，要看詳情或調整嗎？"
5. Proceed within the agreed scope; ask before a material story-direction change.

---

### Chapter Writing Loop

For each chapter, retain context → draft → lightweight edit → log/diff → graph update → validation.
Fill in {N} and {STORY_DIR}. Roles may be delegated or performed sequentially;
do not skip required artifacts or write dependent chapters concurrently.

---

**STEP 1 — Context Assembly**
```
.venv/bin/python scripts/assemble_context.py --story-dir {STORY_DIR} --chapter {N} --format json
```
Pass `context_package` with its omission/source diagnostics to the writer. Successful assembly records a context receipt in the story's `runtime/chapter_workflow.json`. A smaller package does not mean omitted evidence is absent; use its exact source spans for targeted follow-up.

The package includes the YAML/Markdown beat, previous same-line ending, earlier log entries, chapter-bounded graph facts, and one selected memory recall. Modes `off`/`shadow` use the existing local Chroma index; `active` uses only Jev-Mem. Shadow evidence is excluded from both writer text and JSON. An unavailable backend leaves structured sources and the canonical graph available; do not silently switch backends. See `docs/memory-workflow.md` for setup and recovery.

Read the package's distinct author-intent, canon, POV knowledge/belief, continuity
and reference sections according to their labels. No recorded POV/knowledge means
unknown, not omniscience or proven ignorance. Optional `narrative_updates` must
cite real manuscript lines; source hashing is handled by the graph CLI. The text
package has a character budget and reports omitted optional blocks. Follow the
listed source spans for targeted reading instead of loading full living profiles;
never remove knowledge qualifiers to fit the budget. See `docs/narrative-context.md`.

---

**STEP 2 — Chapter Draft and Lightweight Edit**

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
> Follow the lightweight editorial pass in the writing skill before handoff.
> For major choices, check the prose supplies the reason for accepting the risk, not only the planned action or a warning. Trace missing support to its responsible stage before repairing it; keep planned later information outside earlier character knowledge.
> Write the final chapter to: {STORY_DIR}/outputs/chapter_{NNN}.md

Ordinary chapters use the writer's full-draft self-check, not a mandatory second
agent or separate editorial report. The main agent may request a bounded independent
review for a major turning point, an unresolved continuity concern or a user request.
Resolve necessary scoped revisions before Step 3 reads the prose. Editorial checks
are part of Step 2, not a new CLI receipt or a claim of objectively verified quality.
New characters are detected by progress-updater in Step 3.

---

**STEP 3 — Update Progress + Graph**

Launch **progress-updater plugin agent** (has Read + Edit + Write):

```
subagent_type: novel-agents:progress-updater
```

Prompt (agent reads files, edits story_log, writes diff):

> Story directory: {STORY_DIR}
> Chapter {N}: {title}
>
> Read the chapter: {STORY_DIR}/outputs/chapter_{NNN}.md
> Read this chapter's existing log entry and the relevant prior entries in {STORY_DIR}/runtime/story_log.md.
> Use the supplied relevant chapter-bounded narrative IDs and existing foreshadow keys. For revision, also read the previously applied diff for chapter {N}; it is an identity/completeness checklist, not proof that removed prose still happened.
>
> Edit story_log.md IN PLACE — append a new entry, or replace this chapter's existing entry when revising.
> Write the COMPLETE chapter diff to: {TASK_TMP_DIR}/chapter_{N}_diff.yaml. This is not merely the latest edit patch.

The main agent creates a unique task temporary directory (for example with
`mktemp -d`) and supplies its actual path. Do not share fixed `/tmp` filenames
across stories. Extract only the requested chapter's prior diff and relevant
IDs from the validated graph; do not pass its full cumulative state to the writer.

After agent completes, main agent runs:
```
.venv/bin/python scripts/update_graph.py --story-dir {STORY_DIR} --diff {TASK_TMP_DIR}/chapter_{N}_diff.yaml
```
This validates and atomically saves the graph, records the applied diff against the chapter and log, and queues optional Chroma indexing in `off`/`shadow` mode after the required steps are complete. `active` skips that index (`not_selected`); Jev capture remains an explicit `novel_memory.py sync --chapter N` action, not automatic ingestion. A log edit alone leaves the graph step pending.

When replacing an already tracked chapter's diff, use `--replace`; the graph replays the recorded chapter history. Recheck affected later chapters because their prior context may have changed.

Check status before reopening a historical chapter. `needs_review` means its own
artifacts stayed unchanged but earlier evidence changed: inspect the impact and
record `chapter_workflow.py review --story-dir {STORY_DIR} --chapter-num {N}
--reason 'specific review conclusion'` if it still fits. A direct local edit needs
the normal update steps. `needs_review` is not `complete` and cannot be used as
current memory; it does not block the Stop hook. See `docs/memory-workflow.md`.

---

**COMPLETION GATE**: Verify all 3 steps before proceeding to chapter {N+1}:

```
.venv/bin/python scripts/chapter_workflow.py status --story-dir {STORY_DIR} --chapter-num {N}
```

Proceed when `complete` is `true`. Otherwise, complete the steps named in `missing` and check again. Index states such as `pending`, `unavailable`, or `error` are reported separately and do not block the chapter. The optional semantic extra and embedding model can be installed explicitly; the chapter workflow does not download a model automatically.

Report: "第{N}章完成：{summary}"
Use the agreed review cadence; do not stop every five chapters by default.

---

### 2.9: Arc Review (每弧線結束後)

When all chapters in an arc are complete, run the arc review **before planning the next arc**.

This ensures expanded settings, updated characters, and new foreshadowing are incorporated into the next arc's planning.

1. Main agent uses relevant log entries to define the review scope and locate sources. The reviewer verifies those passages; reserve a second independent source check for consequential or disputed findings.
2. Launch **arc-reviewer plugin agent**:

```
subagent_type: novel-agents:arc-reviewer
```

> Story directory: {STORY_DIR}
> Review Arc {A} (chapters {start}-{end}).
>
> Read agents/arc-reviewer.md and the relevant log entries; verify proposed changes against the source chapters.
> Scope: {review only / authorized arc maintenance / specific user-authorized setting revision}.
>
> For authorized setting maintenance, edit only affected sections of world_bible.md, character_cast.md, foreshadowing.md and their corresponding wiki entries. Edit structure.md only when the user separately authorized the relevant plan change.
> An authorized definition change replaces the original definition precisely; record old/new text, source and affected scope in the specified report. Do not silently canonize a draft contradiction or rewrite historical chapters.
> Report: {STORY_DIR}/planning/arc_review_{A}.md — create or update only if a saved report is in scope; otherwise return findings.
> Read relevant details from chapter files and arc_plan_{A}.yaml; use chapter-bounded graph references rather than treating today's full graph as past knowledge.

3. Main agent checks actual edited sections and the report, including unchanged material outside scope (`git diff` where tracked). Setting edits do not automatically trigger chapter `needs_review`; list any affected chapters and unresolved continuity questions explicitly.
4. Proceed to next arc → back to 2.0 Arc Planning once required decisions are settled. A review-only request ends with findings, not unrequested maintenance or next-arc generation.

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
1. Resume the explicitly requested story; otherwise read `data/active_story.txt` and verify its directory
2. Read `{STORY_DIR}/runtime/story_log.md` and inspect the latest chapter files
3. Query `chapter_workflow.py status` for the interrupted chapter and finish its `missing` steps; a log entry alone does not establish completion
4. Read the current `arc_plan_N.yaml` (Markdown fallback) for the next chapter objective
5. Resume the next chapter after the required-step status is complete; see `docs/memory-workflow.md` for older stories and optional memory setup
