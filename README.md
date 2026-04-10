# AI Novel Writing System

Multi-agent long-form novel generation system built as a [Claude Code Plugin](https://docs.anthropic.com/en/docs/claude-code). Uses **knowledge graphs** as external memory to maintain narrative consistency across chapters.

## Why Knowledge Graphs?

LLMs lose coherence in long-form generation — character states contradict, foreshadowing threads get dropped, causal chains break. This system solves that with a **feedback loop**:

```
Write chapter → Extract narrative diff → Update graph → Query graph → Write next chapter
                                ↑                              │
                                └──────────────────────────────┘
```

The graph isn't just a record — it actively shapes what the LLM sees next. Every chapter's context is assembled from structured graph queries, not raw file dumps.

## Architecture

```
write_ai_agent/                    ← Claude Code Plugin
├── agents/                        ← Sub-agents (tool-restricted)
│   ├── chapter-writer.md          → Read + Write
│   ├── progress-updater.md        → Read + Edit + Write
│   ├── volume-planner.md          → Read + Write + Glob
│   └── arc-reviewer.md            → Read + Edit + Write + Glob
├── skills/                        ← Workflow skills
│   ├── novel-writing/             → Entry point + pipeline
│   ├── novel-chapter/             → Writing philosophy
│   ├── novel-worldbuilding/       → World bible generation
│   ├── novel-characters/          → Character design
│   ├── novel-architect/           → Structure design
│   ├── novel-foreshadowing/       → Foreshadowing planning
│   └── novel-style-audit/         → Style consistency audit
└── scripts/                       ← Python tools
    ├── assemble_context.py        → 3-path context recall (structure + graph + semantic)
    ├── story_graph_nx.py          → NetworkX graph + query API
    ├── index_chapter.py           → Chapter → ChromaDB indexing
    └── semantic_search.py         → ChromaDB vector search
```

## Story Graph

The core innovation. A NetworkX directed graph with domain-specific node and edge types:

**Nodes:** chapters, characters, locations, events, foreshadowing threads, values, concepts, mirrors

**Edges:**
- `appears_in` — character ↔ chapter
- `located_in` — chapter → location
- `plants / hints / resolves` — chapter → foreshadowing thread
- `causes` — event → event (causal chains)
- `mirrors` — dual-narrative correspondence

Each chapter produces an incremental diff (YAML), applied to the graph without rebuilding:

```yaml
chapter: 6
characters_appeared:
  - name: 手談
    events: "在第七室擺出未完成的棋局"
foreshadowing_updates:
  - thread: ⑤最後一局的意義
    action: hint
causal_chains:
  - cause: 訪客推開棋院大門
    effect: 手談的等待循環被打破
```

## Context Assembly (3-Path Recall)

Before writing each chapter, `assemble_context.py` builds a context package via:

1. **Structured lookup** — Beat sheet tags → character profiles, location wiki articles, foreshadowing directives
2. **Graph traversal** — Causal chains, absent character detection, active foreshadow threads
3. **Semantic search** — ChromaDB vector similarity for thematic connections

Location references use **LLM Wiki** — individual markdown articles per location with fuzzy name matching, instead of dumping the entire world bible.

## Pipeline

```
Stage 1: Conception
  1.1 World Building → world_bible.md → Wiki articles
  1.2 Character Design → character_cast.md
  1.3 Structure → structure.md (volume-level arcs)
  1.4 Foreshadowing → foreshadowing.md

Stage 2: Creation (per arc)
  2.0a World Expansion (if needed)
  2.0b Arc Planning → arc_plan_N.yaml (chapter beat sheets)
  2.1 Chapter Loop:
      ① assemble_context.py → context package
      ② chapter-writer agent → chapter prose
      ③ progress-updater agent → story_log + graph diff
  2.9 Arc Review → update all design docs

Stage 3: Style Audit
Stage 4: Assembly → complete novel
```

Each agent has **restricted tool access** — chapter-writer can only Read + Write, progress-updater can Read + Edit + Write. No agent can do everything.

## Multi-Story Management

```
data/
├── active_story.txt
└── stories/{story-name}/
    ├── world/                 → Living docs (updated each arc)
    │   ├── _index.md          → Wiki index
    │   ├── world_bible.md     → Complete world bible
    │   ├── character_cast.md  → Design + current state
    │   ├── locations/         → Individual wiki articles
    │   ├── setting/           → Era, technology, culture
    │   └── history/           → Historical events
    ├── planning/              → Structure docs
    │   ├── story_brief.md
    │   ├── structure.md
    │   ├── foreshadowing.md
    │   └── arc_plan_N.yaml
    ├── runtime/               → Updated every chapter
    │   ├── story_log.md
    │   └── story_graph.json
    ├── outputs/
    │   └── chapter_NNN.md
    └── chroma/                → Per-story vector DB
```

## Quick Start

```bash
# Install as Claude Code plugin
claude plugins add /path/to/write_ai_agent

# Or from GitHub
claude plugins add https://github.com/Leolai6-7/write_ai_agent

# Start writing
claude
> /novel-writing 一個退休AI棋手在廢棄棋院等待最後對手的故事
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Claude Code Plugin |
| Sub-agents | chapter-writer, progress-updater, volume-planner, arc-reviewer |
| Knowledge Graph | NetworkX (directed graph, flat JSON persistence) |
| Semantic Search | ChromaDB + BAAI/bge-small-zh-v1.5 |
| Context Assembly | Python (3-path recall) |
| Output Language | 繁體中文 (Traditional Chinese) |

## vs Graphify

[Graphify](https://github.com/safishamsi/graphify) uses knowledge graphs to help LLMs **understand** existing codebases. This system uses knowledge graphs to help LLMs **generate** consistent long-form content. Same core insight (graph as LLM external memory), different problem:

| | This System | Graphify |
|---|---|---|
| Direction | Generate → build graph → inform next generation | Read existing → build graph → query |
| Domain | Narrative (characters, foreshadowing, causality) | Code (functions, imports, call graphs) |
| Update | Incremental per-chapter diffs | SHA256-based rebuild |
| Key challenge | Feedback loop (graph shapes output) | Extraction accuracy |

## License

MIT
