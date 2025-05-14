import yaml
import os
from openai import OpenAI

class CharacterManagerAgent:
    def __init__(self, character_file="character_memory.yaml"):
        self.character_file = character_file
        self.client = OpenAI()
        self.characters = self._load_characters()

    def _load_characters(self):
        if not os.path.exists(self.character_file):
            return {}
        with open(self.character_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _save_characters(self):
        with open(self.character_file, "w", encoding="utf-8") as f:
            yaml.dump(self.characters, f, allow_unicode=True)

    def get_character(self, name):
        return self.characters.get(name, f"❌ 找不到角色：{name}")

    def edit_character(self, name, updates: dict):
        if name not in self.characters:
            return f"❌ 找不到角色：{name}"
        self.characters[name].update(updates)
        self._save_characters()
        return f"✏️ 角色「{name}」已更新。"

    def list_characters(self):
        return list(self.characters.keys())

    def create_character_from_instruction(self, instruction: str):
        """使用 LLM 根據自然語言 instruction 建立角色卡並存入記憶庫"""
        system_prompt = """
你是一位專業奇幻小說角色設計師，請根據使用者指令創造一位角色，並以 YAML 格式回覆，包含以下欄位：

name: 角色名稱
race: 種族（人類、精靈、矮人等）
occupation: 職業
role_in_story: 在小說中的功能（如主角的朋友、敵人、導師等）
personality:
  - 個性形容詞
  - ...
background: 簡短背景故事
"""

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": instruction}
            ],
            temperature=0.8,
            max_tokens=600
        )

        raw_yaml = response.choices[0].message.content.strip()
        try:
            character_data = yaml.safe_load(raw_yaml)
            name = character_data.get("name", "未知角色")
            if name in self.characters:
                return f"⚠️ 角色「{name}」已存在，請使用 edit_character 修改。"
            self.characters[name] = character_data
            self._save_characters()
            return f"✅ 已新增角色「{name}」\n\n{yaml.dump(character_data, allow_unicode=True)}"
        except yaml.YAMLError as e:
            return f"❌ YAML 解析錯誤：{e}"
    def summarize_character_arc(self, name):
        """使用 GPT 生成該角色目前的性格與故事進程摘要"""
        character = self.get_character(name)
        if isinstance(character, str):
            return character  # 找不到角色

        system_prompt = "你是一位小說總編輯，請根據角色卡提供該角色的故事弧線摘要，涵蓋：性格、經歷、目前心理變化趨勢。"

        user_prompt = f"角色設定如下：\n{yaml.dump(character, allow_unicode=True)}"

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        return response.choices[0].message.content.strip()

    def check_consistency(self, name, scene_text):
        """檢查角色在指定劇情段落中是否有違反其性格（OOC）"""
        character = self.get_character(name)
        if isinstance(character, str):
            return character

        system_prompt = """
你是一位小說評論者，請根據角色設定判斷以下段落中角色是否有 OOC（Out of Character）行為。
請指出不一致的地方與建議修改方式。
"""

        user_prompt = f"角色設定如下：\n{yaml.dump(character, allow_unicode=True)}\n\n劇情段落如下：\n{scene_text}"

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        return response.choices[0].message.content.strip()

    def assign_relationship(self, name1, name2, relation):
        """在角色卡中建立關係圖（雙方）"""
        for name in [name1, name2]:
            if name not in self.characters:
                return f"❌ 找不到角色：{name}"

        # 建立或更新雙向關係
        self.characters[name1].setdefault("relationships", {})[name2] = relation
        self.characters[name2].setdefault("relationships", {})[name1] = self._reverse_relation(relation)

        self._save_characters()
        return f"✅ 已建立關係：「{name1}」與「{name2}」為「{relation}」"

    def _reverse_relation(self, relation):
        """簡單反轉關係名稱，可擴充詞庫"""
        reverse_map = {
            "導師": "學生",
            "學生": "導師",
            "朋友": "朋友",
            "敵人": "敵人",
            "父親": "子女",
            "母親": "子女",
            "子女": "父母",
        }
        return reverse_map.get(relation, relation)

    def delete_character(self, name):
        if name in self.characters:
            del self.characters[name]
            self._save_characters()
            return f"🗑️ 角色「{name}」已刪除。"
        return f"❌ 找不到角色：{name}"

