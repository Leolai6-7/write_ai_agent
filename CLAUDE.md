# AI 小說寫作系統 (write_ai_agent)

## 專案概述
一個基於 Claude Code Plugin 的多 Agent 長篇小說自動生成系統。支援多故事管理和分卷式小說創作。

## 架構

統一的 plugin（`novel-agents`）管理所有組件：

```
write_ai_agent/                    ← plugin 本體
├── .claude-plugin/plugin.json     ← plugin 定義
├── agents/                        ← sub-agents（工具限制各異）
│   ├── chapter-writer.md          → Read + Write（讀設計文件 + 前章，寫新章節）
│   ├── progress-updater.md        → Read + Edit + Write（讀章節，Edit story_log，Write story_graph）
│   ├── volume-planner.md          → Read + Write + Glob（讀設計文件，輸出 YAML）
│   └── arc-reviewer.md            → Read + Edit + Write + Glob（Edit 原檔 + Write 報告）
├── skills/                        ← 主 agent 的工作流 skills
│   ├── novel-writing/             → 入口 + pipeline
│   ├── novel-chapter/             → 寫作哲學
│   ├── novel-worldbuilding/
│   ├── novel-characters/
│   ├── novel-architect/
│   ├── novel-foreshadowing/
│   └── novel-style-audit/
└── scripts/                       ← Python 工具
    ├── assemble_context.py        → 三路召回（結構化 + 圖譜 + 語義）
    ├── index_chapter.py           → 章節 → ChromaDB 索引
    ├── story_graph_nx.py          → NetworkX 圖結構 + 查詢 API（扁平 JSON 格式）
    └── semantic_search.py         → ChromaDB 語義查詢
```

## 多故事管理

```
data/
├── active_story.txt
└── stories/
    └── {story-name}/
        ├── world/                 → 活文件（Arc Review 時更新）
        │   ├── world_bible.md
        │   └── character_cast.md  → 含「設計」+「當前狀態」兩區塊
        ├── planning/              → 結構文檔
        │   ├── story_brief.md     → 全書級（不變）
        │   ├── structure.md       → 卷級弧線（少變）
        │   ├── foreshadowing.md   → 跨卷伏筆（少變）
        │   ├── volume_plan_N.yaml → 章級 beat sheet（YAML，每卷開始前生成）
        │   └── arc_review_N.md    → 弧線回顧報告（每卷結束後生成）
        ├── runtime/               → 運行時文檔（每章更新）
        │   ├── story_log.md
        │   └── story_graph.json   → 扁平 JSON 格式
        ├── outputs/
        │   └── chapter_NNN.md
        └── chroma/                → ChromaDB（per-story）
```

## 生命週期（卷循環）

```
Stage 1 構思 → structure.md（卷級弧線，不含章級 beat sheet）
                ↓
Stage 2 創作（每卷循環）：
  2.0 Volume Planning → volume-planner agent → volume_plan_N.md
  2.1 章節循環（3 步 × M 章）
  2.9 Arc Review → arc-reviewer agent → 更新 world_bible + character_cast
                ↓
Stage 3 編輯 → style audit
Stage 4 組裝 → 完整小說
```

## 章節生成規則（不可違反）

每章必須完成 3 步才算完成，缺一不可：
1. **Context assembly** — `scripts/assemble_context.py`（主 agent 呼叫，9 秒）
2. **Chapter generation** — `novel-agents:chapter-writer`（Read+Write，讀設計文件+context導航包）
3. **Update progress** — `novel-agents:progress-updater`（Read+Edit+Write，Edit story_log + Write story_graph.json）

完成後自動觸發（非阻塞）：
- `scripts/index_chapter.py` → ChromaDB 索引

**不可合併 sub-agent。不可跳過步驟。不可平行多章。**

## 卷級規則

- **每卷開始前**必須先跑 `volume-planner`，生成 `volume_plan_N.yaml`
- **每卷結束後**必須跑 `arc-reviewer`，更新 world_bible + character_cast
- `assemble_context.py` 優先從 `volume_plan_N.yaml` 讀 beat sheet，fallback 到 markdown
- `structure.md` 只含卷級弧線 + 弧線分解，不含章級 beat sheet

## 開發須知

- **測試**: `uv run pytest tests/ -v`
- **修改 skills/agents**: 改本地檔案 → `/reload-plugins` → 即時生效
  - plugin 快取已 symlink 到本地 repo，不需要 push/reinstall
- **發佈更新**: `git push` → 其他機器用 `/plugins update novel-agents`
- **Embedding model**: ChromaDB 使用 `BAAI/bge-small-zh-v1.5`（中文專用）
- **圖資料庫**: NetworkX（`runtime/story_graph.json`，扁平 JSON 格式，由 progress-updater 直接更新）
- **語言**: 所有 agent 輸出使用繁體中文
