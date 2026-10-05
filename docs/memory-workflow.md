# 小說記憶流程與 Jev-Mem 試驗

小說原文、章節記錄與結構化圖譜是主資料；向量索引與 Jev-Mem 是可重建的召回層。Jev-Mem 的判斷用於記憶建立與召回，不負責生成小說，也不取代原本的寫作 Agent。

## 1. 完成一章的條件

1. `assemble_context.py` 讀取章前資料，記錄上下文收據。
2. 寫入 `outputs/chapter_NNN.md`。
3. 更新 `runtime/story_log.md`，包含唯一的本章標題與非空摘要。
4. 以 `update_graph.py` 驗證及套用本章差分，記錄圖譜收據。

只有四項一致才標為完成。索引另列狀態，不因選用套件或模型缺少而阻擋正文完成；也不把索引失敗當成功。

```bash
uv sync --extra dev
uv run python scripts/assemble_context.py --story-dir data/stories/STORY --chapter 3 --format json
# 由寫作 Agent 寫正文，再由進度更新 Agent 寫 story_log 與差分 YAML。
uv run python scripts/update_graph.py --story-dir data/stories/STORY --diff /path/to/chapter_3_diff.yaml
uv run python scripts/chapter_workflow.py status --story-dir data/stories/STORY --chapter-num 3
```

`runtime/chapter_workflow.json` 綁定正文、當章記錄、圖譜歷史前綴；上下文收據綁定前章正文、記錄與章前圖譜。收據是步驟及內容一致性檢查，不是文學品質或語義正確性的保證。

狀態分成 `writing`（必要步驟未完成）、`complete`（來源一致）、`needs_review`（過去已完成，本章正文／記錄／自身 diff 未變，但前情變動）。Stop 只阻擋 `writing`；`needs_review` 仍會列出，而且不能當有效記憶。改前章不等於要重寫所有後文。

先查狀態，再決定是否重寫。若人工核對後確認原章仍成立，可留下具體理由：

```bash
.venv/bin/python scripts/chapter_workflow.py review --story-dir data/stories/STORY --chapter-num 3 --reason '核對前章修訂與本章承接，改動只涉及標點，人物行動及線索未變'
```

此命令只接受未變動的歷史已完成章節，將理由與當下來源指紋一同保留。正文、當章摘要或自身 diff 被改動時，仍走正常更新；圖譜不一致不能以 review 放行。明確重新 assemble 或套用 graph receipt 會重開寫作流程。舊收據沒有自身 diff 指紋、且歷史前綴已變時，不猜測先前狀態；需重新核對必要步驟，未自動改寫既有檔案。

Claude hooks 只追蹤本專案 `data/stories/*`；其他工具／Codex 可直接使用以上 CLI。既有小說不自動全量補寫收據、遷移或重建。

Codex 使用 `codex-skills/novel-writing/SKILL.md` 入口；可委派或循序完成角色工作，不需要 Claude 特定 agent 名稱或 hooks。兩種入口的完成與覆核規則相同。

## 2. 圖譜重試與改稿

相同章號、相同差分可安全重跑，不會再次累加角色事件。已記錄章號改用另一份差分時，必須明確加 `--replace`：

```bash
uv run python scripts/update_graph.py --story-dir data/stories/STORY --diff /path/to/revised_diff.yaml --replace
```

系統保留既有基底與逐章差分，重播該章及後續圖譜。正文與 `story_log` 仍須由作者同步修改；後續章節須人工覆核，不能只重跑命令就認為情節已修好。

有 `_history` 的圖譜以 baseline + diffs 為依據，外層欄位是重播出的快照。讀取、重試、套用新章、保存及章前投影都會比對；若有人只改外層，會明確拒絕，不蓋掉修正。遇到不一致時先另存分歧原件，確認要保留的修改，再透過正確 diff 修正；不能刪掉 `_history` 來繞過檢查。

