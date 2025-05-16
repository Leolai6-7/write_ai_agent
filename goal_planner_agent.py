from openai import OpenAI
from dotenv import load_dotenv
import os
import yaml

load_dotenv()
client = OpenAI()

GOAL_PLAN_LOG = "objectives_expanded.yaml"


current_main_goal = None

def suggest_subgoals(main_goal: str, story_context: str = "") -> list:
    prompt = (
        "你是一位小說策劃顧問，擅長將一個主要故事目標拆解為 3 到 6 個子目標，"
        "以便在多章節中逐步推進故事發展。子目標應具備明確行動與情境，並能帶出人物互動或衝突。"
        "請列出子目標清單，每行一項，語氣簡潔。"
    )
    if story_context:
        prompt += f"\n\n【故事背景】\n{story_context}"

    prompt += f"\n\n【主要目標】\n{main_goal}\n\n【子目標建議】"

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "你是一位經驗豐富的小說故事規劃顧問。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=800
    )
    return response.choices[0].message.content.strip().split("\n")


def log_subgoals(main_goal: str, subgoals: list):
    if os.path.exists(GOAL_PLAN_LOG):
        with open(GOAL_PLAN_LOG, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data[main_goal] = subgoals
    with open(GOAL_PLAN_LOG, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True)


def load_subgoals(main_goal: str):
    if not os.path.exists(GOAL_PLAN_LOG):
        return []
    with open(GOAL_PLAN_LOG, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return data.get(main_goal, [])


def get_chapter_objective(main_goal: str, chapter_id: int):
    subgoals = load_subgoals(main_goal)
    if not subgoals:
        print("⚠️ 無子目標紀錄，請先建立。")
        return None
    if chapter_id <= len(subgoals):
        return subgoals[chapter_id - 1]
    print("⚠️ 所有子目標已用盡。請新增目標或中止寫作流程。")
    return None


if __name__ == "__main__":
    main_goal = input("請輸入主要故事目標：\n> ")
    context = input("（可選）請輸入故事背景摘要：\n> ")
    subgoals = suggest_subgoals(main_goal, context)
    print("\n🎯 子目標建議：\n")
    for g in subgoals:
        print("-", g)
    log_subgoals(main_goal, subgoals)
    print(f"\n✅ 子目標已記錄至：{GOAL_PLAN_LOG}")
    