---
name: novel-style-audit
description: Audit style consistency across multiple chapters of a novel. Use when checking for voice shifts, tone inconsistencies, dialogue out-of-character issues, or repetitive writing patterns across chapters. Also triggers when reviewing a batch of chapters for editorial quality.
argument-hint: "[chapter files or text to audit]"
---

Audit writing style consistency across multiple chapters.

Review requests produce findings, not manuscript edits. Apply revisions only when requested; save a report only when a destination or report file is in scope.

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

1. Read the requested chapters in full when making a chapter-wide judgment. If sampling is necessary, identify the exact sampled passages (chapter + paragraph/line range or scene anchors), why they were selected, and what remains unread. The first 2000 characters are not a substitute for a full chapter.
2. Note relevant style markers, such as sentence rhythm, vocabulary, and dialogue-to-description balance. Treat these as qualitative observations unless actually measured; do not invent distributions or ratios.
3. Compare the passages actually read against the story's established voice and the scene's purpose. Distinguish intentional tonal changes or character growth from unsupported inconsistency.
4. For each finding, give the original passage's location, a short quote or precise description, its concrete effect on the reader, and an actionable revision. Do not prescribe arbitrary numerical targets for prose.
5. State the coverage limits of the conclusion. A sampled audit may report “no issue found in the passages read,” but must not declare unread passages or the whole chapter problem-free. Do not assign an X/10 score unless requested and supported by an explicit rubric and the stated reading coverage.

## Output Format

Scale the report to the evidence; omit empty sections rather than inventing findings or praise to fill the template.

```markdown
## 文風審查報告

### 總覽
- 審查範圍：[逐章列出全文，或具體抽樣段落／行號／場景]
- 未讀範圍與限制：[無，或未讀章節／段落及因此無法判定的事項]
- 主要問題：[簡述]

### 問題清單
| 原文位置 | 類型 | 原文／具體現象 | 具體影響 | 可執行建議 |
|----------|------|---------------|----------|------------|
| 第X章第3段 | voice_shift | [短引文：無提示切換敘述視角] | [使讀者誤認知覺主體] | [改回既定視角，或補上視角切換標記] |

### 正面觀察
- [附原文位置，說明有效之處，供後續章節參考]

### 風格指南建議
[按已讀證據提出需要的具體建議；不為湊數新增規則]
```

## Quality Criteria
- [ ] 明示實際閱讀與未讀範圍，抽樣結論不擴張成全章保證
- [ ] 每個問題都有具體的章節和段落引用
- [ ] 每個問題說明具體影響，建議可操作且符合該場景目的
- [ ] 無無根據的評分、統計或任意字數目標
- [ ] 正面觀察如有，附具體原文依據；沒有充分證據時省略，不為平衡語氣硬加稱讚
