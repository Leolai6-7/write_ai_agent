"""通用工具函式模組"""
import os

import yaml
from common import settings


# ========= 基本檔案操作 =========

def load_yaml(path):
    """安全地讀取 YAML 檔案"""
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_yaml(path, data):
    """將資料儲存為 YAML 檔案，自動建立目錄"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True)


def save_text(path, content):
    """將文字儲存為檔案，自動建立目錄"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def load_text(path):
    """安全地讀取文字檔案"""
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ========= 角色相關工具 =========

def tool_get_main_character(args=None):
    """取得主角設定"""
    return load_yaml(settings.MAIN_CHARACTER_FILE) or {}


def get_character(name: str):
    """取得指定角色設定"""
    path = os.path.join(settings.CHARACTERS_DIR, f"{name}.yaml")
    return load_yaml(path)


def list_characters():
    """列出所有角色名稱"""
    if not os.path.exists(settings.CHARACTERS_DIR):
        return []
    files = [f for f in os.listdir(settings.CHARACTERS_DIR) if f.endswith('.yaml')]
    return [f[:-5] for f in files]  # 移除 .yaml 副檔名


# ========= 記憶管理相關 =========

def summarize_character_change(name: str, text: str) -> str:
    """總結角色在章節中的變化"""
    prompt = f"""
你是一位小說分析師，請從以下小說段落中，總結角色「{name}」的行為變化、心理變化與重要記憶。請以 1~3 條列點方式清楚列出。
請避免虛構不存在的情節，僅根據提供文本推論。

【小說內容】
{text}

【角色記憶摘要】
"""
    response = settings.CLIENT.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "你是一位嚴謹的小說角色心理分析師。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=500
    )
    return response.choices[0].message.content.strip()


def update_main_character_memory(chapter: int, memory: str):
    """更新主角記憶"""
    data = load_yaml(settings.MAIN_CHARACTER_FILE) or {}
    data.setdefault("memory", [])
    data["memory"].append({"chapter": chapter, "event": memory})
    save_yaml(settings.MAIN_CHARACTER_FILE, data)


def update_character_memory(name: str, chapter: int, memory: str):
    """更新指定角色記憶"""
    path = os.path.join(settings.CHARACTERS_DIR, f"{name}.yaml")
    data = load_yaml(path) or {}
    data.setdefault("memory", [])
    data["memory"].append({"chapter": chapter, "event": memory})
    save_yaml(path, data)


def get_recent_main_character_memory(n: int = 3):
    """取得主角最近的記憶"""
    data = load_yaml(settings.MAIN_CHARACTER_FILE) or {}
    memory = data.get("memory", [])[-n:]
    lines = [f"- 第 {m['chapter']} 章：{m['event']}" for m in memory if 'chapter' in m and 'event' in m]
    return "\n".join(lines)


def get_recent_other_characters_memory(n: int = 2):
    """取得其他角色最近的記憶"""
    active_file = "active_characters.yaml"
    active_data = load_yaml(active_file) or {}
    active_characters = active_data.get("active", [])
    
    section = ""
    for name in active_characters:
        data = get_character(name)
        if data:
            memory = data.get("memory", [])[-n:]
            lines = [f"- 第 {m['chapter']} 章：{m['event']}" for m in memory if 'chapter' in m and 'event' in m]
            if lines:
                section += f"{name}：\n" + "\n".join(lines) + "\n\n"
    return section.strip()


def get_recent_timeline(n: int = 5):
    """取得最近的時間線"""
    if not os.path.exists(settings.TIMELINE_FILE):
        return ""
    with open(settings.TIMELINE_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return "\n".join(lines[-n:])


# ========= 時間線管理 =========

def load_objectives(objective_path=None):
    """載入章節目標"""
    if objective_path is None:
        objective_path = settings.OBJECTIVES_EXPANDED_FILE
    if not os.path.exists(objective_path):
        return {}
    with open(objective_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_summary(chapter_id):
    """載入章節摘要"""
    path = os.path.join(settings.SUMMARIES_DIR, f"chapter_{chapter_id:02d}_summary.md")
    return load_text(path)


def generate_timeline_markdown():
    """生成時間線 Markdown"""
    objectives = load_objectives()
    timeline_md = "# 📖 小說劇情時間線\n\n"

    # 解析 objectives_expanded.yaml 的結構，找到正確的目標
    target_objectives = None
    
    # 尋找當前主要目標對應的子目標列表
    main_goal_data = load_yaml(settings.MAIN_GOAL_FILE)
    current_main_goal = main_goal_data.get("main_goal") if main_goal_data else None
    
    if current_main_goal and current_main_goal in objectives:
        target_objectives = objectives[current_main_goal]
    else:
        # 如果找不到匹配的目標，使用最後一個非空的列表
        for key, value in objectives.items():
            if isinstance(value, list) and len(value) > 0 and value[0]:  # 確保不是空字符串
                target_objectives = value

    if target_objectives:
        for i, obj in enumerate(target_objectives):
            chapter_id = i + 1
            summary = load_summary(chapter_id)
            
            timeline_md += f"## 第 {chapter_id} 章\n"
            timeline_md += f"**章節目標：** {obj}\n\n"
            if summary:
                timeline_md += f"**章節摘要：**\n{summary}\n"
            else:
                timeline_md += "*⚠️ 本章尚無摘要。*\n"
            timeline_md += "\n---\n\n"

    return timeline_md


def update_timeline():
    """更新時間線"""
    md = generate_timeline_markdown()
    save_text(settings.TIMELINE_FILE, md)
    print(f"✅ 劇情時間線已更新至 {settings.TIMELINE_FILE}")


def update_all_active_characters_memory(chapter_text: str, chapter_id: int):
    """更新所有活躍角色的記憶"""
    active_file = "active_characters.yaml"
    active_data = load_yaml(active_file) or {}
    active_characters = active_data.get("active", [])
    
    for name in active_characters:
        memory_summary = summarize_character_change(name, chapter_text)
        if name == "伊澤":  # 主角
            update_main_character_memory(chapter_id, memory_summary)
        else:
            update_character_memory(name, chapter_id, memory_summary)