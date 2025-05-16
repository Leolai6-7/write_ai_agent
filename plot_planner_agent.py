from openai import OpenAI
import yaml
import os

client = OpenAI()

class PlotPlannerAgent:
    def __init__(self, main_char_path="main_character.yaml", objective_log_path="objectives.yaml"):
        with open(main_char_path, "r", encoding="utf-8") as f:
            self.main_char = yaml.safe_load(f)
        self.objective_log_path = objective_log_path

    def suggest_next_objectives(self, summary_text: str, n=3):
        system_prompt = (
            "你是一位奇幻小說編劇，根據前情摘要與主角性格，請提出接下來可能的發生的故事與轉折，條列 "
            f"{n} 條，每條不超過 200 字，包含可能出現新的人物、物品、事件等。"
        )
        user_prompt = f"【前情提要】\n{summary_text}\n\n【主角性格】\n{', '.join(self.main_char.get('personality', []))}"

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()

    def log_objective(self, chapter_id: int, objective: str):
        """
        將該章節的目標寫入 objectives.yaml，格式：
        01: 主角獲得禁咒殘片
        02: 與芙蕾雅首次心理衝突
        """
        path = self.objective_log_path
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        data[f"{chapter_id:02d}"] = objective

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

        print(f"✅ 已儲存章節 {chapter_id} 的目標至 {path}")
