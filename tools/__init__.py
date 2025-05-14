# tools/__init__.py

from tools.character_tools import (
    character_tools,
    tool_create_character,
    tool_get_character,
    tool_edit_character,
    tool_check_consistency,
    tool_assign_relationship,
    tool_summarize_arc,
    tool_delete_character,
)

from tools.main_character_tools import (
    main_character_tools,
    tool_get_main_character,
    tool_update_main_field,
    tool_summarize_main_arc,
)

# 所有提供給 GPT 使用的工具 schema
tool_schemas = character_tools + main_character_tools

# GPT 工具呼叫對應的實際 Python 函數
tool_function_map = {
    "create_character": tool_create_character,
    "get_character": tool_get_character,
    "edit_character": tool_edit_character,
    "check_consistency": tool_check_consistency,
    "assign_relationship": tool_assign_relationship,
    "summarize_arc": tool_summarize_arc,
    "delete_character": tool_delete_character,

    "get_main_character": tool_get_main_character,
    "update_main_field": tool_update_main_field,
    "summarize_main_arc": tool_summarize_main_arc,
}
