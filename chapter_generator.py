from openai import OpenAI
import yaml
from dotenv import load_dotenv
import os

# 初始化
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI()

# ========= 基本載入 =========

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_text(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# ========= Prompt 建構 =========

def build_prompt(main_char, world, objective, summary=None, context=None):
    prompt = ""

    if context:
        prompt += f"{context}\n\n"
        
    if summary:
        prompt += f"【前情提要】\n{summary}\n\n"

    prompt += f"【故事目標】\n{objective}\n\n"
    prompt += f"【主角設定】\n{yaml.dump(main_char, allow_unicode=True)}\n\n"
    prompt += f"【世界觀設定】\n{yaml.dump(world, allow_unicode=True)}\n\n"
    prompt += "請根據上述內容撰寫本章小說內容，語氣真摯，描述具體，約 800 字。"

    return prompt

# ========= 摘要章節內容 =========

def summarize_chapter(chapter_text: str):
    system_prompt = "你是一位小說總編輯，請將以下章節摘要為三件重要事件與主角心理變化，格式條列。"
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chapter_text}
        ],
        temperature=0.7,
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

# ========= 主函數 =========

def generate_chapter(character_path, world_path, objective, chapter_id=None, save_to=None, context=None):

    # 載入角色與世界觀設定
    character = load_yaml(character_path)
    world = load_yaml(world_path)

    # 載入前情提要（若提供章節編號）
    summary = None
    if chapter_id and chapter_id > 1:
        summary_path = f"summaries/chapter_{chapter_id-1:02d}_summary.md"
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = f.read()

    # 建立 prompt
    prompt = build_prompt(character, world, objective, summary=summary, context=context)

    # 生成小說內容
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=2000
    )

    chapter_text = response.choices[0].message.content.strip()

    # 儲存章節
    if save_to:
        os.makedirs(os.path.dirname(save_to), exist_ok=True)
        save_text(save_to, chapter_text)

    # 生成摘要
    if chapter_id:
        summary_text = summarize_chapter(chapter_text)
        os.makedirs("summaries", exist_ok=True)
        summary_path = f"summaries/chapter_{chapter_id:02d}_summary.md"
        save_text(summary_path, summary_text)

    return chapter_text
