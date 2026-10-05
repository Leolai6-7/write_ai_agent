---
name: novel-writing
description: Plan, continue, revise, or review a novel in the write_ai_agent project. Route to the relevant story stage and preserve chapter records and continuity. Use for this project's new stories and existing novels, not generic fiction discussion or software maintenance.
argument-hint: "[story premise]"
---

Resume the user's requested stage. First identify the specified story, or use the existing active-story pointer when no story was specified. Do not switch stories or restart brainstorming merely because this skill was invoked.

- **New story:** use the supplied premise; ask for a seed only when it is missing.
- **Continue:** inspect the relevant plan and chapter workflow state, then continue from the unfinished work or next chapter.
- **Revise:** read the target chapter and requested changes, preserve unrelated material, and refresh its log/diff through the revision workflow.
- **Review:** report findings within scope; do not turn review into manuscript edits or the next writing stage.

Read the matching stage in `references/pipeline.md` for artifacts, delegation and completion checks. Shared path and recovery rules apply to all stages; read other design skills only when that stage needs them. Follow the user's requested review cadence rather than adding fixed confirmation pauses.
