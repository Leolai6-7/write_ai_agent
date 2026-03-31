---
name: novel-judge
description: Evaluate the quality of a novel chapter across multiple dimensions. Use when reviewing fiction writing quality, scoring a chapter, critiquing creative writing, or deciding if a chapter draft needs revision. Also triggers for beta reading or editorial feedback.
argument-hint: "[chapter text or file path]"
---

Evaluate a novel chapter's quality as a professional web novel editor.

## Input

From $ARGUMENTS or conversation:
- **Chapter text**: the full chapter to evaluate (or file path to read)
- **Chapter objective** (optional): what the chapter was supposed to achieve
- **Previous chapter summary** (optional): for continuity checking

## Evaluation Dimensions (6 dimensions, 0-10 each)

### 1. 情節推進 (Plot Progression)
- Does the chapter advance the story?
- Is there at least one meaningful event (not filler)?
- Does it set up future developments?
- **9-10**: Major plot advancement, satisfying revelations
- **7-8**: Clear forward momentum
- **5-6**: Story moves but slowly
- **3-4**: Mostly filler, little happens
- **1-2**: Nothing happens, could be deleted

### 2. 角色一致性 (Character Consistency)
- Do characters behave according to their established personality?
- Does dialogue match each character's voice?
- Are motivations clear and believable?
- **Special check**: Do all characters sound the same? If yes, max score 5.

### 3. 文筆品質 (Writing Quality)
- 長短句節奏: sentence rhythm variety?
- 描寫生動度: vivid sensory descriptions?
- 對話自然度: natural dialogue flow?
- 成語運用: appropriate (not excessive) use of idioms?
- **Special check**: 水字數 (word padding) — unnecessary repetition, meaningless exchanges? If found, deduct 2 points.

### 4. 節奏感 (Pacing)
- 張弛有度: tension-release balance?
- Not too rushed, not too dragging?
- **Special check**: Does the chapter end with a cliffhanger/hook? If not, deduct 1-2 points.

### 5. 目標吻合度 (Objective Alignment)
- Did the chapter achieve its stated objective?
- Were the key events included?
- Does the emotional tone match the plan?

### 6. 綜合評分 (Overall Score)
As a web novel reader: do you want to read the next chapter?

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
[通過 ✅ / 需改寫 ❌]（綜合 ≥ 7.0 通過）

### 具體問題
1. ...
2. ...

### 改寫建議
1. ...
2. ...

### 亮點
1. ...（也要指出做得好的地方）
```

## Evaluation Principles
- Be honest but constructive — harsh on problems, generous on strengths
- Give specific examples from the text, not vague criticism
- Prioritize issues by impact: plot holes > character inconsistency > prose style
- If overall score < 7.0, the rewrite suggestions MUST be specific enough to act on

## Story Log Entry

After evaluation, output a standardized log entry in this EXACT format (for the main agent to append to story_log.md):

```
## 第{N}章：{title}
- 摘要：{one-line summary, under 80 chars}
- 評分：{overall}/10
- 角色變化：{brief character changes}
- 伏筆進展：{planted/hinted/resolved}
- 情感基調：{tone}
```

No extra fields. No "關鍵意象". Keep it concise — this is an index, not a full record.
