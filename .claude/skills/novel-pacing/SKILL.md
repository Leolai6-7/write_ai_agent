---
name: novel-pacing
description: Analyze and advise on novel pacing and rhythm. Use when discussing chapter rhythm, story pacing problems, scene type distribution, narrative flow issues, or when planning the tempo of upcoming chapters.
argument-hint: "[recent chapters summary or chapter plan]"
---

Analyze pacing patterns and recommend rhythm adjustments for upcoming chapters.

## Input

From $ARGUMENTS or conversation:
- **Recent chapters**: summaries or emotional arcs of the last 5-10 chapters
- **Upcoming chapter objective** (optional): what's planned next
- **Genre conventions** (optional): expected pacing for this genre

## Analysis

### Step 1: Pattern Detection

Categorize each recent chapter by scene type:
- **Action** (動作): fights, chases, escapes
- **Dialogue** (對話): conversations, negotiations, reveals
- **Introspection** (內省): character reflection, emotional processing
- **Worldbuilding** (世界觀): exploration, lore dumps, travel
- **Romance** (感情): relationship development
- **Mystery** (懸疑): clue discovery, investigation

Map the pattern:
```
Ch1: Action → Ch2: Action → Ch3: Dialogue → Ch4: Action → Ch5: Action
Pattern: ACTION-HEAVY ⚠️
```

### Step 2: Problem Detection

Flag these issues:
- **3+ consecutive same-type** chapters → reader fatigue
- **No breather after climax** → emotional exhaustion
- **All slow chapters** → momentum lost
- **No tension for 5+ chapters** → reader drops off
- **Cliffhanger every chapter** → diminishing returns (need occasional soft landings)

### Step 3: Recommendation

For the next chapter, suggest:
- **Pace**: fast / medium / slow
- **Scene types**: recommended mix
- **Avoid**: what NOT to do this chapter
- **Length target**: shorter for fast pace, longer for slow
- **Emotional trajectory**: where to start and end emotionally

## Output Format

```markdown
## 節奏分析報告

### 近期節奏模式
| 章節 | 場景類型 | 情感強度 | 斷章類型 |
|------|---------|---------|---------|
| 第N章 | 動作 | 高 | 危機型 |
| ... | ... | ... | ... |

### 問題診斷
- ⚠️ [問題描述]

### 下一章建議
- **節奏**: [fast/medium/slow]
- **場景類型**: [建議組合]
- **避免**: [不要做的事]
- **字數目標**: [建議字數]
- **情感軌跡**: 從[起點]到[終點]

### 節奏處方
[1-2句具體的執行建議，如「用一段安靜的師徒對話開場，中段插入一個小衝突，結尾用懸念而非動作收尾」]
```
