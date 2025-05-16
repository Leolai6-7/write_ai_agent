import json
import os
import re
import yaml
import textwrap
from openai import OpenAI
from tools import tool_schemas, tool_function_map
from chapter_generator import build_prompt, generate_chapter
from timeline_generator import update_timeline
from character_memory_agent import update_all_active_characters_memory
from expansion_agent import expand_chapter_file
from goal_planner_agent import suggest_subgoals, log_subgoals, get_chapter_objective
from plot_planner_agent import PlotPlannerAgent

client = OpenAI()

MAIN_GOAL_FILE = "main_goal.yaml"

plot_agent = PlotPlannerAgent()

def save_text(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def load_main_goal():
    if os.path.exists(MAIN_GOAL_FILE):
        with open(MAIN_GOAL_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f).get("goal")
    return None

def save_main_goal(goal):
    with open(MAIN_GOAL_FILE, 'w', encoding='utf-8') as f:
        yaml.dump({"goal": goal}, f, allow_unicode=True)

def find_last_chapter_id(outputs_dir="outputs"):
    if not os.path.exists(outputs_dir):
        return 0
    files = os.listdir(outputs_dir)
    chapter_ids = [int(match.group(1)) for f in files if (match := re.match(r"chapter_(\d+)\.md", f))]
    return max(chapter_ids, default=0)

def get_last_chapter_tail(chapter_id: int, num_paragraphs: int = 2):
    if chapter_id <= 1:
        return None
    for name in [f"outputs/chapter_{chapter_id-1:02d}_final.md", f"outputs/chapter_{chapter_id-1:02d}.md"]:
        if os.path.exists(name):
            with open(name, "r", encoding="utf-8") as f:
                paragraphs = [p.strip() for p in f.read().strip().split("\n\n") if p.strip()]
                return "\n\n".join(paragraphs[-num_paragraphs:]) if paragraphs else None
    return None

def print_objective_block(objective: str):
    print("\U0001F4AC 本章子目標內容如下：")
    print("=" * 40)
    for line in objective.strip().splitlines():
        print(textwrap.fill(line, width=80))
    print("=" * 40 + "\n")

def ensure_objective_exists(main_goal, chapter_id):
    objective = get_chapter_objective(main_goal, chapter_id)
    if objective:
        return objective

    print("\U0001F3AF 為你規劃章節子目標中...\n")
    summary_path = f"summaries/chapter_{chapter_id-1:02d}_summary.md"
    if not os.path.exists(summary_path):
        print("\u26A0\uFE0F 找不到上一章摘要，無法生成子目標。")
        return None

    with open(summary_path, "r", encoding="utf-8") as f:
        summary_text = f.read()

    suggestions = plot_agent.suggest_next_objectives(summary_text, n=3)
    print("\U0001F4CA 以下是建議的章節方向：\n")
    print(suggestions)

    choice = input("\n請輸入你要使用的子目標描述（可貼上或手動修改）：\n> ").strip()
    if choice:
        log_subgoals(main_goal, choice)  # 這裡仍呼叫 log_subgoals 寫入
        plot_agent.log_objective(chapter_id, choice)
        return choice
    else:
        print("\u26A0\uFE0F 未輸入內容，將跳過本章。")
        return None

def write_chapter(chapter_id: int):
    print(f"\n\U0001F4D8 開始撰寫第 {chapter_id} 章...\n")

    # 載入主目標（若不存在則要求）
    main_goal = load_main_goal()
    if chapter_id == 1 or not main_goal:
        main_goal = input("\n請輸入本次小說的主要目標（例如：伊澤潛入星環之塔找尋父親的禁咒研究）：\n> ")
        save_main_goal(main_goal)
        print("\n\U0001F3AF 為你規劃章節子目標中...\n")
        subgoals = suggest_subgoals(main_goal)
        log_subgoals(main_goal, subgoals)

    # 確保有章節目標
    objective = ensure_objective_exists(main_goal, chapter_id)
    if not objective:
        return

    print_objective_block(objective)

    # 載入 context snapshot（如果有）
    context = None
    if os.path.exists("context_snapshot.yaml"):
        with open("context_snapshot.yaml", "r", encoding="utf-8") as f:
            context = f.read()

    # 加入上一章結尾段落作為銜接
    prev_tail = get_last_chapter_tail(chapter_id)
    if prev_tail:
        context = (context or "") + f"\n\n【前章結尾銜接段落】\n{prev_tail}"

    # 產出初稿
    chapter_text = generate_chapter(
        character_path="main_character.yaml",
        world_path="world_setting.yaml",
        objective=objective,
        chapter_id=chapter_id,
        save_to=f"outputs/chapter_{chapter_id:02d}.md",
        context=context
    )

    print(f"\n\u2705 第 {chapter_id} 章初稿完成，以下是內容預覽：\n")
    print("=" * 30)
    print(chapter_text[:800])
    print("=" * 30)

    # 執行擴寫
    print("\n\U0001F6A7 執行擴寫並覆蓋原章節...\n")
    result = expand_chapter_file(f"outputs/chapter_{chapter_id:02d}.md")

    if result and "【改寫版本】" in result:
        final_text = result.split("【改寫版本】")[-1].strip()
        save_text(f"outputs/chapter_{chapter_id:02d}_final.md", final_text)
        print("\n\U0001F4D8 擴寫後定稿內容預覽：\n")
        print("=" * 30)
        print(final_text[:800])
        print("=" * 30)
        update_all_active_characters_memory(final_text, chapter_id)
    else:
        print("\u26A0\uFE0F 擴寫失敗或格式錯誤，已保留初稿於 outputs。")

    update_timeline()

def write_story_loop(start_chapter=None):
    print("\U0001F4DA 啟動小說連續創作模式！")
    current_chapter = start_chapter or find_last_chapter_id() + 1
    print(f"\U0001F4CD 目前最新章節：第 {current_chapter - 1} 章")
    print(f"\U0001F680 將從第 {current_chapter} 章開始寫作")

    while True:
        write_chapter(current_chapter)
        cont = input("\n\U0001F4DD 是否繼續寫下一章？(y/n): ").strip().lower()
        if cont != "y":
            print("\U0001F6D1 寫作結束，歡迎下次再來！")
            break
        current_chapter += 1
        update_timeline()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, help="從指定章節開始")
    args = parser.parse_args()
    write_story_loop(start_chapter=args.start)