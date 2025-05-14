# write_agent
novel_agent_project/
│
├── chapter_generator.py          ✍️ 小說段落生成模組
│   ├─ build_prompt()
│   ├─ generate_chapter()
│   └─ load_yaml()
│
├── character_manager.py          🧠 多角色管理 Agent
│   └─ CharacterManagerAgent
│       ├─ create / edit / get
│       ├─ assign_relationship()
│       ├─ check_consistency()
│       └─ summarize_character_arc()
│
├── main_character_agent.py       🌟 主角管理 Agent
│   └─ MainCharacterAgent
│       ├─ update_field()
│       ├─ summarize_arc()
│       └─ display_summary()
│
├── novel_agent.py                🤖 小說主控 Agent
│   └─ run_novel_agent(chapter_goal, save_to)
│       ├─ 載入主角 + 世界觀 + 任務目標
│       ├─ 呼叫 GPT（內建工具使用）
│       └─ 處理 tool_call → 執行對應工具函數
│
├── agent_loop.py                 🧪 測試與 CLI 入口（可選）
│   └─ 使用者輸入 → 呼叫 run_novel_agent()
│
├── outputs/                      📁 輸出章節內容
│   ├─ chapter_01.md
│   ├─ ...
│
├── tools/                        🛠️ GPT 工具模組
│   ├── __init__.py                  ← 整合所有 tools
│   ├── character_tools.py           ← 多角色用工具（創角、查詢、關係、OOC 檢查）
│   └── main_character_tools.py      ← 主角專用工具（更新情緒弧線、目標等）
│
├── character_memory.yaml        📒 所有配角角色資料庫
├── main_character.yaml          📘 主角角色卡（追蹤主線人物變化）
├── world_setting.yaml           🌍 世界觀（時代、魔法規則、地理）
│
├── requirements.txt             📦 套件列表（建議包含 openai>=1.0.0）
├── .env                         🔐 儲存 OPENAI_API_KEY（選擇性）
├── .gitignore                   🧼 忽略檔案（如 .env, __pycache__ 等）
└── 小說AI_Agent.ipynb          💻 Notebook 版本主控（測試用）
