# AI Novel Writer v2.0

Multi-agent novel writing pipeline powered by LangGraph, AWS Bedrock, and structured memory.

## Architecture

```
VolumeArchitect → ArcPlanner → ChapterPlanner
                                      │
                        ┌─────────────┘
                        ▼
              ┌── ChapterGenerator ──┐
              │         │            │
              │    JudgeAgent        │
              │    (score < 7?)      │
              │     │       │        │
              │    YES     NO        │
              │     │       │        │
              │  RewriteAgent  ConsistencyChecker
              │     │              │
              │     └──→ Judge ←───┘
              │                    │
              │              SummarizerAgent
              │                    │
              └── MemoryManager ←──┘
                  (SQLite + ChromaDB)
```

**9 Agents** | **LangGraph pipeline** | **4-layer memory** | **30 tests**

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM Provider | AWS Bedrock (Claude Sonnet / Haiku) |
| Agent Framework | LangGraph (StateGraph) |
| Structured Output | Pydantic + JSON mode |
| Memory Storage | SQLite + ChromaDB |
| CLI | Typer + Rich |

## Quick Start

```bash
# Install
uv pip install -e ".[dev]"

# Configure AWS credentials
aws configure  # or set AWS_PROFILE

# Generate a novel
python main.py generate

# Generate a single chapter (test)
python main.py chapter 1 --title "初入圖書館" --objective "主角到達圖書館"

# Check progress
python main.py status
```

## Project Structure

```
write_ai_agent/
├── main.py                  # CLI entry point
├── config/
│   ├── models.py            # Pydantic data models (13 models)
│   └── settings.py          # NovelConfig
├── agents/
│   ├── base_agent.py        # Base class with LLM abstraction
│   ├── volume_architect.py  # Novel structure design
│   ├── arc_planner.py       # Story arc planning
│   ├── chapter_planner.py   # Chapter objectives
│   ├── chapter_generator.py # Content generation
│   ├── judge_agent.py       # LLM-as-Judge (6 dimensions)
│   ├── rewrite_agent.py     # Targeted rewriting
│   ├── summarizer.py        # Structured summarization
│   └── consistency_checker.py # Cross-chapter consistency
├── memory/
│   ├── memory_manager.py    # 4-layer memory + token budget
│   ├── retrieval.py         # ChromaDB semantic search
│   └── token_budget.py      # Context window management
├── pipeline/
│   ├── chapter_graph.py     # LangGraph StateGraph
│   └── orchestrator.py      # Volume/arc/chapter orchestration
├── infrastructure/
│   ├── llm_client.py        # Multi-model client (Bedrock/OpenAI/Anthropic)
│   ├── db.py                # SQLite schema
│   └── logger.py            # Structured logging
└── tests/                   # 30 tests
```

## Memory Architecture

| Layer | Purpose | Storage |
|-------|---------|---------|
| Short-term | Last 5 chapter summaries | SQLite |
| Long-term | Compressed every 10 chapters | SQLite |
| Character | Per-character state tracking | SQLite |
| Semantic | Relevant memory retrieval | ChromaDB |

Token budget control ensures context never exceeds model limits.

## Model Configuration

Default: all agents use AWS Bedrock. Override in environment or config:

```bash
# Use specific AWS profile/region
AWS_PROFILE=my-profile AWS_REGION=us-east-1 python main.py generate

# Mix with OpenAI (optional)
OPENAI_API_KEY=sk-... python main.py generate
```

Model routing:
- `bedrock:...` → AWS Bedrock Converse API
- `claude-...` + Anthropic key → Anthropic direct
- `gpt-...` + OpenAI key → OpenAI

## License

MIT
