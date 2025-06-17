"""章節生成代理 - 根據目標生成章節內容"""
import os
import yaml
from common import settings, utils
from .context_builder import ContextBuilder


class ChapterGeneratorAgent:
    def __init__(self):
        self.client = settings.CLIENT
        self.model = settings.GENERATION_MODEL

    def _build_prompt(self, objective: str, chapter_id: int, context: str = None):
        """建構章節生成的提示詞 - 使用 ContextBuilder"""
        context_builder = ContextBuilder(chapter_id, objective)
        return context_builder.build(context)

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