# AI 小說寫作系統 (write_ai_agent)

## 專案概述
一個基於 Claude Code Skills 的多 Agent 長篇小說自動生成系統。支援多故事管理和分卷式小說創作。Python 基礎設施（LangGraph + SQLite + ChromaDB）透過 CLI 腳本橋接到 skill pipeline。

## 架構

兩層系統：
- **Skill Pipeline**（生產用）：Claude Code sub-agents 讀寫 markdown 檔案，透過 skills 定義工作流
- **Python Infrastructure**（資料層）：SQLite + ChromaDB 提供結構化查詢和語義檢索，透過 `scripts/` CLI 腳本橋接

## 小說寫作 Skills

完整工作流入口：`/novel-writing`

| Skill | 用途 |
|-------|------|
| `/novel-worldbuilding` | 世界觀構建 |
| `/novel-characters` | 角色群像設計 |
| `/novel-architect` | 分卷/弧線結構 |
| `/novel-foreshadowing` | 伏筆規劃 |
| `/novel-context` | 上下文組裝（章節生成前的 RAG） |
| `/novel-chapter` | 章節生成（含改寫模式） |
| `/novel-style-audit` | 文風審查（弧線級） |

## 多故事管理

每個故事有獨立的子目錄。`data/active_story.txt` 記錄當前正在寫的故事。

```
data/
├── active_story.txt              → 當前故事名稱
└── stories/
    └── {story-name}/
        ├── world/
        │   ├── world_bible.md
        │   └── character_cast.md
        ├── planning/           → 設計文檔（寫章前定好，不隨章節更新）
        │   ├── story_brief.md
        │   ├── structure.md
        │   └── foreshadowing.md
        ├── runtime/            → 運行時文檔（每章更新）
        │   ├── story_log.md
        │   └── story_graph.md
        ├── outputs/
        │   └── chapter_NNN.md
        ├── novel.db              → SQLite（per-story）
        └── chroma/               → ChromaDB（per-story）
```

## 路徑規則

所有 sub-agent 的檔案路徑必須使用 active story 的目錄：

```
STORY_DIR = data/stories/{active_story}/
```

## 當前進度載入

每次新對話，如果用戶提到寫小說：
1. 讀取 `data/active_story.txt` 確認當前故事
2. 讀取 `{STORY_DIR}/runtime/story_log.md` — 上次寫到哪裡
3. 讀取 `{STORY_DIR}/planning/story_brief.md` — 故事概要
4. 如果這些檔案存在，告訴用戶當前進度並詢問要繼續還是開新故事
5. 如果不存在，從 `/novel-writing` 開始

## 章節生成規則（不可違反）

每章必須完成 4 步才算完成，缺一不可：
1. Context assembly（sub-agent）
2. Chapter generation（獨立 sub-agent）
3. Update story_log（主 agent）
4. Update story_graph（sub-agent）

完成後自動觸發（非阻塞）：
- `scripts/index_chapter.py` → SQLite + ChromaDB 索引
- `scripts/sync_graph.py` → story_graph → SQLite 同步

**不可合併 sub-agent。不可跳過步驟。不可平行多章。**

Hooks（`.claude/hooks/`）會自動追蹤完成狀態，阻止在未完成所有步驟時停止回應。

## 橋接腳本

| 腳本 | 用途 | 時機 |
|------|------|------|
| `scripts/index_chapter.py` | 章節摘要 → SQLite + ChromaDB | Step 3 後 |
| `scripts/sync_graph.py` | story_graph.md → SQLite | Step 4 後 |
| `scripts/semantic_search.py` | ChromaDB 語義查詢 | Step 1（context assembly）中 |

## 開發須知

- **測試**: `uv run pytest tests/ -v`
- **Skill 迭代**: 改 `.claude/skills/*/SKILL.md`，用 git commit 做版本管理
- **A/B 測試**: workspace 在 `.claude/skills/novel-chapter-workspace/`，每個 iteration 有 skill-snapshot
- **Embedding model**: ChromaDB 使用 `BAAI/bge-small-zh-v1.5`（中文專用）
