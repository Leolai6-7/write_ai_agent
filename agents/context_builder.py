"""上下文建構器 - 專門負責收集和組裝寫作上下文"""
import os
import yaml
from common import settings, utils


class ContextBuilder:
    def __init__(self, chapter_id: int, objective: str):
        self.chapter_id = chapter_id
        self.objective = objective
        self.prompt_parts = []

    def _add_story_snapshot(self):
        """添加故事現況快照"""
        snapshot_data = utils.load_yaml(settings.CONTEXT_SNAPSHOT_FILE)
        if snapshot_data and snapshot_data.get("summary"):
            self.prompt_parts.append(f"【故事現況摘要】\n{snapshot_data['summary']}")

    def _add_previous_summary(self):
        """添加前情提要"""
        if self.chapter_id <= 1:
            return
        summary_path = os.path.join(settings.SUMMARIES_DIR, f"chapter_{self.chapter_id-1:02d}_summary.md")
        summary = utils.load_text(summary_path)
        if summary:
            self.prompt_parts.append(f"【前情提要】\n{summary}")

    def _add_chapter_objective(self):
        """添加本章目標"""
        # 讀取主要目標
        main_goal_data = utils.load_yaml(settings.MAIN_GOAL_FILE)
        main_goal = main_goal_data.get("main_goal") if main_goal_data else None
        
        if main_goal:
            self.prompt_parts.append(f"【終極使命】\n{main_goal}")
        
        self.prompt_parts.append(f"【本章任務】\n{self.objective}
        
        ⚠️ 重要提醒：每一章都必須朝向【終極使命】推進，不可偏離主線！")

    def _add_main_character(self):
        """添加主角設定"""
        main_char = utils.tool_get_main_character({})
        if main_char:
            self.prompt_parts.append(f"【主角設定】\n{yaml.dump(main_char, allow_unicode=True)}")
        return main_char

    def _add_character_memories(self):
        """添加角色記憶"""
        # 主角記憶
        recent_memory = utils.get_recent_main_character_memory()
        if recent_memory:
            self.prompt_parts.append(f"【主角記憶】\n{recent_memory}")

        # 其他角色記憶
        others_memory = utils.get_recent_other_characters_memory()
        if others_memory:
            self.prompt_parts.append(f"【其他角色記憶】\n{others_memory}")

    def _add_timeline(self):
        """添加劇情發展摘要"""
        timeline = utils.get_recent_timeline()
        if timeline:
            self.prompt_parts.append(f"【劇情發展摘要】\n{timeline}")

    def _add_world_setting(self):
        """添加世界觀設定"""
        world = utils.load_yaml(settings.WORLD_SETTING_FILE)
        if world:
            self.prompt_parts.append(f"【世界觀設定】\n{yaml.dump(world, allow_unicode=True)}")

    def _add_dialogue_guidance(self, main_char):
        """添加角色對話指引"""
        if not main_char or not main_char.get("speaking_style"):
            return

        dialogue_guidance = f"""
【角色對話指引】
- 主角伊澤：{main_char['speaking_style']}，對話應簡潔、內斂，多思考少說話
- 其他角色應與主角形成對比，各具特色的說話方式
- 避免所有角色說話風格相同或過於正式"""
        
        return dialogue_guidance

    def _add_writing_instructions(self, dialogue_guidance=""):
        """添加寫作指令"""
        writing_instructions = f"""請從【前章結尾銜接段落】自然延續故事，並根據上述章節目標與背景撰寫本章小說內容，字數約為 800 字。

- 本章僅需描述主角朝向目標邁進的「一小段過程」，不需完成整個任務。
- 重點強化：角色心理變化、對話張力、劇情轉折
- 場景描寫應推進劇情，避免純裝飾性描述
- 敘事語氣請保持真摯、細膩，節奏張弛有度
- 節奏比例：具體行動50%，內心思考30%，環境描寫20%{dialogue_guidance}

請讓讀者透過角色行動與對話感受故事推進與角色成長。"""
        self.prompt_parts.append(writing_instructions)

    def build(self, context: str = None) -> str:
        """組裝並回傳最終的 prompt"""
        print("  - 正在建立寫作上下文...")
        
        # 按順序添加各個部分
        self._add_story_snapshot()
        
        # 額外上下文 (如果有的話)
        if context:
            self.prompt_parts.append(context)
            
        self._add_previous_summary()
        self._add_chapter_objective()
        
        # 添加角色相關信息
        main_char = self._add_main_character()
        self._add_character_memories()
        self._add_timeline()
        self._add_world_setting()
        
        # 添加對話指引和寫作指令
        dialogue_guidance = self._add_dialogue_guidance(main_char)
        self._add_writing_instructions(dialogue_guidance)
        
        # 將所有部分用換行符連接起來
        return "\n\n".join(self.prompt_parts)