`StorySnapshot` 在一次狀態檢查／召回中共用圖譜、記錄、收據與正文內容，避免逐章重讀整個前綴。這是單次操作快取，不是長期索引。Context 組裝完成前核對快照仍有效；Jev worker 回來後建立新快照驗證，來源變動就撤回該次 evidence。為相容既有收據，workflow 保留正規化換行的文字 hash，Jev 正文觀察保留原始 bytes hash。

舊圖譜若只有累積結果、沒有逐章歷史，不能還原其中更早章節。回寫舊章時會跳過含本章／未來狀態的舊圖譜，不把最新狀態冒充歷史快照。舊基底涵蓋的章號禁止直接 `--replace`；需另行核對原文、重建正確基底。

## 3. 語意召回：可選、本地、具章號邊界

正常上下文包括規劃定位、同敘事線前章結尾、近期記錄、圖譜，以及一條選定的記憶召回。`off`／`shadow` 使用原 Chroma 候選，`active` 改由 Jev-Mem 提供候選，不同時注入兩套結果。歷史記錄、圖譜和召回只使用小於目標章號的內容；規劃及世界設定是作者設計資料，不是歷史事件證據。

```bash
uv sync --extra dev --extra semantic
# 首次明確允許下載 embedding 模型；之後省略此旗標。
uv run --extra semantic python scripts/index_chapter.py --story-dir data/stories/STORY --chapter-num 1 --chapter-file data/stories/STORY/outputs/chapter_001.md --allow-model-download
```

日常組裝與背景索引不自動下載模型。未安裝套件、沒有索引或本地模型不可用時，輸出 `not_indexed`／`unavailable` 等狀態，保留結構化資料與故事圖譜。摘要候選附原文章號與路徑，寫作前可回查。使用 Jev-Mem 的 `active` 模式不需要安裝 Chroma 的 `semantic` extra。

索引候選還需通過來源檢查；正文／摘要改寫後尚未重建，或舊索引沒有來源收據時，會略過並提示 `needs_reindex`。只需明確重建受影響章節，不自動重建整本小說。

## 4. Jev-Mem 三種模式

| 模式 | 寫作使用的召回 | 背景工作 |
|---|---|---|
| `off`（預設） | 原 Chroma（有可用索引時） | 不啟動 Jev worker、不建立 Jev 記憶、不呼叫 Jev 服務。 |
| `shadow` | 原 Chroma | Jev 作旁路比較；上下文 JSON 只保留狀態／trace，不交付其證據。 |
| `active` | 只用 Jev-Mem，每次至多 3 筆有來源的章前證據 | 不查 Chroma、不新增其背景索引工作，index 顯示 `not_selected`。 |

Jev-Mem 本身含向量／關鍵字候選與受控圖譜探索，不依賴原 Chroma。原 `story_graph.json` 的角色、伏筆與數值等明確設定仍保留，並非要一併移除。`active` 遇到空記憶、服務錯誤或來源失效時會明示狀態，只保留結構化資料與故事圖譜，不偷偷切換 Chroma。無效設定不呼叫任一召回後端。

設定放在個別小說 `planning/memory_config.json`，範例見 `examples/memory_config.example.json`。此設定及衍生記憶不納入 Git。切回 `off` 即停止使用 Jev，恢復原召回；既有資料不刪除。下次排程可更新原索引；切換不會取消已在執行的索引程序。正文完成後仍需明確執行 `sync --chapter N` 才會加入 Jev 記憶。

### 獨立執行環境

