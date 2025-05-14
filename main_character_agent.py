import yaml
import os
from openai import OpenAI

class MainCharacterAgent:
    def __init__(self, path="main_character.yaml"):
        self.path = path
        self.client = OpenAI()
        self.character = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"{self.path} 不存在")
        with open(self.path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.dump(self.character, f, allow_unicode=True)

    def get_field(self, field):
        return self.character.get(field, f"⚠️ 欄位「{field}」不存在")

    def update_field(self, field, value, mode="append"):
        """
        更新某欄位：
        - append：若是 list 則追加（如 emotional_arc）
        - replace：直接覆蓋欄位（如 current_goals）
        """
        if mode == "append":
            if field not in self.character:
                self.character[field] = [value]
            elif isinstance(self.character[field], list):
                self.character[field].append(value)
            else:
                raise ValueError(f"欄位「{field}」不是 list，無法 append")
        elif mode == "replace":
            self.character[field] = value
        else:
            raise ValueError("mode 必須為 'append' 或 'replace'")
        self._save()
        print(f"✅ 已更新主角欄位「{field}」：{value}")

    def summarize_arc(self):
        """
        使用 GPT 自動總結目前的 emotional_arc 或背景變化
        """
        arc = self.character.get("emotional_arc", [])
        if not arc:
            return "❌ 尚無 emotional_arc 可摘要"

        content = "\n".join(arc)
        prompt = f"請根據以下主角心理變化紀錄，摘要出目前主角的情緒發展狀態：\n{content}"

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "你是一位小說總編輯，負責描寫主角的情緒弧線發展。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()

    def display_summary(self):
        """輸出完整主角卡（YAML 格式）"""
        return yaml.dump(self.character, allow_unicode=True)
