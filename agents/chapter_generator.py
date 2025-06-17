"""章節生成代理 - 根據目標生成章節內容"""
import os
import yaml
from common import settings, utils


class ChapterGeneratorAgent:
    def __init__(self):
        self.client = settings.CLIENT
        self.model = settings.GENERATION_MODEL

    def _get_previous_summary(self, chapter_id: int):
        """取得前一章的摘要"""
        if chapter_id <= 1:
            return None
        summary_path = os.path.join(settings.SUMMARIES_DIR, f"chapter_{chapter_id-1:02d}_summary.md")
        return utils.load_text(summary_path)

    def _build_prompt(self, objective: str, chapter_id: int, context: str = None):
        """建構章節生成的提示詞 - 完整重現舊版功能"""
        print("  - 正在建立寫作上下文...")
        prompt_parts = []

        # 1. 故事現況快照
        snapshot_data = utils.load_yaml(settings.CONTEXT_SNAPSHOT_FILE)
        if snapshot_data and snapshot_data.get("summary"):
            prompt_parts.append(f"【故事現況摘要】\n{snapshot_data['summary']}")

        # 2. 額外上下文 (如果有的話)
        if context:
            prompt_parts.append(context)

        # 3. 前情提要
        summary = self._get_previous_summary(chapter_id)
        if summary:
            prompt_parts.append(f"【前情提要】\n{summary}")

        # 4. 本章目標
        prompt_parts.append(f"【故事目標】\n{objective}")

        # 5. 主角設定
        main_char = utils.tool_get_main_character({})
        if main_char:
            prompt_parts.append(f"【主角設定】\n{yaml.dump(main_char, allow_unicode=True)}")

        # 6. 主角記憶
        recent_memory = utils.get_recent_main_character_memory()
        if recent_memory:
            prompt_parts.append(f"【主角記憶】\n{recent_memory}")

        # 7. 其他角色記憶
        others_memory = utils.get_recent_other_characters_memory()
        if others_memory:
            prompt_parts.append(f"【其他角色記憶】\n{others_memory}")

        # 8. 劇情發展摘要
        timeline = utils.get_recent_timeline()
        if timeline:
            prompt_parts.append(f"【劇情發展摘要】\n{timeline}")

        # 9. 世界觀設定
        world = utils.load_yaml(settings.WORLD_SETTING_FILE)
        if world:
            prompt_parts.append(f"【世界觀設定】\n{yaml.dump(world, allow_unicode=True)}")

        # 10. 角色對話指引
        dialogue_guidance = ""
        if main_char and main_char.get("speaking_style"):
            dialogue_guidance = f"""
【角色對話指引】
- 主角伊澤：{main_char['speaking_style']}，對話應簡潔、內斂，多思考少說話
- 其他角色應與主角形成對比，各具特色的說話方式
- 避免所有角色說話風格相同或過於正式"""

        # 11. 寫作指令 (優化版)
        writing_instructions = f"""請從【前章結尾銜接段落】自然延續故事，並根據上述章節目標與背景撰寫本章小說內容，字數約為 800 字。

- 本章僅需描述主角朝向目標邁進的「一小段過程」，不需完成整個任務。
- 重點強化：角色心理變化、對話張力、劇情轉折
- 場景描寫應推進劇情，避免純裝飾性描述
- 敘事語氣請保持真摯、細膩，節奏張弛有度
- 節奏比例：具體行動50%，內心思考30%，環境描寫20%{dialogue_guidance}

請讓讀者透過角色行動與對話感受故事推進與角色成長。"""
        prompt_parts.append(writing_instructions)

        # 將所有部分用換行符連接起來
        return "\n\n".join(prompt_parts)

    def run(self, objective: str, chapter_id: int, context: str = None) -> str:
        """執行章節生成"""
        print(f"✍️  正在為第 {chapter_id} 章生成初稿...")
        prompt = self._build_prompt(objective, chapter_id, context)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=2000
        )
        
        chapter_text = response.choices[0].message.content.strip()
        print(f"✅ 第 {chapter_id} 章初稿完成。")
        return chapter_text