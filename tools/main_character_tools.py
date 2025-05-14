from main_character_agent import MainCharacterAgent

# 初始化主角管理 Agent
main_char_agent = MainCharacterAgent()

# --- 工具函數 ---

def tool_get_main_character():
    """回傳完整主角角色卡 YAML 格式"""
    return main_char_agent.display_summary()

def tool_update_main_field(field: str, value, mode="append"):
    """更新主角欄位（例如 emotional_arc, current_goals）"""
    main_char_agent.update_field(field, value, mode)
    return f"✅ 主角欄位「{field}」已更新"

def tool_summarize_main_arc():
    """使用 GPT 總結主角 emotional_arc"""
    return main_char_agent.summarize_arc()

# --- GPT tools schema ---

main_character_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_main_character",
            "description": "取得目前主角的完整角色卡內容（YAML 格式）",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_main_field",
            "description": "更新主角角色卡的某個欄位（如目標、情緒弧線）",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "要更新的欄位名稱（如 emotional_arc, current_goals）"
                    },
                    "value": {
                        "type": "string",
                        "description": "要加入的內容（例如：'第五章：主角展現勇氣'）"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["append", "replace"],
                        "default": "append",
                        "description": "append 追加；replace 替換整個欄位"
                    }
                },
                "required": ["field", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_main_arc",
            "description": "根據主角的情緒歷程，請 GPT 生成目前心理狀態摘要",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]
