---
name: novel-worldbuilding
description: Expand a basic world premise into a complete world bible for fiction writing. Use when the user wants to create or expand world settings, design magic systems, create locations, factions, or history for a novel. Also triggers when discussing worldbuilding, fantasy settings, or story universes.
argument-hint: "[world premise or genre]"
---

Expand a basic world premise into a comprehensive world bible. The user provides a starting point (genre, setting basics, magic system sketch), and you build it into a rich, internally consistent world.

## Input

From $ARGUMENTS or conversation, gather:
- **Genre**: 奇幻、科幻、武俠、都市、etc.
- **Setting basics**: continent name, era, key locations (even just 2-3 names)
- **Magic/power system sketch**: even a single sentence like "魔力來自靈脈" is enough
- **Story premise** (optional): helps connect world to plot

If the user gives minimal input, that's fine — expand creatively. If they give detailed input, respect and build upon it.

## World Bible Structure

Generate all sections below. Output in **繁體中文**.

### 1. 地點（5-8 個）

Each location must feel distinct — not "another fantasy village." Think about what makes each place UNIQUE:

For each location:
- **名稱**：evocative name fitting the world's culture
- **環境描寫**：2-3 sentences of sensory detail (what you see, hear, smell)
- **文化特色**：what makes the people here different (customs, values, economy)
- **故事意義**：why this place matters to the plot

Diversity checklist — locations should span:
- A safe haven (home base)
- A dangerous frontier
- A center of power/knowledge
- A mysterious/forbidden place
- A crossroads/trading hub

### 2. 歷史大事記（3-5 件）

Events that shaped the CURRENT world and connect to the story's conflicts. Not ancient irrelevant history — each event should have visible consequences in the present.

For each event:
- **名稱**
- **時代**
- **經過**：what happened (2-3 sentences)
- **影響**：how it affects the current story

### 3. 勢力/陣營（2-4 個）

Factions with CONFLICTING goals — their tensions drive story drama.

For each faction:
- **名稱**
- **領導者**：name + brief character (1 sentence)
- **目標**：what they want (must conflict with at least one other faction)
- **對主角的態度**：ally / enemy / neutral / complicated
- **資源/優勢**：what gives them power

The faction ecosystem must create a web of tension, not a simple good-vs-evil binary.

### 4. 魔法/力量體系

This is where most worldbuilding fails — overpowered systems with no cost. Design with constraints:

- **來源**：where does power come from?
- **分類**：schools/types (3-5 types)
- **代價**：what does using magic COST? (physical toll, moral cost, resource depletion)
- **限制**：what CAN'T magic do? (at least 3 hard limits)
- **等級體系**：ranking system (4-6 tiers with names)
- **禁忌**：what's forbidden and why?

Rule of thumb: the more powerful the magic, the higher the cost. No free power.

### 5. 文化細節

The texture that makes a world feel lived-in:
- **語言/方言**：any linguistic differences between regions?
- **社會結構**：who's on top? Who's oppressed?
- **風俗習慣**：unique customs (greetings, festivals, taboos)
- **經濟**：what do people trade? What's valuable?

## Quality Self-Check

Before outputting, verify:
- [ ] No two locations feel interchangeable
- [ ] Magic has clear costs that create dramatic tension
- [ ] Factions have conflicting goals (not just "good guys vs bad guys")
- [ ] History events connect to current story conflicts
- [ ] Cultural details are specific enough to influence character behavior
