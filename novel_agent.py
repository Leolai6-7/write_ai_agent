import json
from openai import OpenAI
from tools import tool_schemas, tool_function_map
from chapter_generator import build_prompt
import yaml

client = OpenAI()

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_novel_agent(chapter_goal, save_to=None):
    # 初始設定
    messages = []
    system_prompt = "你是一位中文奇幻小說作家。請根據提供的角色設定與章節目標撰寫小說內容，風格內斂、有情感、節奏穩定。必要時可以使用工具創建角色、查詢角色、更新主角狀態。"
    messages.append({"role": "system", "content": system_prompt})

    # 載入角色與世界觀
    main_char = load_yaml("main_character.yaml")
    world = load_yaml("world_setting.yaml")
    
    # 加入章節目標
    prompt = build_prompt(main_char, world, chapter_goal)
    messages.append({"role": "user", "content": prompt})

    # GPT 主對話 + tools 調用
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        tools=tool_schemas,
        tool_choice="auto"
    )

    reply = response.choices[0].message

    # 處理 tool 呼叫
    if reply.tool_calls:
        tool_messages = []
        for tool_call in reply.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            if func_name in tool_function_map:
                result = tool_function_map[func_name](**args)
                tool_messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": func_name,
                    "content": result
                })
            else:
                print(f"❌ 未知工具：{func_name}")

        # 接續 GPT 對話，餵入 tool 回應
        messages.append({"role": "assistant", "tool_calls": reply.tool_calls})
        messages.extend(tool_messages)

        second_response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=tool_schemas,
            tool_choice="none"  # 第二輪不再自動選 tool
        )
        final_text = second_response.choices[0].message.content.strip()
    else:
        final_text = reply.content.strip()

    # 儲存故事段落
    if save_to:
        with open(save_to, "w", encoding="utf-8") as f:
            f.write(final_text)
        print(f"✅ 小說章節已儲存至：{save_to}")

    return final_text

