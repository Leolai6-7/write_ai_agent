# AI Novel Writing System

Long-form novel writing with a shared local Python core, a Codex skill, and a Claude Code plugin. Uses **knowledge graphs** and source-bound chapter receipts to support narrative consistency across chapters.

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
write_ai_agent/                    ← Shared core + platform entrypoints
├── codex-skills/novel-writing/    ← Codex entry (no Claude hooks required)
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
    ├── update_graph.py            → Validate/apply chapter diffs + completion receipt
    ├── chapter_workflow.py        → Required-step receipts + optional index status
    ├── story_snapshot.py          → Read-once source view + freshness checks
    ├── index_chapter.py           → Chapter summary → optional ChromaDB indexing
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

Each chapter produces a diff (YAML). `update_graph.py` validates it and replays the stored chapter history, so retrying a chapter does not duplicate its events and replacing a tracked diff has a reproducible result:

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
    cause_ch: 6
    effect: 手談的等待循環被打破
    effect_ch: 6
```

## Context Assembly (3-Path Recall)

Before writing each chapter, `assemble_context.py` builds a context package via:

1. **Structured lookup** — Beat sheet tags → character profiles, location wiki articles, foreshadowing directives
2. **Graph traversal** — Chapter-bounded causal chains, absent characters, and active foreshadow threads; tracked diffs permit historical replay
3. **Selected memory recall (optional)** — Chroma baseline in `off`/`shadow`, or Jev-Mem in `active`; bounded evidence with chapter IDs and source paths

The writer package separates author intent, recorded canon, explicit POV knowledge/belief, continuity and design references. Optional `narrative_updates` in each chapter diff bind facts and character-specific knowledge/beliefs to actual manuscript lines. Unknown POV/knowledge stays unknown; current character profiles are design references, not a substitute for chapter-bounded knowledge. Latest retired/stale states never revert to older beliefs.

For consequential character choices, optional beat `decision_points` carries the character's basis, alternatives and expected costs as required author intent. Decision clues can share the existing bounded recall query; older beats retain their previous query. Planning, writing and review check why a character accepts a risk, while allowing coherent mistakes and impulse. See [Character decisions](docs/character-decisions.md) and the [scoped scene exercise](examples/decision-causality/review.md).

New foreshadow plans use a stable `thread_id`, optional display name and explicit `plant`/`hint`/`resolve` action. The graph diff keeps its existing `thread` string key; legacy stories are not renumbered. Revision handoffs carry existing IDs and the previous chapter diff so the replacement describes the complete revised chapter, not only the edited passage.

`ContextBundle` selects whole blocks under an exact 12,000-character default for the rendered package (not a token or whole-JSON limit). Required boundaries/current beat/targeted threads must fit or assembly fails without a new receipt. Valid POV records are high-priority candidates, newer first, rather than an unbounded mandatory lifetime history. Other blocks are ranked and omissions reported without leaking their prose into JSON. Recalled and recent log entries are deduplicated. Graph references point to isolated baseline/prior-diff items, never the entire current history; tracked stale chapter contributions are withheld. Use `--max-context-chars` or per-story `planning/context_policy.json`; chapter word-length targets come from the beat or story brief. See [Narrative context](docs/narrative-context.md) for the optional schema and examples.

Location references use **LLM Wiki** — individual markdown articles per location with fuzzy name matching, instead of dumping the entire world bible.

Recent logs and same-line endings are also restricted to earlier chapters; YAML arc plans and legacy Markdown plans are supported. When an older cumulative graph has no snapshot for a requested chapter, the package reports that limitation and uses the available earlier logs and text. Tracked chapters awaiting review are not injected as valid history. Missing semantic dependencies or a missing local model appear as a recall status in the package.

Semantic candidates must match a unique current log summary and a successful index receipt with current chapter/log hashes. Stale or unreceipted legacy entries are omitted with a `needs_reindex` status when none remain; reindex the affected chapter explicitly after resolving its source or log changes.

Jev-Mem already includes candidate search and controlled graph traversal. `active` therefore skips Chroma queries and new background indexing; `shadow` keeps only baseline evidence in writer input. Errors never silently enable the other backend. The canonical story graph and structured sources remain available in every mode. Configure a story's `planning/memory_config.json` as described in [Memory workflow](docs/memory-workflow.md).

## Pipeline

```
Stage 1: Conception
  1.1 World Building → world_bible.md → Wiki articles
  1.2 Character Design → character_cast.md
  1.3 Structure → structure.md (volume-level arcs)
  1.4 Foreshadowing → foreshadowing.md

