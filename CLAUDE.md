# AI 小說寫作系統 (write_ai_agent)

## 專案概述
一個基於 Claude Code Plugin 的多 Agent 長篇小說自動生成系統。支援多故事管理和分卷式小說創作。

## 架構

統一的 plugin（`novel-agents`）管理所有組件：

```
write_ai_agent/                    ← plugin 本體
├── .claude-plugin/plugin.json     ← plugin 定義
├── agents/                        ← 工具限制的 sub-agents（自動發現）
│   ├── chapter-writer.md          → Write only（不能讀檔，防止跨線汙染）
│   └── graph-updater.md           → Read + Write only
├── skills/                        ← 主 agent 的工作流 skills
│   ├── novel-writing/             → 入口 + pipeline
│   ├── novel-chapter/             → 寫作哲學
│   ├── novel-worldbuilding/
│   ├── novel-characters/
│   ├── novel-architect/
│   ├── novel-foreshadowing/
│   ├── novel-context/             → 設計文檔（已被 assemble_context.py 取代）
│   └── novel-style-audit/
└── scripts/                       ← Python 工具
    ├── assemble_context.py        → 三路召回（結構化 + 圖譜 + 語義）
    ├── index_chapter.py           → 章節 → ChromaDB 索引
    ├── sync_graph.py              → story_graph.md → NetworkX JSON
    ├── story_graph_nx.py          → NetworkX 圖結構 + 查詢 API
    └── semantic_search.py         → ChromaDB 語義查詢
```

## 多故事管理

```
data/
├── active_story.txt
└── stories/
    └── {story-name}/
        ├── world/                 → 設計文檔
        │   ├── world_bible.md
        │   └── character_cast.md
        ├── planning/              → 設計文檔（不隨章節更新）
        │   ├── story_brief.md
        │   ├── structure.md
        │   └── foreshadowing.md
        ├── runtime/               → 運行時文檔（每章更新）
        │   ├── story_log.md
        │   └── story_graph.md
        ├── outputs/
        │   └── chapter_NNN.md
        └── chroma/                → ChromaDB（per-story）
```

## 章節生成規則（不可違反）

每章必須完成 4 步才算完成，缺一不可：
1. **Context assembly** — `scripts/assemble_context.py`（主 agent 呼叫，9 秒）
2. **Chapter generation** — `novel-agents:chapter-writer`（Write only，不能讀其他檔案）
3. **Update story_log** — 主 agent 直接編輯
4. **Update story_graph** — `novel-agents:graph-updater`（Read + Write only）

完成後自動觸發（非阻塞）：
- `scripts/index_chapter.py` → ChromaDB 索引
- `scripts/sync_graph.py` → story_graph → NetworkX JSON

**不可合併 sub-agent。不可跳過步驟。不可平行多章。**

## 開發須知

- **測試**: `uv run pytest tests/ -v`
- **修改 skills/agents**: 改本地檔案 → `/reload-plugins` → 即時生效
  - plugin 快取已 symlink 到本地 repo，不需要 push/reinstall
- **發佈更新**: `git push` → 其他機器用 `/plugins update novel-agents`
- **Embedding model**: ChromaDB 使用 `BAAI/bge-small-zh-v1.5`（中文專用）
- **圖資料庫**: NetworkX（`runtime/story_graph.json`），從 `story_graph.md` 同步
