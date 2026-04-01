---
name: novel-chapter
description: Generate a single novel chapter. Use when the user wants to write a chapter, generate fiction content, continue a story, or create narrative prose. Adapts to any genre, language, and style based on the story brief.
argument-hint: "[chapter number and objective]"
---

Generate a single chapter from the provided context package.

## Input

- **Context package**: chapter objective, key events, characters, setting, foreshadowing, tone
- **Story brief**: genre, language, style references, target length

## Constraints (hard rules)

- Never use meta-narrative terms (主角, 第一章, 讀者) — characters don't know they're in a story
- Multiple narrative layers have separate setting data — don't bleed details between layers
- Previously established values (numbers, names, facts) must be consistent
- Length must meet the target from story brief
- Output the chapter text directly — no commentary, no explanations

## Style

Don't follow rules. Write literature.

Read the story brief's reference works and prose style field. Write at that level. If the brief references 姜峯楠 or 乙一, write with that restraint and precision. If it references 金庸 or 布蘭乾, write with that sweep and momentum.

## Rewrite Mode

If the input includes JUDGE FEEDBACK:
- Read the existing chapter first
- Fix only what the feedback identifies
- Preserve everything else

## Post-write Checklist (verify after writing, not during)

- [ ] Length in target range
- [ ] No meta-narrative terms
- [ ] No layer contamination
- [ ] Established values consistent
