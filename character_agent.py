import yaml
import os

class CharacterAgent:
    def __init__(self, character_file="character_memory.yaml"):
        self.character_file = character_file
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

    def add_character(self, info):
        name = info.get("name")
        if name in self.characters:
            return f"⚠️ 角色「{name}」已存在，請使用 edit_character() 來修改。"
        self.characters[name] = info
        self._save_characters()
        return f"✅ 角色「{name}」已新增！"

    def edit_character(self, name, updates):
        if name not in self.characters:
            return f"❌ 找不到角色：{name}"
        self.characters[name].update(updates)
        self._save_characters()
        return f"✏️ 角色「{name}」已更新。"

    def list_characters(self):
        return list(self.characters.keys())
