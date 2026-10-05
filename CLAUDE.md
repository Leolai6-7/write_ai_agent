# AI 小說寫作系統 (write_ai_agent)

## 專案概述
一個以本地 Python 工具、章節憑據與故事圖譜為核心的長篇小說創作系統。支援 Codex skill 與 Claude Code Plugin，共用多故事管理和分卷式流程。

## 架構

統一的 plugin（`novel-agents`）管理所有組件：

```
write_ai_agent/                    ← plugin 本體
├── .claude-plugin/plugin.json     ← plugin 定義
├── agents/                        ← sub-agents（工具限制各異）
│   ├── chapter-writer.md          → Read + Write（讀設計文件 + 前章，寫新章節）
│   ├── progress-updater.md        → Read + Edit + Write（讀章節，Edit story_log，Write 章節 diff）
│   ├── volume-planner.md          → Read + Write + Glob（規劃弧線章級 beat sheet）
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
    ├── assemble_context.py        → 結構化 + 章前圖譜 + 可選語意召回
    ├── update_graph.py            → 驗證並套用章節 diff，記錄完成憑據
    ├── chapter_workflow.py        → 每故事的完成狀態與索引狀態
    ├── index_chapter.py           → 已完成章節摘要 → 可選 ChromaDB 索引
    ├── story_graph_nx.py          → NetworkX 圖結構 + 查詢 API（扁平 JSON 格式）
    └── semantic_search.py         → ChromaDB 語義查詢（獨立工具）
```

## 多故事管理

```
data/
├── active_story.txt
└── stories/
    └── {story-name}/
        ├── world/                 → 活文件（Arc Review 時更新）
        │   ├── _index.md          → wiki 索引（地點/設定/歷史摘要 + 連結）
        │   ├── world_bible.md     → 完整世界觀（fallback，wiki 條目的原始來源）
        │   ├── character_cast.md  → 含「設計」+「當前狀態」兩區塊
        │   ├── locations/         → 每個地點一篇 wiki 條目
        │   ├── setting/           → 時代背景、AI世代、文化肌理
        │   ├── history/           → 圍棋消亡史
        │   └── 留白區域.md        → 刻意未定義的設定
        ├── planning/              → 結構文檔
        │   ├── story_brief.md     → 全書級（不變）
        │   ├── structure.md       → 卷級弧線（少變）
        │   ├── foreshadowing.md   → 跨卷伏筆（少變）
        │   ├── story_expansion.md → 故事走向概述（1頁，Stage 1 生成）
        │   ├── arc_synopsis_N.md → 弧線散文概述（每弧線前生成）
        │   ├── arc_plan_N.yaml   → 章級 beat sheet（YAML，每弧線前生成）
        │   └── arc_review_N.md    → 弧線回顧報告（依授權於弧線結束後生成）
        ├── runtime/               → 運行時文檔（每章更新）
        │   ├── story_log.md
        │   ├── story_graph.json   → 扁平 JSON + 可重播的章節 diff
        │   └── chapter_workflow.json → 必要步驟憑據 + 非阻塞索引狀態
        ├── outputs/
        │   └── chapter_NNN.md
        └── chroma/                → ChromaDB（per-story）
```

## 生命週期（卷循環）

```
Stage 1 構思 → structure.md（卷級弧線，不含章級 beat sheet）
                ↓
Stage 2 創作（每弧線循環）：
  2.0a World Expansion（如需要）→ 擴展 world_bible / character_cast
  2.0b Arc Planning → volume-planner agent → arc_synopsis_N.md + arc_plan_N.yaml
  2.1 章節循環（3 步 × M 章）
  2.9 Arc Review → arc-reviewer agent → 按授權更新受影響的設定與規劃
  → 回到 2.0a
                ↓
Stage 3 編輯 → style audit
Stage 4 組裝 → 完整小說
```

## 章節生成規則（不可違反）

每章必須完成 3 步才算完成，缺一不可：
1. **Context assembly** — 主 agent 呼叫 `scripts/assemble_context.py`，建立章前脈絡並留下 context 憑據。
2. **Chapter generation** — `novel-agents:chapter-writer`（Read+Write，讀設計文件+context導航包）；草稿完成後依 `skills/novel-chapter/SKILL.md` 做輕量編輯，以定稿交接，不為一般章額外建立審稿報告。
3. **Update progress** — `novel-agents:progress-updater` 更新 `story_log.md`、產生章節 diff；主 agent 再執行 `scripts/update_graph.py`，驗證、保存圖譜並登記憑據。改稿時根據定稿、既有 ID 與本章原 diff 重製整章完整差分，不只交出此次局部修改。

