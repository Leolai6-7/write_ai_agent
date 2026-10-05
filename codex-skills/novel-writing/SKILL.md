---
name: novel-writing
description: "在 write_ai_agent 小說專案中規劃、續寫、修訂或覆核章節，使用可回查的故事脈絡，並同步章節記錄與故事圖譜。適用於使用者要求接續既有小說、建立此專案的新故事或維護章節連貫性；不因一般小說討論、短篇創作或任意 fiction 任務自動啟用。"
---

# 小說專案寫作

依使用者目前的階段接續工作，不一律重問故事構想，也不把討論或審稿請求擴成檔案修改。先簡短說明使用本技能及本輪處理的章節／規劃範圍。

## 1. 定位專案與故事

1. 優先使用使用者指定的專案 checkout；否則解析本技能的實際位置（先解析 symlink），若其上兩層是有效 checkout 就使用該處。預設備援位置為 `/Users/laihaoqian/write_ai_agent`。
2. 先確認專案有 `scripts/assemble_context.py`、`scripts/update_graph.py`、`scripts/chapter_workflow.py` 及 `skills/`。找不到時詢問正確位置，不建立替代專案。以下路徑均相對於已確認的專案根目錄。
3. 優先使用明確指定的故事目錄，否則讀 `data/active_story.txt`，核對 `data/stories/{slug}/` 存在。不要因指標缺失而猜故事、改指標或重建既有故事。只有建立新故事的請求才建立新目錄。
4. 讀 `planning/story_brief.md`、相關卷計畫、近期 `runtime/story_log.md` 與目標章節狀態，確認使用者要的是規劃、下一章、指定章修訂或覆核。保留原有語言、體裁與字數要求；使用者本次修改指示優先。
5. 使用專案既有 `.venv/bin/python` 或已確認可用的專案 Python；不為啟用技能自動安裝套件、建立環境或下載模型。

不要要求 Claude 插件、hooks 或特定命名 agent。可以委派互不衝突的研究／覆核；同一章的「寫正文 → 寫記錄與差分 → 套圖譜」必須循序，後章不可與尚未完成的前章平行產生。沒有委派工具時，依角色分次完成即可。

## 2. 按階段讀既有寫作規範

只讀當前階段需要的規範；下列連結相對於儲存在 repo 的本技能。若從個人技能 symlink 進入，改用已確認的專案根目錄定位同一路徑。

| 階段 | 必讀來源 | 主要交付 |
|---|---|---|
| 新故事與全書規劃 | [架構設計](../../skills/novel-architect/SKILL.md)、按需讀[世界觀](../../skills/novel-worldbuilding/SKILL.md)、[角色](../../skills/novel-characters/SKILL.md)、[伏筆](../../skills/novel-foreshadowing/SKILL.md) | `story_brief.md`、世界／角色設定、`structure.md`、`foreshadowing.md` |
| 弧線與逐章計畫 | [弧線規劃角色](../../agents/volume-planner.md) | `planning/arc_synopsis_N.md`、有效的 `planning/arc_plan_N.yaml`（N 為弧線編號） |
| 寫作與修訂 | [章節寫作規範](../../skills/novel-chapter/SKILL.md)、[章節作者角色](../../agents/chapter-writer.md) | `outputs/chapter_NNN.md` |
| 本章記錄與差分 | [進度更新角色](../../agents/progress-updater.md) | 本章唯一 log 條目、章節差分 YAML |
| 弧線／整卷覆核與風格審查 | [弧線覆核角色](../../agents/arc-reviewer.md)、[風格審查](../../skills/novel-style-audit/SKILL.md) | 有章節依據的覆核；僅按授權修訂 |

重用這些來源的寫作原則、欄位及產物格式，不沿用其 Claude 專用模型／工具宣告、強制子 agent 名稱或固定停頓次數。按使用者授權的範圍持續執行；遇到會改變故事方向的重要歧義再問。要求精簡或刪除時，不套用「修訂只能增加篇幅」。

