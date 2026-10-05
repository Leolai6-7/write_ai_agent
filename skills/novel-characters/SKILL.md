---
name: novel-characters
description: Design protagonists and supporting characters for a novel. Use when the user wants to create character profiles, design character arcs, or build a character relationship map for fiction writing.
argument-hint: "[story premise]"
---

Design the requested characters for a novel. Read the story brief first to understand the story's needs. When building the cast, include a heading-searchable profile for each protagonist as well as supporting characters; preserve agreed protagonist designs and fill only relevant gaps. A request to update one character does not require rebuilding the cast.

## Input
- **Story brief** (if available): determines genre, tone, what roles the cast needs to fill
- **Protagonist**: name, personality, goal
- **World setting**: enough to ground the characters in a specific world
- **Story premise**: what conflict drives the story

## Philosophy

Characters exist to create friction, support, and revelation around the protagonist. The cast should be designed to serve the story's specific needs — not from a template of "mentor + rival + love interest."

Ask: what relationships and conflicts does THIS story need? Then design the people who embody them.

## Process

### Step 1: Analyze Story Needs
Based on the premise, identify what FUNCTIONS the cast needs to serve:
- Who challenges the protagonist's worldview?
- Who represents what the protagonist is afraid of becoming?
- Who holds information the protagonist needs?
- Who creates emotional stakes?
- Whose goals directly conflict with the protagonist's?

Don't start from role labels. Start from story needs.

### Step 2: Design Each Character

For each character, create TWO sections:

#### 設計（static — set at creation, rarely changes）

**Identity**: Name, age, background — grounded in the world setting

**Depth**:
- Core motivation (what they WANT — must be understandable, even if wrong)
- For important characters, show conflicting priorities and a blind spot: what they protect first under pressure, what they may sacrifice, and what they misread or avoid acknowledging. These should explain different choices in different relationships and situations, not give every character the same flaw or a fixed decision formula.
- Secret/hidden dimension (what readers discover later)
- Fatal flaw (what causes their biggest mistake)
- Speaking style — for important recurring characters, describe usable tendencies in vocabulary, rhythm, and responses to different people or pressures. Voices may overlap naturally; do not force a unique catchphrase for every person.

**Arc**: Where they start → what changes them → where they end up

#### 當前狀態（evolving — updated during authorized arc maintenance）

Initialize as empty at creation. After each arc, authorized maintenance updates the relevant fields from verified prose:
- **位置**：current physical location
- **情感狀態**：emotional state
- **關鍵認知**：what they currently know
- **關係變化**：how relationships have shifted
- **最近行動**：most significant recent action

Example:
```markdown
### 當前狀態
- 位置：（故事開始後更新）
- 情感狀態：（故事開始後更新）
- 關鍵認知：（故事開始後更新）
- 關係變化：（故事開始後更新）
- 最近行動：（故事開始後更新）
```

### Step 3: Relationship Map
Show how characters relate to EACH OTHER, not just to the protagonist:
- Alliances and tensions
- Hidden agendas
- How relationships will evolve

### Step 4: Dialogue Voice Test (optional)
When useful, try a brief response to the same story-relevant scenario for important recurring characters. Minor characters do not need a separate voice exercise.

Look for differences in what they notice, want, avoid, and say. Shared language within a family or workplace can be intentional; judge the voice with its relationship and scene context, not solely by whether a nameless line is instantly identifiable.

## Naming and Searchability

The character file is read by an automated context assembly system that uses Grep to find character profiles. To ensure characters can be found:

- **Heading format**: `## 角色N：{name}` or `## 配角：{name}` — the heading MUST contain the name used in the beat sheet
- **Aliases**: If a character has multiple names (e.g., real name + code name), include all names in the heading: `## 角色N：{name_A} / {name_B}`
- **Every character in the beat sheet gets a profile** — even minor characters. A minor character's profile can be short (gender, role, speaking style — 3-5 lines), but it must exist as its own `## ` section
- **Gender must be explicit** in 基本資料

## Quality Criteria
- Important recurring characters have usable voice tendencies, with contextual overlap where appropriate
- Every character has a clear, understandable motivation
- Important characters' priorities, emotional pressures, and blind spots explain consequential choices, including mistakes or refusal, without assuming they know future revelations or outcomes
- Relationship map contains genuine conflict/tension
- Similar narrative functions are distinguished where the story needs them, rather than forcing every role to be unique
- Speaking styles can be maintained over the story's intended length without becoming repetitive mannerisms
- Every character in the beat sheet has a heading-searchable profile
