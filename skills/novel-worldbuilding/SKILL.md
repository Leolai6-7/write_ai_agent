---
name: novel-worldbuilding
description: Expand a basic world premise into a complete world bible for fiction writing. Use when the user wants to create or expand world settings, design power systems, create locations, factions, or history for a novel. Also triggers when discussing worldbuilding, settings, or story universes.
argument-hint: "[world premise or genre]"
---

Expand a basic world premise into a comprehensive world bible. Read the story brief first to understand genre, tone, and scope.

## Input

From $ARGUMENTS or conversation, gather:
- **Story brief** (if available): determines genre, scale, and what the world needs to serve
- **Setting basics**: any starting details the user provides (even a single sentence is enough)
- **Story premise** (optional): helps connect world to plot

If the user gives minimal input, expand creatively. If they give detailed input, respect and build upon it.

## World Bible Philosophy

A world bible is a REFERENCE DOCUMENT for the writer, not a chapter of the novel. It should be:
- **Functional**: every element serves the story's conflicts and characters
- **Specific**: details concrete enough to influence character behavior and plot decisions
- **Internally consistent**: no contradictions in its own rules
- **Not exhaustive**: leave gaps for discovery during writing — the world should feel larger than what's documented

## Suggested Sections

These are starting points, not mandatory templates. Adapt based on what the story actually needs. A realistic thriller doesn't need a magic system section; a space opera doesn't need a "local customs" section.

### Locations
Create as many as the story needs. Each location should feel distinct — if you can swap two locations' descriptions and nothing changes, one of them shouldn't exist.

For each:
- Sensory identity (what you see, hear, smell — make it specific)
- Cultural character (what makes the people here different)
- Story function (why this place matters to the plot)

Think about diversity of function: safe haven, frontier, power center, forbidden zone, crossroads. Not every story needs all of these.

### History
Events that shaped the CURRENT world and connect to the story's conflicts. Not ancient irrelevant backstory — each event should have visible consequences in the present.

### Factions / Power Groups
Groups with CONFLICTING goals — their tensions drive story drama. The faction ecosystem should create a web of tension, not a simple binary opposition.

### Core System (if applicable)
If the world has a unique power/technology/rule system, describe it. If not, skip entirely. Don't force a system where the story doesn't need one.

When applicable, design with constraints:
- Source: where does power come from?
- Cost: what does using it cost? (the more powerful, the higher the cost)
- Limits: what CAN'T it do?
- Forbidden: what's taboo and why?

### Cultural Texture
The details that make a world feel lived-in: language, social structure, customs, economy. Focus on details that will actually affect how characters behave and interact.

## Output Format

Save the complete world bible to the path specified in the prompt (typically `{STORY_DIR}/world/world_bible.md`).

**The main agent will handle wiki splitting after you finish** — you don't need to create individual wiki files. Just produce one comprehensive world_bible.md with clear section headings for each location, setting, and history entry.

## Quality Self-Check

- [ ] No two locations feel interchangeable
- [ ] If a core system exists, it has clear costs that create dramatic tension
- [ ] Factions have conflicting goals
- [ ] History events connect to current story conflicts
- [ ] Cultural details are specific enough to influence character behavior
- [ ] Output language matches the story brief
- [ ] Each location has a clear heading (the main agent uses these for wiki splitting)
