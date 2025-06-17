"""摘要代理 - 專門負責章節摘要工作"""
from common import settings


class SummarizerAgent:
    def __init__(self):
        self.client = settings.CLIENT
        self.model = settings.SUMMARY_MODEL

    def run(self, chapter_text: str) -> str:
        """接收章節內容，回傳摘要"""
        print("✍️  正在生成摘要...")
        system_prompt = "你是一位小說總編輯，請將以下章節摘要為三件重要事件與主角心理變化，格式條列。"
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chapter_text}
            ],
            temperature=0.7,
            max_tokens=500
        )
        summary = response.choices[0].message.content.strip()
        print("✅ 摘要完成。")
        return summary