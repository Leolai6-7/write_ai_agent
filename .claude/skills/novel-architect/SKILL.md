---
name: novel-architect
description: Design the structural architecture of a novel - volume breakdown, story arcs, and chapter outlines. Use when planning a novel's structure, designing story arcs, breaking a story into volumes or chapters, or discussing plot architecture and pacing across a long-form narrative.
argument-hint: "[story premise and target scale]"
---

Design the structural architecture for a long-form novel (100+ chapters).

## Input

From $ARGUMENTS or conversation, gather:
- **Story premise**: main goal/conflict (1-2 sentences)
- **Genre**: 奇幻、科幻、武俠、etc.
- **Scale**: target volumes (1-5) and chapters per volume (30-200)
- **Character cast** (optional): protagonist + key characters
- **World setting** (optional): key locations, power systems

## Process

### Step 1: Volume Architecture

Design each volume with:
- **卷名**: evocative title reflecting the volume's theme
- **主題**: one sentence capturing the emotional/narrative core
- **章節範圍**: start-end chapter numbers
- **核心情節轉折**: 3-5 major plot turns that define this volume
- **主角成長**: how the protagonist transforms in this volume

Volume design principles:
- Volume 1: establish world, characters, stakes. End with a revelation that reframes everything
- Middle volumes: escalate stakes, deepen relationships, introduce moral complexity
- Final volume: convergence of all threads, climax, resolution

### Step 2: Arc Decomposition

For each volume, break into 3-5 **story arcs** (弧線), each 20-40 chapters:

For each arc:
- **弧線名稱**
- **章節範圍**
- **核心衝突**: the central tension driving this arc
- **結尾轉折**: how this arc ends and hooks into the next

Arc pacing pattern:
```
Arc 1: Setup → Rising tension → First major confrontation
Arc 2: Aftermath → New challenges → Deepening relationships
Arc 3: Crisis → All seems lost → Unexpected ally/revelation
Arc 4: Final push → Climax → Volume resolution + cliffhanger
```

### Step 3: Chapter Beat Sheet (optional, for first arc)

If the user wants more detail, outline the first arc's chapters:
- Chapter title + one-line objective
- Key events (2-3 per chapter)
- Emotional tone (緊張/溫馨/悲壯/輕鬆/etc.)

Rhythm rules:
- No more than 3 consecutive chapters of the same tone
- Every 5-7 chapters needs a "breather" after tension
- End every chapter with a hook (question, threat, revelation)

## Output Format

```markdown
# [小說標題] — 結構設計

## 分卷架構
### 第一卷：[卷名]
- 主題：...
- 章節：第1-120章
- 核心轉折：
  1. ...
  2. ...
- 主角成長：從A到B

## 弧線分解（第一卷）
### 弧線一：[名稱]（第1-30章）
- 核心衝突：...
- 結尾轉折：...

## 章節節拍（弧線一，可選）
| 章 | 標題 | 線 | 目標 | 角色 | 地點 | 伏筆 | 概念 | 情感 |
|----|------|----|------|------|------|------|------|------|
| 1  | ... | R | ... | 沈逸,林昭明 | 深潛研究所 | ⑨觀察者效應 | 模擬啟動 | 期待 |
```

The beat sheet columns serve as a pre-built retrieval index:
- **角色**: which character profiles to retrieve from character_cast
- **地點**: which location descriptions to retrieve from world_bible
- **伏筆**: which foreshadowing threads to retrieve (plant/hint/resolve)
- **概念**: key concepts/technologies that need world_bible context

These tags are the KEYS for the RAG system. When the context assembler
queries "what does chapter 15 need?", it looks up row 15 in this table
and immediately knows which sections to retrieve — no inference needed.

## Structural Philosophy

### On Protagonist Agency
- Every protagonist must make at least one ACTIVE choice per arc — something driven by internal desire, not external pressure
- "Being forced to" is not a choice. "Choosing to despite the cost" is.
- If a protagonist spends an entire arc only reacting, the structure has failed

### On Multi-Line Narratives
- If the story has dual/multiple narrative lines, each line must have its OWN momentum — not just serve as contrast to the other
- Both lines need active protagonists who drive events, not just one active + one passive
- The lines should create dramatic irony: the reader knows things from line A that make line B more tense, and vice versa

### On Introducing Story Elements
This applies to characters, organizations, technologies, locations, and concepts equally:
- Important elements should cast a SHADOW before they appear — mentioned in dialogue, visible in the background, felt through indirect effects
- Mark each major element's "first shadow" and "first full appearance" chapter separately
- Example: before an organization becomes a plot force, characters should argue about it in passing; before a technology drives a scene, a character should encounter its everyday consequences
- An element that appears fully formed with no setup feels artificial

### On World-Building Chapters
- Chapters that establish setting/world should still advance plot. Pure "tour guide" chapters lose readers.
- World details are best revealed through character need, not narrator exposition

## Quality Criteria
- [ ] 每卷有明確且不同的主題
- [ ] 弧線之間有因果關係
- [ ] 章節節奏有起伏，不單調
- [ ] 主角在每卷有可見的成長變化
- [ ] 每條敘事線的主角都有主動行為推進
- [ ] 重要角色在正式登場前已被提及或側寫
