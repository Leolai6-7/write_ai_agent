import json
from openai import OpenAI
from tools import tool_schemas, tool_function_map
from chapter_generator import build_prompt
import yaml
from timeline_generator import update_timeline

client = OpenAI()

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_novel_agent(chapter_goal, save_to=None):
    # 初始設定
    messages = []
    system_prompt = """你是一位中文奇幻小說作家。
    請根據角色設定、世界觀與章節目標撰寫小說內容，風格內斂、有情感、節奏穩定。
    你有以下工具可以使用，請在需要時主動呼叫：

    1. create_character(info): 當有新角色出現時使用。
    2. query_character(name): 查詢角色的背景與記憶。
    3. update_main_character(updates): 當主角成長或獲得新能力時使用。
    4. append_character_memory(name, event): 為角色記下新事件或記憶。
    5. load_context_snapshot(): 當需要了解當前世界與主線發展時使用。

    請你在撰寫章節過程中，根據情節需要，自動選擇並呼叫適當的工具。
    你不需要寫出工具的執行結果，只要專注於故事與情感的描寫即可。
    """

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

import os
import re

def find_last_chapter_id(outputs_dir="outputs"):
    if not os.path.exists(outputs_dir):
        return 0
    files = os.listdir(outputs_dir)
    chapter_ids = [
        int(match.group(1)) for f in files
        if (match := re.match(r"chapter_(\d+)\.md", f))
    ]
    return max(chapter_ids, default=0)

from chapter_generator import generate_chapter
from plot_planner_agent import PlotPlannerAgent
from expansion_agent import expand_chapter_file

def write_chapter(chapter_id: int, objective: str = None):
    print(f"\n📘 開始撰寫第 {chapter_id} 章...\n")

    # === 讀取上下文快照（若存在）
    context = None
    if os.path.exists("context_snapshot.yaml"):
        with open("context_snapshot.yaml", "r", encoding="utf-8") as f:
            context = f.read()

    # === 任務規劃
    if chapter_id > 1 and not objective:
        planner = PlotPlannerAgent()
        prev_summary_path = f"summaries/chapter_{chapter_id-1:02d}_summary.md"
        if os.path.exists(prev_summary_path):
            with open(prev_summary_path, "r", encoding="utf-8") as f:
                summary = f.read()
        else:
            print("⚠️ 找不到前一章摘要，無法規劃目標。")
            return
        print("🎯 建議的任務方向：\n")
        suggestions = planner.suggest_next_objectives(summary)
        print(suggestions)
        objective = input("\n請輸入你想使用的章節目標（可從建議中選一條）：\n> ")
        planner.log_objective(chapter_id, objective)

    elif chapter_id == 1:
        if not objective:
            print("❌ 第一章必須手動提供 objective。")
            return
        else:
            print(f"🎯 使用的目標：{objective}")
            planner = PlotPlannerAgent()
            planner.log_objective(chapter_id, objective)

    # === 產出初稿
    chapter_text = generate_chapter(
        character_path="main_character.yaml",
        world_path="world_setting.yaml",
        objective=objective,
        chapter_id=chapter_id,
        save_to=f"outputs/chapter_{chapter_id:02d}.md",
        context=context
    )

    print(f"\n✅ 第 {chapter_id} 章初稿完成，以下是內容預覽：\n")
    print("=" * 30)
    print(chapter_text)
    print("=" * 30)

    # === 執行擴寫
    print("\n🚧 執行擴寫並覆蓋原章節...\n")
    result = expand_chapter_file(f"outputs/chapter_{chapter_id:02d}.md")

    # === 印出擴寫後定稿內容（debug 追蹤）
    print("\n🧪 DEBUG 擴寫回傳預覽（前300字）：\n")
    print(result[:300])

    if result and "【改寫版本】" in result:
        print("✅ 成功找到【改寫版本】，擷取並顯示定稿：")
        final_text = result.split("【改寫版本】")[-1].strip()
        print(f"\n📘 擴寫後定稿內容：\n")
        print("=" * 30)
        print(final_text)
        print("=" * 30)
    else:
        print("⚠️ 沒有偵測到【改寫版本】，以下是 GPT 回傳的完整內容：")
        print(result)


def write_story_loop():
    print("📚 啟動小說連續創作模式！")

    current_chapter = find_last_chapter_id() + 1
    print(f"📍 目前最新章節：第 {current_chapter - 1} 章")
    print(f"🚀 將從第 {current_chapter} 章開始寫作")

    while True:
        if current_chapter == 1:
            objective = input("\n請輸入第 1 章的故事目標：\n> ")
            write_chapter(current_chapter, objective)
        else:
            write_chapter(current_chapter)  # 自動規劃 + 輸入目標 + 自動寫

        cont = input("\n📝 是否繼續寫下一章？(y/n): ").strip().lower()
        if cont != "y":
            print("🛑 寫作結束，歡迎下次再來！")
            break

        current_chapter += 1
        update_timeline()