## 3. 逐章工作迴圈

命令均在已確認的專案根目錄執行。`NOVEL_PYTHON`、`NOVEL_STORY_DIR`、`NOVEL_CHAPTER`、`NOVEL_DIFF` 代表本輪已核對的解譯器、故事絕對路徑、正整數章號及差分檔路徑；先設定實際值，或直接以實際值替換。

### 先看狀態，再組上下文

```bash
"$NOVEL_PYTHON" scripts/chapter_workflow.py status --story-dir "$NOVEL_STORY_DIR" --chapter-num "$NOVEL_CHAPTER"
```

若狀態為 `needs_review`，先依下一節覆核，不先用重新組裝或套圖譜掩蓋待確認事項。若本章已完成，而使用者要「繼續」，按實際卷計畫與已完成章節確認下一章；不要改寫已完成章。

```bash
"$NOVEL_PYTHON" scripts/assemble_context.py --story-dir "$NOVEL_STORY_DIR" --chapter "$NOVEL_CHAPTER" --format json
```

讀輸出的上下文及所指向的原件範圍，不整份傾入活人物檔；核對本章需要的角色、場景、同敘事線前章、伏筆與相關歷史原文。歷史證據只取目標章之前的章節；索引／Jev 候選須回查來源，失效或未來記憶不可補進正文。

寫作、規劃或更新角色知情資料時，讀 [敘事分層與有界上下文](../../docs/narrative-context.md)：已確立事實不等於角色已知，`belief` 不等於真相，作者計畫不等於已發生事件。依明確 `pov` 分別處理角色資料；未列出時先分辨預算省略、來源失效與未記錄，不自行推定知情或無知。POV 紀錄是高優先的完整候選，不要求全數載入。篇幅依 beat／story brief 及使用者要求，不套通用字數。文字包預設 12,000 字元，可由故事政策或 `--max-context-chars` 調整；必要內容放不下時先解決超限，不刪掉關鍵限制來取得收據。

重大選擇需要核對角色為何在當時資訊／信念與壓力下採取這個行動，及其如何看待可行替代與後果；「知道風險仍決定做」尚不是完整理由。可選 `decision_points` 留在作者計畫，依場景轉成言行，不當成角色已有記憶。遇到此類疑點，按 [重大角色決策](../../docs/character-decisions.md) 定位規劃、來源／召回或表達缺口，再修正相應模組；一般章不額外增加一輪 Agent 或新收據。

### 草稿 → 輕量編輯 → 記錄 → 差分

