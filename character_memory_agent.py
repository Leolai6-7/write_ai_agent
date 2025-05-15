import os
import yaml
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

CHARACTER_DIR = "characters"
MEMORY_SUMMARY_FILE = "character_memory.yaml"

os.makedirs(CHARACTER_DIR, exist_ok=True)


def load_yaml(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def save_yaml(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True)


def summarize_character_change(name: str, text: str) -> str:
    prompt = f"""
你是一位小說分析師，請從以下小說段落中，總結角色「{name}」的行為變化、心理變化與重要記憶。請以 1~3 條列點方式清楚列出。
請避免虛構不存在的情節，僅根據提供文本推論。

【小說內容】
{text}

【角色記憶摘要】
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "你是一位嚴謹的小說角色心理分析師。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=500
    )
    return response.choices[0].message.content.strip()


def update_individual_character_file(name: str, chapter: int, memory: str):
    path = os.path.join(CHARACTER_DIR, f"{name}.yaml")
    data = load_yaml(path)
    data.setdefault("memory", [])
    data["memory"].append({"chapter": chapter, "event": memory})
    save_yaml(path, data)


def update_main_character_file(chapter: int, memory: str):
    data = load_yaml("main_character.yaml")
    data.setdefault("memory", [])
    data["memory"].append({"chapter": chapter, "event": memory})
    save_yaml("main_character.yaml", data)


def append_global_summary(name: str, chapter: int, memory: str):
    data = load_yaml(MEMORY_SUMMARY_FILE)
    data.setdefault(name, [])
    data[name].append({"chapter": chapter, "event": memory})
    save_yaml(MEMORY_SUMMARY_FILE, data)


def summarize_and_update_memory(name: str, text: str, chapter: int):
    print(f"🧠 分析角色「{name}」在第 {chapter} 章的變化...")
    memory_summary = summarize_character_change(name, text)
    print("🔎 擷取角色記憶摘要：\n" + memory_summary)

    if name == "伊澤":
        update_main_character_file(chapter, memory_summary)
    else:
        update_individual_character_file(name, chapter, memory_summary)

    append_global_summary(name, chapter, memory_summary)
    return memory_summary


# ✅ 固定流程統一化版本

def update_all_active_characters_memory(chapter_text: str, chapter_id: int):
    active_characters = ["伊澤", "莉亞"]  # 可以從設定檔中讀取
    for name in active_characters:
        summarize_and_update_memory(name, chapter_text, chapter_id)
        
# 🔧 用於生成 prompt 的主角記憶整合

def get_recent_main_character_memory(n: int = 3):
    data = load_yaml("main_character.yaml")
    memory = data.get("memory", [])[-n:]
    lines = [f"- 第 {m['chapter']} 章：{m['event']}" for m in memory if 'chapter' in m and 'event' in m]
    return "\n".join(lines)
