# AI 小說寫作系統 (write_ai_agent)

## 專案概述
一個基於 LangGraph + AWS Bedrock 的多 Agent 長篇小說自動生成系統。支援多故事管理和 300+ 章的分卷式小說創作。

## 技術棧
- **Agent 框架**: LangGraph (StateGraph)
- **LLM**: AWS Bedrock (Claude Sonnet/Haiku), 支援 OpenAI 和 Anthropic 直連
- **記憶**: SQLite + ChromaDB (4 層記憶 + 語義檢索)
- **結構化輸出**: Pydantic + JSON mode
- **CLI**: Typer + Rich

## 小說寫作 Skills

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

## 多故事管理

每個故事有獨立的子目錄。`data/active_story.txt` 記錄當前正在寫的故事。

```
data/
├── active_story.txt              → 當前故事名稱
└── stories/
    ├── star-ring-tower/          # 星環之塔（奇幻冒險）
    │   ├── world/
    │   ├── planning/
    │   └── outputs/
    └── civilization-disease/     # 文明病（哲思科幻）
        ├── world/
        │   └── world_bible.md
        ├── planning/
        │   ├── story_brief.md
        │   ├── structure.md
        │   ├── foreshadowing.md
        │   └── story_log.md
        └── outputs/
            ├── chapter_001.md
            └── novel_complete.md
```

## 路徑規則

所有 sub-agent 的檔案路徑必須使用 active story 的目錄：

```
STORY_DIR = data/stories/{active_story}/
- world bible  → {STORY_DIR}/world/world_bible.md
- characters   → {STORY_DIR}/world/character_cast.md
- story brief  → {STORY_DIR}/planning/story_brief.md
- structure    → {STORY_DIR}/planning/structure.md
- foreshadow   → {STORY_DIR}/planning/foreshadowing.md
- story log    → {STORY_DIR}/planning/story_log.md
- chapters     → {STORY_DIR}/outputs/chapter_NNN.md
```

## 當前進度載入

每次新對話，如果用戶提到寫小說：
1. 讀取 `data/active_story.txt` 確認當前故事
2. 讀取 `{STORY_DIR}/planning/story_log.md` — 上次寫到哪裡
3. 讀取 `{STORY_DIR}/planning/story_brief.md` — 故事概要
4. 如果這些檔案存在，告訴用戶當前進度並詢問要繼續還是開新故事
5. 如果不存在，從 `/novel-writing` 開始

## 切換故事

如果用戶想切換到另一個故事：
1. 更新 `data/active_story.txt`
2. 載入該故事的進度檔案

## 章節生成規則（不可違反）

每章必須完成 4 步才算完成，缺一不可：
1. Context assembly（sub-agent）
2. Chapter generation（獨立 sub-agent）
3. Update story_log（主 agent）
4. Update story_graph（sub-agent）

**不可合併 sub-agent。不可跳過步驟。不可平行多章。**

## 開發須知

- **測試**: `uv run pytest tests/ -v`
- **AWS 認證過期**: 用 `/refresh-aws` 刷新
- **Prompt 迭代**: 先改 `.claude/skills/*/SKILL.md` 驗證，確認後同步到 `prompts/*.yaml`
- **新增 Agent**: 建 `agents/xxx.py` + `prompts/xxx.yaml` + `pipeline/nodes/xxx.py`