Stage 2: Creation (per arc)
  2.0a World Expansion (if needed)
  2.0b Arc Planning → arc_synopsis_N.md + arc_plan_N.yaml (arc overview + chapter beats)
  2.1 Chapter Loop:
      ① assemble_context.py → context package
      ② chapter-writer agent → draft + lightweight edit → final prose
      ③ progress-updater agent → story_log + graph diff
        → main agent runs update_graph.py → completion receipt
        → background optional indexing (separate status)
  2.9 Arc Review → review or authorized edits to affected design docs

Stage 3: Style Audit
Stage 4: Assembly → complete novel
```

The Claude plugin declares tool-restricted agents. The Codex skill uses available delegation or sequential roles; both retain the same required artifacts and completion gate.

Writing techniques are choices guided by genre and user intent, not fixed scene or suspense formulas. The writer reads the complete draft once for motivation, pacing and readability before the progress update; independent review is used when warranted, not required for every chapter. See the [chapter writing guidelines](skills/novel-chapter/SKILL.md). A sampled style review reports its actual coverage rather than assigning a whole-book score. Authorized setting revisions replace affected definitions and record the change in the arc review; setting edits alone do not automatically mark chapters `needs_review`.

The main agent checks `chapter_workflow.py status --story-dir {STORY_DIR} --chapter-num {N}` before advancing. A chapter is complete when context assembly, chapter text, its log entry, and the applied graph diff have valid receipts. Editing only the log leaves the graph update pending. Indexing has its own status and does not block completion.

Previously completed chapters with unchanged local artifacts become `needs_review` when earlier sources change. They remain ineligible for memory recall until reviewed, but do not block the Stop check like active `writing` work. Review is explicit and records a reason against the current evidence; it cannot approve changed chapter/log/diff content. Tracked graph snapshots are checked against baseline + diffs before use, so manual snapshot corrections cannot be silently overwritten by replay.

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
    │   ├── story_graph.json
    │   └── chapter_workflow.json
    ├── outputs/
    │   └── chapter_NNN.md
    └── chroma/                → Per-story vector DB
```

## Quick Start

### Codex

Use [the Codex novel-writing skill](codex-skills/novel-writing/SKILL.md) with this checkout. The local personal skill entry is a symlink to that directory; no duplicate source or extra model SDK is needed. Invoke `$novel-writing` and name the story and task, for example: `繼續指定故事的第 3 章，先檢查前情與章節狀態`.

The skill checks the repository and story before writing, reuses the Python CLI, and reads stage-specific writing references as needed. It does not install Claude hooks, ingest all novels, or automatically sync Jev memory. Its standard `SKILL.md` entry follows [OpenAI's skill format](https://learn.chatgpt.com/docs/build-skills); the linked checkout must remain available.

### Claude Code

```bash
# From the repository root: install the core Python tools
uv sync

# Install as Claude Code plugin
claude plugins add /path/to/write_ai_agent

# Or from GitHub
claude plugins add https://github.com/Leolai6-7/write_ai_agent

# Start writing
claude
> /novel-writing 一個退休AI棋手在廢棄棋院等待最後對手的故事
```

The core workflow runs without a vector database. To enable semantic indexing, install `uv sync --extra semantic`. The embedding model is loaded from the local cache by default. For an explicit first download, run:

```bash
.venv/bin/python scripts/index_chapter.py \
  --story-dir data/stories/{story-name} --chapter-num 1 \
  --chapter-file data/stories/{story-name}/outputs/chapter_001.md \
  --allow-model-download
```

Run offline tests with `uv sync --extra dev` followed by `.venv/bin/python -m pytest tests/ -v`. Real model-backed retrieval tests require the semantic extra, a cached model, and `NOVEL_TEST_SEMANTIC=1`.

`memory/memory_manager.py` retains the older SQLite-based four-layer memory API for compatibility and its existing tests. The active plugin pipeline uses `assemble_context.py`, `story_graph.json`, and chapter receipts. See [Memory and chapter workflow](docs/memory-workflow.md) for recovery and the optional Jev-Mem integration.

For a read-only audit of fictional source-to-record coverage, run `.venv/bin/python -m scripts.benchmark_memory`. The [memory evaluation guide](docs/memory-evaluation.md) also documents an explicit opt-in, equal-input Chroma/Jev comparison; offline checks do not establish retrieval or writing-quality gains.

For repeated Jev queries, an explicit `JevWorkerSession` reuses the isolated interpreter and encoder while reloading a fresh graph for each query; see [session usage](docs/memory-workflow.md#同一次工作內連續查詢). The evaluation CLI accepts `--jev-worker session` to measure first-query cold startup separately from subsequent warm queries. No background daemon or default backend switch is introduced.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Local Python core; Codex skill / Claude Code plugin |
| Sub-agents | chapter-writer, progress-updater, volume-planner, arc-reviewer |
| Knowledge Graph | NetworkX (directed multigraph, flat JSON + chapter history) |
| Semantic Search | Optional ChromaDB + locally cached BAAI/bge-small-zh-v1.5 |
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