以 `scripts/chapter_workflow.py status --story-dir {STORY_DIR} --chapter-num {N}` 的 `complete: true` 驗收。單獨修改 story_log 仍屬待完成。歷史已完成章節若只有前情變動，標為 `needs_review`，不阻擋停止，但不作有效召回；先覆核再用 `review --reason` 登記，詳見操作文件。直接改動本章正文、摘要或自身 diff 則須完成必要更新。

必要步驟完成後，`off`／`shadow` 模式背景執行 `scripts/index_chapter.py`；`active` 使用 Jev-Mem，不查 Chroma、不新增 Chroma 索引工作。索引為非阻塞工作，另顯示 `pending / ok / unavailable / error / stale / not_selected` 等狀態。Context 每次只選一種召回後端，`shadow` 的 Jev 結果只留狀態／trace；服務不可用時明示原因，保留結構化與圖譜內容，不暗中切換後端。Jev 同步仍須明確指定章節，不因完成正文而自動送出。

章前包分開「作者計畫／文本事實／指定 POV 知情與信念／連貫性線索／設計參考」。可選 `narrative_updates` 綁定正文行段；不從角色出場或讀者知道的事推定角色知情。缺少 `pov` 或來源時保持未知。章前文字包預設 12,000 字元，完整條目取捨；必要資訊放不下就報錯。目標章節字數來自 beat 的 `target_length` 或 story brief，不使用固定值。資料格式與覆核規則見 [敘事脈絡](docs/narrative-context.md)。

**不可跳過必要產物與驗收。不可平行寫作相依章節。** Claude 可使用既有命名 sub-agent；Codex 可按角色委派，或依序執行寫作及進度核對，不要求平台特有的 agent 名稱。執行角色可合併，驗收步驟不可省略。

## 弧線規劃與覆核

- **每弧線開始前**：先做 World Expansion（如需要），再跑 `volume-planner` 生成 `arc_synopsis_N.md` 與 `arc_plan_N.yaml`；檔名 N 是弧線編號。
- **每弧線結束後**跑 `arc-reviewer`，依請求範圍審閱或維護受影響的設定與規劃；已授權的定義修改精確替換原段並留下變更依據，不累積互相矛盾的版本。設定修改不會自動觸發章節 `needs_review`，須列出受影響章節另行覆核。
- `assemble_context.py` 優先從 `arc_plan_N.yaml` 讀 beat sheet，fallback 到 markdown
- `structure.md` 只含卷級弧線 + 弧線分解，不含章級 beat sheet
- 新伏筆在計畫使用穩定 `thread_id`、可選顯示名稱及本章 `action`，差分仍以 `thread` 字串存 key；舊故事不重編 key。規則見 [敘事脈絡](docs/narrative-context.md#伏筆識別與本章動作)。

## 開發須知

- **環境與測試**: `uv sync --extra dev`，再用 `.venv/bin/python -m pytest tests/ -v`。預設測試使用離線替身；真實語意整合測試另設 `NOVEL_TEST_SEMANTIC=1`。
- **修改 skills/agents**: 改本地檔案 → `/reload-plugins` → 即時生效
  - plugin 快取已 symlink 到本地 repo，不需要 push/reinstall
- **發佈更新**: `git push` → 其他機器用 `/plugins update novel-agents`
- **語意召回**: `uv sync --extra dev --extra semantic` 安裝 ChromaDB 與 sentence-transformers。使用 `BAAI/bge-small-zh-v1.5`；預設只讀本地模型。首次下載需明確執行 `index_chapter.py --allow-model-download` 並帶入該章的故事與檔案參數。
- **圖資料庫**: NetworkX（`runtime/story_graph.json`），`_history` 的 baseline + diffs 是 tracked 圖譜依據，外層快照是衍生結果。兩者不一致會拒絕讀取／更新，不直接覆蓋手改內容。`update_graph.py --replace` 用於更換已有追蹤紀錄的 diff 並重播；先保留分歧原檔及核對修正內容。
- **共享讀取**: `scripts/story_snapshot.py` 每次操作只讀取一次故事來源；模型查詢後另建快照覆核。Context 憑據使用實際組裝時的快照，來源變動則重做，不能用事後新 hash 背書舊內容。
- **Codex 入口**: `codex-skills/novel-writing/SKILL.md`，以 `$novel-writing` 使用；不依賴 Claude hooks。一般程式開發不需要載入小說創作技能。
- **記憶入口**: 現行章節流程使用 `assemble_context.py`。`memory/memory_manager.py` 是保留的舊 SQLite 四層記憶 API，供相容性與既有測試使用，未接入此章節流程。
- **詳細操作與可選 Jev-Mem**: 見 [記憶與章節工作流](docs/memory-workflow.md)。
- **語言**: 所有 agent 輸出使用繁體中文
