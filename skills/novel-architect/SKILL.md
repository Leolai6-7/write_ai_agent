---
name: novel-architect
description: Design the structural architecture of a novel - volume breakdown, story arcs, and chapter outlines. Use when planning a novel's structure, designing story arcs, breaking a story into volumes or chapters, or discussing plot architecture and pacing across a long-form narrative.
argument-hint: "[story premise and target scale]"
---

Design the structural architecture for a long-form novel.

## Input

From $ARGUMENTS or conversation, gather:
- **Story premise**: main goal/conflict (1-2 sentences)
- **Genre**: 奇幻、科幻、武俠、etc.
- **Scale**: target volumes (1-5) and chapters per volume (30-200)
- **Character cast** (optional): protagonist + key characters
- **World setting** (optional): key locations, power systems

---

## Core Philosophy (always apply)

### 1. Characters drive structure, not the other way around

Every protagonist must make at least one ACTIVE choice per arc — driven by internal desire, not external pressure. "Being forced to" is not a choice. "Choosing to despite the cost" is. If a protagonist spends an entire arc only reacting, the structure has failed.

### 2. Elements cast shadows before they arrive

Characters, organizations, technologies, locations, concepts — anything important should be felt before it's seen. Mentioned in passing dialogue, visible in the background, encountered through indirect effects. An element that appears fully formed with no prior shadow feels artificial.

Mark each major element's "first shadow" and "first full appearance" separately.

### 3. World-building serves story, never replaces it

Chapters that establish setting must still advance plot. World details are best revealed through character need, not narrator exposition. Pure "tour guide" chapters lose readers.

### 4. Rhythm is felt, not counted

Tension and release should alternate naturally based on the story's emotional logic. Sustained tension without relief exhausts the reader. Sustained calm without stakes bores them. The rhythm should feel like breathing — the story itself tells you when it needs a pause.

When designing multi-line narratives: each line must have its OWN momentum, not just serve as contrast. Both lines need active protagonists. The lines should create dramatic irony — the reader knows things from line A that make line B more tense.

---

## Process

### Step 1: Volume Architecture

Design each volume with:
- **卷名**: evocative title reflecting the volume's theme
- **主題**: one sentence — the emotional/narrative core
- **章節範圍**: start-end chapter numbers
- **核心情節轉折**: 3-5 major plot turns
- **主角成長**: how the protagonist transforms

### Step 2: Arc Decomposition

For each volume, break into 3-5 story arcs (弧線):
- **弧線名稱**
- **章節範圍**
- **核心衝突**: the central tension driving this arc
- **結尾轉折**: how it ends and hooks into the next

### Step 3: R/S Line Rhythm (for multi-line narratives)

If the story uses dual or multi-line narrative (e.g., R-line and S-line), define the line alternation pattern for each volume:

```
R/S 節奏：R-S-R-S-R-S-R-S-R-RS
```

This gives the volume-planner agent the constraint it needs to assign narrative lines to chapters.

**Note**: Chapter-level beat sheets are NOT generated here. They are created by the `volume-planner` agent just before each volume begins writing, using the volume arcs and current story state as input. This allows the beat sheet to adapt to actual story progression rather than being locked at planning time.

---

## Output Format

```markdown
# [小說標題] — 結構設計

## 分卷架構
### 第一卷：[卷名]（第1-N章）
- 主題：...
- 核心轉折：1. ... 2. ... 3. ...
- 主角成長：從A到B
- R/S 節奏：R-S-R-S-R-S-R-S-R-RS（if multi-line）

### 第二卷：[卷名]（第N+1-M章）
- 主題：...
（以此類推）

## 弧線分解
### 弧線一：[名稱]（第1-N章）
- 核心衝突：...
- 結尾轉折：...

### 弧線二：[名稱]（第N+1-M章）
- 核心衝突：...
- 結尾轉折：...
（以此類推）
```

**Note**: No chapter-level beat sheet here. Chapter beats are generated per-volume by the `volume-planner` agent.

## Quality Checklist
- [ ] Every protagonist makes active choices, not just reacts
- [ ] Important elements cast shadows before full appearance
- [ ] Each volume has a distinct theme
- [ ] Arcs have causal connections (not just chronological)
- [ ] Rhythm has natural variation
- [ ] Multi-line narratives each have independent momentum