使用 [Jev-Mem 上游專案](https://github.com/libingzheren/Jev-Mem) 的獨立 Python 環境，依上游安裝說明準備。這次介接測試對應 commit `81574eb23f3fd8d1a6c4d54a1e7d6f2dd539e9bb`。本專案與上游都有名為 `memory` 的套件，因此由隔離 subprocess 執行，不合併 import path 或套件環境。

可在設定檔指定 `python`／`source`，或用 `JEV_MEM_PYTHON`／`JEV_MEM_SOURCE` 環境變數覆蓋。模型應先在上游環境準備好；live 模式另需在執行環境設定 `TYPESAFE_API_KEY`，金鑰不放在小說設定、Git 或原文。選用 TypeSafe 模型可透過設定中的 `jev_model` 指定。

每次只有明確指定、通過完成驗收的章節才會同步：

```bash
uv run python scripts/novel_memory.py --story-dir data/stories/STORY status
uv run python scripts/novel_memory.py --story-dir data/stories/STORY sync --chapter 1
uv run python scripts/novel_memory.py --story-dir data/stories/STORY query --before-chapter 3 --query '主角把鑰匙交給誰？'
```

`sync` 取用當章 `story_log`（最多 4,000 字），並綁定正文與記錄雜湊。live 模式會把記憶文字及查詢所需候選傳給 TypeSafe 做判斷；正文全文不在自動同步範圍，不能把它稱為全本地 AI。此處不讀 Codex 對話記憶，也不混入其他小說。

同份來源重跑不重複新增；舊章改寫、插入或 backend 更動會重建衍生 generation，成功才切換 current pointer，保留前一版本。查詢在送進模型前排除未來章、其他故事及來源已失效的記憶；不改動已儲存圖譜。mock 與 live 記憶不可混用，改模式測試請使用不同的測試小說。

需要修復衍生記憶時，可在 `sync --chapter N` 後加 `--rebuild`，從已捕捉且仍有效的章節記錄重建；不改寫小說原件。召回途中來源發生修改時回傳 `stale`，不把該次結果交給寫作 Agent。

### 同一次工作內連續查詢

需要連續查幾個線索時，可明確使用有界 session，共用隔離程序與 encoder。每題仍重新載入記憶、排除不合格章節，並在回傳後覆核來源；不共用已被前題裁切的圖譜、答案或 Jev 判斷快取。

```python
from pathlib import Path
from memory.jev_bridge import JevWorkerSession, query_memory

story = Path("data/stories/STORY")
with JevWorkerSession() as session:
    first = query_memory(story, 12, "鑰匙最後交給誰？", worker_session=session)
    second = query_memory(story, 8, "當時主角知道暗語嗎？", worker_session=session)
```

第一題仍包含冷啟動；後續題目才重用模型。離開 `with` 即關閉程序，至多 128 題，只接受循序查詢；逾時、協定錯誤或 backend 改變即停止，不自動重試付費請求。`off`／空記憶不啟動程序。既有單題 CLI 仍是一題一程序，沒有安裝背景常駐服務或改變小說後端設定。

## 5. 怎麼比較效果

已有[同輸入比較與記錄保真檢查](memory-evaluation.md)：預設離線檢查正文→摘要／記錄的必要線索；明確啟用 live 時，兩套後端使用同一份文字、問題及回傳預算。正式流程原有的 Chroma 摘要／Jev 完整記錄差異保持不動，不能混用兩種輸入條件宣稱模型勝負。

先用 `shadow`，保留原有寫作流程。對同一目標章與問題，查看原本上下文及 `novel_memory.py query` 回傳來源，評估：

- 是否找回必要的前情，能否定位原文。
- 是否混入未來、舊版或其他小說內容。
- 更正前章後，舊記憶是否被排除。
- 額外呼叫數、延遲及人工查證成本是否值得。

至少包含遠距伏筆、改名／別名、物品轉手、舊章修改與相似場景等題目，再決定是否切 `active`。目前測試驗證流程及隔離，不代表 Jev-Mem 已提升長篇小說品質或降低成本。

`tests/test_memory/test_jev_scenarios.py` 提供四章虛構故事與三題來源驗收：早期暗語、別名連回早前物品交接、轉手後的持有人；另放入相似場景干擾與未來章節。live 測試逐題列出必要／召回章號及缺漏，mock 只驗證流程與隔離，不能當品質證據。這組舊測試沒有 Chroma 對照；另已完成 [9 章、8 題的同輸入實跑](memory-evaluation.md#5-同題實跑2026-10-01)：已記錄必要來源為 Chroma 6/7、Jev 7/7，不能與下列舊題組混算。

### 本次小樣本結果（2026-10-01）

以 `jev-1.13.0`、已快取的 `paraphrase-multilingual-MiniLM-L12-v2` 及上述 upstream commit 執行真實 API 測試；資料全為虛構，查詢都限定第 4 章之前：

| 問題 | 必要章節 | 實際召回 | Jev 判斷次數／停止原因 |
|---|---|---|---|
| 早期暗語的取信時間與地點 | 1 | 1 | 4／達到呼叫上限 |
| 「夜鷺」別名連回先前交接物品 | 1、3 | 3、1 | 2／證據足夠 |
| 轉手後胸針由誰保管 | 3 | 3 | 4／證據足夠 |

三題皆找到指定來源片段，未帶入第 2 章干擾或第 4 章未來資訊。早期暗語雖召回正確，但不是以「證據足夠」停止，仍需關注探索成本。四次寫入與三次查詢整個測試耗時約 30 秒，包含多次程序與模型初始化；不是每題端到端延遲。這不是長篇品質、相對 Chroma 優勢或成本節省的證明。

## 6. 可重跑驗證

2026-10-01 基礎重構驗收：全套離線 `166 passed, 11 skipped`；另以真實上游引擎搭配 mock 判斷執行 bridge／scenario 測試，`22 passed, 3 skipped`（三題 live 案例未在此輪重跑）。本輪未呼叫付費 API，未改任何既有小說。

新增覆核涵蓋：手改圖譜快照拒絕覆寫、前情變動與本章改稿分流、review 原因與來源綁定、每次檢查每檔最多讀一次、模型查詢前後各建一次快照、組裝中修改／新增規劃檔就拒絕舊 context 收據、CRLF 舊指紋相容。Codex skill 通過格式／連結檢查，並用待覆核續寫與縮稿兩個唯讀情境演練；不是完整小說寫作品質測試。

同日第二階段（敘事分層與有界上下文）離線驗收：`258 passed, 11 skipped`。新增測試涵蓋事實／知情／信念區隔、正文行段與 hash 綁定、退休或失效記錄不回退、POV 缺漏、100 筆角色紀錄的完整條目取捨、小預算不留收據、JSON 不繞過文字預算、章前圖譜的精確來源、待覆核圖譜來源排除，以及伏筆編號與複合地點的相容性。未啟用模型／API 整合測試，未修改既有小說；這些合成測試驗證機制，不代表已量測寫作品質改善。

同日三章實寫與選擇性改稿驗收完成：全套離線 `297 passed, 11 skipped`。虛構短篇先由不同角色視角寫出「讀者知道、人物尚未知」，再修改第一章藏處：第二章經逐段覆核保留原文，第三章重新組裝脈絡後同步改寫取物動作。另修復實寫揭露的縮排YAML定位多帶下一章首行問題。見 [短篇、來源及驗收結果](../examples/narrative-smoke/planning/arc_review_1.md)；這次驗證正文與流程，未啟用Jev或語意模型。

```bash
uv run --extra dev python -m pytest -q
# 以下用真實上游引擎、mock 判斷與合成小說；不需 live key。
NOVEL_TEST_JEV=1 uv run --extra dev python -m pytest tests/test_memory/test_jev_bridge.py -q
# 顯式開啟付費 API smoke；仍只使用測試程式內的虛構文字。
NOVEL_TEST_JEV_LIVE=1 uv run --extra dev python -m pytest tests/test_memory/test_jev_live.py -s -q
# 三題合成故事來源驗收（四次寫入、三次查詢）。
NOVEL_TEST_JEV_LIVE=1 uv run --extra dev python -m pytest tests/test_memory/test_jev_scenarios.py -s -q
```

後兩者需配置 `JEV_MEM_PYTHON`／`JEV_MEM_SOURCE`。live 測試另需 key 與預先快取的 encoder，可用 `JEV_MEM_ENCODER`、`JEV_MEM_MODEL` 指定。模型式語意檢索另由 `NOVEL_TEST_SEMANTIC=1` 啟用，可用 `NOVEL_TEST_ENCODER` 選擇已快取的測試模型；預設離線測試不需下載。