1. 依章節計畫與核對過的來源寫／修 `outputs/chapter_NNN.md`。按照[章節寫作規範的輕量編輯段](../../skills/novel-chapter/SKILL.md#lightweight-editorial-pass)，通讀草稿、修正具體問題，再以定稿整理記錄，不從原計畫猜測已發生事件。一般章由作者自查；重大轉折、未解的連貫性疑點或使用者要求時，才按需安排獨立覆核。不為每章新增編輯報告，也不把篇幅增加視為改進。
2. 在 `runtime/story_log.md` 保留本章唯一條目；修訂時更新原條目，不重複追加。摘要與角色、伏筆變化必須對應正文。
3. 依進度更新規範產生本章 YAML 差分。先提供相關章前 narrative ID、伏筆既有 key；改稿另提供該章舊差分作身分與完整性核對，依定稿重製本章完整差分，不只交出本次改動片段。角色、地點與既有伏筆 key 不任意改名；新伏筆以固定 `thread_id` 串接，名稱可另列，差分用 `thread` 保存該 ID。事件章號不得超過本章，不傾印累積圖譜。僅為重要新事實、知識或信念加入可選 `narrative_updates`，引用本章真實行段；來源 hash 交由程式綁定，不補標全部舊故事。
4. 使用任務專屬暫存目錄保存差分，避免不同小說共用 `/tmp/chapter_N_diff.yaml`。使用檔案編輯工具寫入，不改寫原始圖譜或手工偽造 workflow 收據。

```bash
"$NOVEL_PYTHON" scripts/update_graph.py --story-dir "$NOVEL_STORY_DIR" --diff "$NOVEL_DIFF"
"$NOVEL_PYTHON" scripts/chapter_workflow.py status --story-dir "$NOVEL_STORY_DIR" --chapter-num "$NOVEL_CHAPTER"
```

只有 `complete: true` 才宣告本章工作流程完成。`writing` 時按 `missing` 修補本章缺項，不跳往下一章。索引是另列的可選狀態；`unavailable`、`not_started` 等不可假稱成功，也不因缺少模型而自動安裝或重跑全文。

## 4. 改稿與前文變動

- 設定修訂依[分卷覆核角色](../../agents/arc-reviewer.md)區分故事內狀態變化與既有定義改寫。使用者授權修改定義時，精確更新原段及受影響的對應條目，在指定／既有回顧報告記錄舊新內容、依據及影響範圍；不只追加另一個矛盾版本。設定文件修改不會自動觸發章節的 `needs_review`，須另列受影響章節供覆核，不宣稱程式已驗證一致。
- 修改已記錄章節時，先核對章前資料，再改正文、替換本章 log、重製差分；明確使用 `update_graph.py --replace` 套用修訂。不要自動替換其他章的差分。
- 前章修改可能令未改動的後章進入 `needs_review`。讀前章變更與受影響後章的正文、log、差分，判斷情節是否仍成立；不能把「重新跑過工具」當成文義覆核。
- 若後章確實不需修改，才以 workflow 的明確 review 操作記錄具體理由（指出核對了什麼、為何不受影響）；若需改稿，走正常修訂流程。批量寫入「已確認」或手改收據不可取代逐章判斷。
- 舊圖譜若沒有可回溯歷史，依提示回查原文，不把今日累積狀態當成早期事實，也不擅自全書遷移或重建。

僅在實際完成上述覆核、確定後章無需改稿後使用；`NOVEL_REVIEW_REASON` 必須是本輪具體結論：

```bash
"$NOVEL_PYTHON" scripts/chapter_workflow.py review --story-dir "$NOVEL_STORY_DIR" --chapter-num "$NOVEL_CHAPTER" --reason "$NOVEL_REVIEW_REASON"
```

詳見 [記憶與 workflow 說明](../../docs/memory-workflow.md)。

## 5. 可選記憶與資料邊界

正文、章節記錄與 canonical 故事圖譜是主資料；索引／Jev-Mem 僅供召回。維持每本故事既有 `planning/memory_config.json` 設定，不替使用者自動啟用 Jev、變更後端或混用不同小說的記憶。

正常 `off` 不呼叫 Jev。既有 `shadow`／`active` 配合 live 後端時，組裝上下文可能向外部服務送出查詢與候選；先核對該小說已有明確使用授權，不把「請寫下一章」視為新的對外傳輸授權。沒有授權時先說明並確認處理方式，不自行改設定。

只有使用者明確要求同步指定章節，且本章通過完成檢查後，才執行：

```bash
"$NOVEL_PYTHON" scripts/novel_memory.py --story-dir "$NOVEL_STORY_DIR" sync --chapter "$NOVEL_CHAPTER"
```

不自動匯入既有小說、Codex 對話或其他資料；不搜尋／複製密鑰、不讀鑰匙圈、不安裝模型、不因召回失敗自行改用其他外部服務。記憶不可用時明示狀態，保留可核對的原文與結構化資料。

## 6. 交付

簡短列出本輪完成的章節／規劃、實際修改的文件、workflow 狀態與尚需處理的具體問題。將機械完成與文學品質覆核分開；不宣稱未做過的索引、Jev 同步或全書一致性審查已完成。
