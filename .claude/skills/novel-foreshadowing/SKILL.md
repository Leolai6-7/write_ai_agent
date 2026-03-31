---
name: novel-foreshadowing
description: Plan and manage foreshadowing for a novel. Design when to plant, hint, and resolve story threads across chapters. Use when discussing plot threads, story hooks, Chekhov's guns, mystery setups, foreshadowing, or when planning long-term plot elements.
argument-hint: "[story arcs or chapter range]"
---

Plan foreshadowing threads for a novel — when to plant seeds, drop hints, and deliver payoffs.

## Input

From $ARGUMENTS or conversation, gather:
- **Story arcs/chapters**: what arc or chapter range to plan foreshadowing for
- **Key plot points**: major events that need setup
- **Existing threads** (optional): unresolved threads from earlier chapters
- **Character cast** (optional): who's involved

## Foreshadowing Design Principles

Good foreshadowing follows the "3-beat rule":
1. **Plant** (埋): introduce the element naturally, readers barely notice
2. **Hint** (暗示): reference it again in a different context, readers start connecting
3. **Resolve** (收): pay it off — readers feel satisfied ("原來如此！")

### Types of Foreshadowing

- **Major (主線伏筆)**: spans 30+ chapters, connects to main conflict
- **Minor (支線伏筆)**: resolves within 5-15 chapters, enriches subplot
- **Red Herring (煙霧彈)**: deliberately misleads, revealed as misdirection

### Rules
- Every **major** foreshadow MUST have at least 2 hints before resolution
- **Minor** foreshadows need at least 1 hint
- Never let a planted thread go unresolved for more than 50 chapters without a hint
- Don't plant more than 2 new threads per chapter (reader overload)
- Resolution should feel inevitable in hindsight but surprising in the moment

## Output Format

### 伏筆規劃表

For each foreshadowing thread:

```
### [伏筆名稱]
- **類型**: major / minor / red_herring
- **描述**: 一句話說明這是什麼伏筆
- **相關角色**: 涉及的角色
- **埋設（第X章）**: 如何自然地植入（不能太刻意）
- **暗示（第Y、Z章）**: 如何在不同場景中呼應
- **收束（第W章）**: 如何揭曉，讀者會有什麼反應
- **與主線的關係**: 這條伏筆如何服務於主要故事衝突
```

### 章節伏筆指令表

For the planned chapter range, output a per-chapter directive:

```
| 章節 | 埋設 | 暗示 | 收束 |
|------|------|------|------|
| 第1章 | 神秘符文出現在牆上 | — | — |
| 第5章 | — | 角色B提到類似符文 | — |
| 第12章 | — | — | 揭露符文是XX的標記 |
```

## Quality Self-Check

- [ ] 每條主線伏筆至少有 2 次暗示
- [ ] 沒有超過 50 章未被暗示的伏筆
- [ ] 每章最多埋 2 條新伏筆
- [ ] 伏筆的植入方式自然，不刻意
- [ ] 收束時讀者會感到「原來如此」而非「什麼？」
- [ ] 至少有 1 條 red herring 增加懸疑感
