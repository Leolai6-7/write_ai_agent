---
name: novel-rewrite
description: Rewrite a novel chapter based on specific quality feedback. Use when a chapter draft needs revision, when editorial feedback needs to be applied, or when a judge/review identified specific issues to fix.
argument-hint: "[chapter text + feedback]"
---

Rewrite a chapter based on structured editorial feedback.

## Input

From $ARGUMENTS or conversation:
- **Original chapter text**: the draft that needs revision
- **Feedback**: from `/novel-judge` or manual editorial notes, including:
  - Issues found (specific problems)
  - Rewrite suggestions (what to change)
  - Score breakdown (which dimensions were weak)

## Rewrite Philosophy

You are an EDITOR, not a rewriter from scratch. Key principles:

1. **Preserve the skeleton**: keep the core plot events, character actions, and chapter structure
2. **Fix what's broken**: target the specific issues identified, don't rewrite unrelated parts
3. **Maintain voice**: don't shift the narrator's style or character voices
4. **Net positive length**: rewrites should maintain or slightly increase word count (no cutting without adding)

## Rewrite by Issue Type

### 情節推進 (Plot) issues
- Add foreshadowing beats or story reveals
- Tighten cause-and-effect chains
- Cut irrelevant digressions that don't serve the plot

### 角色一致性 (Character) issues
- Revise dialogue to match established speaking patterns
- Add character-specific reactions and mannerisms
- Fix out-of-character decisions with proper motivation

### 文筆品質 (Writing) issues
- Vary sentence length (break up monotonous rhythm)
- Replace generic descriptions with sensory-specific ones
- Fix 水字數: cut repetitive descriptions, merge redundant paragraphs
- Add 成語/四字詞 where natural (not forced)

### 節奏感 (Pacing) issues
- Add cliffhanger if chapter ending is flat
- Insert a breather scene if too intense throughout
- Cut padding if chapter drags in the middle

### 一致性 (Consistency) issues
- Fix factual contradictions with established story
- Correct character knowledge (they shouldn't know things they haven't learned yet)
- Fix timeline/location errors

## Output

Output the complete revised chapter text. No explanations, no diff markers, no "改動說明".

Just the rewritten chapter, ready to read.

After the chapter, add a brief summary:
```
---
改寫摘要：修正了[X]處對話語氣、加強了結尾懸念、補充了[場景]的環境描寫。
```
