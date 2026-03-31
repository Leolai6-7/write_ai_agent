---
name: novel-style-audit
description: Audit style consistency across multiple chapters of a novel. Use when checking for voice shifts, tone inconsistencies, dialogue out-of-character issues, or repetitive writing patterns across chapters. Also triggers when reviewing a batch of chapters for editorial quality.
argument-hint: "[chapter files or text to audit]"
---

Audit writing style consistency across multiple chapters.

## Input

From $ARGUMENTS or conversation:
- **Chapters to audit**: file paths, pasted text, or chapter range
- **Character voice references** (optional): established speaking styles
- **Target style** (optional): genre conventions to check against

## Audit Dimensions

### 1. Voice Shift (語氣偏移)
Does the narrator's voice stay consistent?
- Sudden shifts between formal/casual
- POV inconsistencies (third person slipping to first)
- Tense changes (past to present)

### 2. Tone Mismatch (基調不符)
Does each chapter's tone match its intended emotional arc?
- A "tense" chapter that reads as calm
- A "warm" chapter that's emotionally flat
- Abrupt mood swings without narrative justification

### 3. Dialogue OOC (角色脫線)
Do characters sound like themselves?
- Character A suddenly using Character B's speech patterns
- A quiet character becoming talkative without story reason
- All characters defaulting to the same neutral voice

### 4. Repetition (重複)
Across chapters:
- Same metaphors reused (每次都「心跳加速」)
- Identical sentence structures repeated
- Same opening patterns (every chapter starts with description)
- Catchphrase overuse

## Process

1. Read each chapter (or first 2000 chars if full text is too long)
2. Note style markers: sentence length distribution, vocabulary richness, dialogue-to-description ratio
3. Compare across chapters for consistency
4. Flag specific passages with issues

## Output Format

```markdown
## 文風審查報告

### 總覽
- 審查章節數：N
- 一致性評分：X/10
- 主要問題：[簡述]

### 問題清單
| # | 章節 | 類型 | 描述 | 建議修改 |
|---|------|------|------|---------|
| 1 | 第X章 | voice_shift | 第3段突然從第三人稱切換... | 改為... |
| 2 | 第Y章 | dialogue_ooc | 米娜的語氣過於隨意... | 恢復她的緩慢語速... |

### 正面觀察
- [做得好的地方，供後續章節參考]

### 風格指南建議
[基於審查結果，給出 2-3 條具體的寫作準則供後續章節遵循]
```

## Quality Criteria
- [ ] 每個問題都有具體的章節和段落引用
- [ ] 建議是可操作的（不是「寫好一點」而是「把這段的句子長度從平均20字縮短到12字」）
- [ ] 也指出做得好的地方（不只是挑毛病）
