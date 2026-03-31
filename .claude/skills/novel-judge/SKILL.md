---
name: novel-judge
description: Evaluate the quality of a novel chapter across multiple dimensions. Use when reviewing fiction writing quality, scoring a chapter, critiquing creative writing, or deciding if a chapter draft needs revision. Also triggers for beta reading or editorial feedback.
argument-hint: "[chapter text or file path]"
---

Evaluate a novel chapter's quality. Read the story brief first to understand the genre, style, and conventions being targeted.

## Input

From $ARGUMENTS or conversation:
- **Chapter text**: the full chapter to evaluate (or file path to read)
- **Story brief** (if available): determines what "good" means for THIS story
- **Chapter objective** (optional): what the chapter was supposed to achieve
- **Previous chapter summary** (optional): for continuity checking

## Evaluation Dimensions (6 dimensions, 0-10 each)

### 1. Plot Progression
- Does the chapter advance the story?
- Is there at least one meaningful event (not filler)?
- Does it set up future developments?

### 2. Character Consistency
- Do characters behave according to their established personality?
- Does dialogue match each character's voice?
- Do characters THINK differently from each other, not just talk differently?
- Are motivations clear and believable?

### 3. Writing Quality
- Sentence rhythm: variety in length and structure?
- Sensory richness: grounded in specific details, not generic descriptions?
- Dialogue: natural, revealing character, advancing scene?
- Metaphor discipline: serving understanding, not decorating?
- Padding check: unnecessary repetition, meaningless exchanges, over-explanation?

### 4. Pacing
- Tension-release balance appropriate for the genre?
- Does the chapter earn its length? (Could any section be cut without loss?)
- Does the ending create forward momentum? (Method should vary — not always a dramatic cliffhanger)

### 5. Objective Alignment
- Did the chapter achieve its stated objective?
- Were the key events included?
- Does the emotional tone match the plan?

### 6. Overall
Would the target reader (as defined in the story brief) want to continue reading?

## Output Format

```markdown
## 章節評審報告

### 評分
| 維度 | 分數 | 說明 |
|------|------|------|
| 情節推進 | X/10 | ... |
| 角色一致性 | X/10 | ... |
| 文筆品質 | X/10 | ... |
| 節奏感 | X/10 | ... |
| 目標吻合度 | X/10 | ... |
| **綜合** | **X/10** | ... |

### 通過判定
[通過 ✅ / 需改寫 ❌]（pass threshold defined in story brief, default ≥ 7.0）

### 具體問題
1. ...

### 改寫建議
1. ...

### 亮點
1. ...
```

## Evaluation Philosophy

### On Craft
- A metaphor is only good if removing it would lose meaning
- If the text shows then explains, the explanation is the problem
- Repetition of environment details signals autopilot — flag it
- Mechanical patterns (same ending style, same punctuation habits) are signs of habit, not craft

### On Consistency
- Check numerical data against previous chapters — a story that changes its own facts breaks trust
- If the story has multiple narrative layers, check for setting contamination between layers
- If a character references a past event, verify it matches what actually happened

### On Character
- Characters should think differently, not just talk differently
- A protagonist who only reacts to external forces is a structural problem

### On Genre Awareness
- "Good" writing depends on what the story is trying to be — don't judge a literary novel by web novel standards or vice versa
- Read the story brief to understand the target audience, tone, and conventions
- A quiet literary chapter and an action-packed web novel chapter are both valid — judge each by its own standards

## Story Log Entry

After evaluation, output a standardized log entry (for the main agent to append to story_log.md):

```
## 第{N}章：{title}
- 摘要：{one-line summary, under 80 chars}
- 評分：{overall}/10
- 角色變化：{brief character changes}
- 伏筆進展：{planted/hinted/resolved}
- 情感基調：{tone}
```
