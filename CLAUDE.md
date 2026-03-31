# AI 小說寫作系統 (write_ai_agent)

## 專案概述
一個基於 LangGraph + AWS Bedrock 的多 Agent 長篇小說自動生成系統。支援 300+ 章的分卷式網路小說創作。

## 技術棧
- **Agent 框架**: LangGraph (StateGraph)
- **LLM**: AWS Bedrock (Claude Sonnet/Haiku), 支援 OpenAI 和 Anthropic 直連
- **記憶**: SQLite + ChromaDB (4 層記憶 + 語義檢索)
- **結構化輸出**: Pydantic + JSON mode
- **CLI**: Typer + Rich

## 小說寫作 Skills（快速驗證用）

完整工作流入口：`/novel-writing`

| Skill | 用途 |
|-------|------|
| `/novel-worldbuilding` | 世界觀構建 |
| `/novel-characters` | 角色群像設計 |
| `/novel-architect` | 分卷/弧線結構 |
| `/novel-foreshadowing` | 伏筆規劃 |
| `/novel-pacing` | 節奏分析 |
| `/novel-chapter` | 章節生成 |
| `/novel-judge` | 品質評審 |
| `/novel-rewrite` | 章節改寫 |
| `/novel-style-audit` | 文風審查 |

## 檔案結構

```
config/          — Pydantic models + settings
agents/          — 16 個 Agent（BaseAgent 繼承）
prompts/         — YAML prompt templates（agent 系統用）
memory/          — MemoryManager + 7 個 Repository
pipeline/        — LangGraph graph + 9 個 Node + Orchestrator
infrastructure/  — LLM Client (3 providers) + DB + Logger + Errors
.claude/skills/  — 9 個 Skills（快速驗證用）
data/            — 運行時資料（DB、向量、輸出、規劃）
tests/           — 45 tests
```

## 開發須知

- **測試**: `uv run pytest tests/ -v`
- **AWS 認證過期**: 用 `/refresh-aws` 刷新
- **Prompt 迭代**: 先改 `.claude/skills/*/SKILL.md` 驗證，確認後同步到 `prompts/*.yaml`
- **新增 Agent**: 建 `agents/xxx.py` + `prompts/xxx.yaml` + `pipeline/nodes/xxx.py`，在 orchestrator 的 nodes dict 加一行

## 當前進度的載入

每次開始新對話時，如果要繼續寫小說，請先檢查：
1. `data/planning/story_log.md` — 上次寫到哪裡
2. `data/planning/structure.md` — 整體結構規劃
3. `data/planning/foreshadowing.md` — 伏筆追蹤表
4. `data/world/world_bible.md` — 世界聖經
5. `data/world/character_cast.md` — 角色群像
6. `data/outputs/` — 已生成的章節

如果這些檔案存在，讀取它們以恢復上下文。如果不存在，從 `/novel-writing` 開始。
