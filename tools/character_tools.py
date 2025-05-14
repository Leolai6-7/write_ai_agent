from character_manager import CharacterManagerAgent

# 初始化角色管理 agent
agent = CharacterManagerAgent()

# -----------------------------
# 工具函數（tool_function_map 會使用這些）
# -----------------------------

def tool_create_character(instruction: str):
    return agent.create_character_from_instruction(instruction)

def tool_get_character(name: str):
    return agent.get_character(name)

def tool_edit_character(name: str, updates: dict):
    return agent.edit_character(name, updates)

def tool_summarize_arc(name: str):
    return agent.summarize_character_arc(name)

def tool_check_consistency(name: str, scene_text: str):
    return agent.check_consistency(name, scene_text)

def tool_assign_relationship(name1: str, name2: str, relation: str):
    return agent.assign_relationship(name1, name2, relation)

def tool_delete_character(name: str):
    return agent.delete_character(name)

# -----------------------------
# GPT 用 Tool Schema（tool_schemas）
# -----------------------------

character_tools = [
    {
        "type": "function",
        "function": {
            "name": "create_character",
            "description": "根據自然語言敘述創建一名新角色",
            "parameters": {
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "自然語言描述角色需求（如：請創造一位冷酷的女刺客）"
                    }
                },
                "required": ["instruction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_character",
            "description": "查詢角色設定",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "角色名稱"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_character",
            "description": "更新角色卡的欄位內容",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "角色名稱"},
                    "updates": {
                        "type": "object",
                        "description": "要更新的欄位內容，例如 {'personality': ['堅定', '冷靜']}"
                    }
                },
                "required": ["name", "updates"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_consistency",
            "description": "檢查角色在段落中的行為是否違反性格（OOC）",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "scene_text": {"type": "string"}
                },
                "required": ["name", "scene_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assign_relationship",
            "description": "建立兩位角色間的關係（雙向）",
            "parameters": {
                "type": "object",
                "properties": {
                    "name1": {"type": "string"},
                    "name2": {"type": "string"},
                    "relation": {"type": "string"}
                },
                "required": ["name1", "name2", "relation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_arc",
            "description": "自動摘要某個角色的心理成長歷程",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_character",
            "description": "刪除角色（慎用）",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "required": ["name"]
            }
        }
    }
]
