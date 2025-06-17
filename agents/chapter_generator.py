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

        # 10. 寫作指令 (從舊版 prompt 複製)
        writing_instructions = """請從【前章結尾銜接段落】自然延續故事，並根據上述章節目標與背景撰寫本章小說內容，字數約為 800 字。

- 本章僅需描述主角朝向目標邁進的「一小段過程」，不需完成整個任務。
- 以具體的場景細節、人物之間的互動、主角的內心變化與情感流動為描寫重點。
- 敘事語氣請保持真摯、細膩，避免快速敘述事件進展。

請讓讀者透過細節感受故事氛圍與角色心理，而非直接交代任務進度。"""
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