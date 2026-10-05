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
- **Scale**: the user's intended length, volume structure, and approximate chapter expectations; leave undecided boundaries flexible
- **Character cast** (optional): protagonist + key characters
- **World setting** (optional): key locations, power systems

---

## Core Philosophy (always apply)

### 1. Characters drive structure, not the other way around

Consequential choices should be understandable for this character: what they know or believe at that moment, what they want or feel, which alternatives are feasible and costly, and what makes the choice urgent now. Show why they accept an anticipated risk, not merely that they know it exists. Refusal, delay, impulse, mistaken judgment, and choices under pressure can all drive an arc; do not require optimal rationality or a fixed quota of active heroic acts.

Do not justify a choice with a revelation or actual consequence that comes after it. If its basis is missing, revisit the plan rather than require the writer to invent a guarantee; consult `docs/character-decisions.md` as needed for consequential-choice planning.

### 2. Elements cast shadows before they arrive

Characters, organizations, technologies, locations, concepts — anything important should be felt before it's seen. Mentioned in passing dialogue, visible in the background, encountered through indirect effects. An element that appears fully formed with no prior shadow feels artificial.

Mark each major element's "first shadow" and "first full appearance" separately.

### 3. World-building serves story, never replaces it

Chapters that establish setting must still advance plot. World details are best revealed through character need, not narrator exposition. Pure "tour guide" chapters lose readers.

### 4. Rhythm is felt, not counted

Tension and release should alternate naturally based on the story's emotional logic. Sustained tension without relief exhausts the reader. Sustained calm without stakes bores them. The rhythm should feel like breathing — the story itself tells you when it needs a pause.

When designing multi-line narratives: each line must have its OWN momentum, not just serve as contrast. Each line's character responses and constraints should sustain that momentum. The lines should create dramatic irony — the reader knows things from line A that make line B more tense.

---

## Process

### Step 1: Volume Architecture

Design each volume with:
- **卷名**: evocative title reflecting the volume's theme
- **主題**: one sentence — the emotional/narrative core
- **大致規模**: approximate chapter count (e.g., 「約 10-15 章」), NOT exact ranges
- **核心情節轉折**: 3-5 major plot turns
- **主角成長**: how the protagonist transforms

Volume size is FLEXIBLE. A volume ends when its thematic arc completes, not at a predetermined chapter count. The actual boundary is decided during arc review.

### Step 2: Arc Decomposition

Divide each volume into as many story arcs (弧線) as its progression needs, without a fixed quota. Only the NEXT arc needs detail; later arcs are sketches:
- **弧線名稱**
- **大致規模**: approximate chapters (e.g., 「約 3-5 章」)
- **核心衝突**: the central tension driving this arc
- **結尾轉折**: how it ends and hooks into the next

Later arcs in later volumes should be LESS detailed — just the core conflict and a sentence on the turning point. They will be refined when their turn comes (progressive planning).

### Step 3: Narrative Lines (when applicable)

Use the story's established line names. A single-line story can use `main`; existing names such as R/S remain valid. For multi-line stories, describe what each line contributes and where switching or convergence would help:

- e.g., stay with 調查線 through a discovery, then switch to 家族線 when the contrast or withheld information matters.

These are planning intentions, not a compulsory alternating sequence. The volume-planner assigns lines for the current arc as pacing and actual story progression require.

**Note**: Chapter-level beat sheets are NOT generated here. They are created by the `volume-planner` agent just before each arc begins writing, using the volume architecture and current story state as input. This allows the beat sheet to adapt to actual story progression rather than being locked at planning time.

---

## Output Format

```markdown
# [小說標題] — 結構設計

## 分卷架構
### 第一卷：[卷名]
- 主題：...
- 大致規模：約 10-15 章
- 核心轉折：1. ... 2. ... 3. ...
- 主角成長：從A到B

### 第二卷：[卷名]
- 主題：...
- 大致規模：約 10-12 章
（以此類推，越後面越簡略）

## 弧線分解
### 弧線一：[名稱]（約 3-5 章）
- 核心衝突：...
- 結尾轉折：...

### 弧線二：[名稱]（約 3-5 章）
- 核心衝突：...
- 結尾轉折：...
（後續弧線只需一句核心衝突）
```

**Note**: No chapter-level beat sheet here. Chapter beats are generated per-arc by the `volume-planner` agent. Volume boundaries are approximate and confirmed during arc review.

## Quality Checklist
- [ ] Major choices follow from character-specific knowledge/beliefs, priorities or emotion, feasible alternatives and costs, and a timely trigger; anticipated risk is not confused with later outcomes
- [ ] Important elements cast shadows before full appearance
- [ ] Each volume has a distinct theme
- [ ] Arcs have causal connections (not just chronological)
- [ ] Rhythm has natural variation
- [ ] Multi-line narratives each have independent momentum
