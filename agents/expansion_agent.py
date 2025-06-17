"""擴寫代理 - 將章節初稿擴寫為完整版本"""
from common import settings


class ExpansionAgent:
    def __init__(self):
        self.client = settings.CLIENT
        self.model = settings.EXPANSION_MODEL
    
    def _build_prompt(self, original_text: str):
        """建構擴寫提示詞"""
        prompt = (
            "以下是小說初稿，請你執行兩件事：\n"
            "1. 條列出可以增加細節、豐富描寫的部分（不少於 3 項）\n"
            "2. 根據原稿與這些補充建議，重新改寫成更完整、更具體的版本。\n\n"
            "請務必遵守以下規則：\n"
            "- 【改寫版本】必須達到至少 2000 字（約 3000 個中文字元）\n"
            "- 敘述需細膩，描述具體，節奏不急促\n"
            "- 請勿省略過程或略過劇情橋段\n"
            "- 避免簡略收尾，請完整鋪陳每段描寫\n\n"
            "請嚴格按照此格式輸出：\n"
            "【擴寫建議】\n...\n\n【改寫版本】\n..."
        )
        return prompt + "\n\n" + original_text

    def run(self, draft_content: str) -> str:
        """接收初稿內容，回傳擴寫後的版本"""
        print("✍️  正在擴寫章節...")
        prompt = self._build_prompt(draft_content)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位專業小說編輯，擅長細節擴寫與章節潤飾。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4096
        )
        result = response.choices[0].message.content.strip()

        # Debug: 顯示回傳結果預覽
        print("\n🧪 GPT 回傳結果預覽（前 300 字）：")
        print(result[:300])

        if "【改寫版本】" in result:
            final_text = result.split("【改寫版本】")[-1].strip()
            print("✅ 擴寫完成。")
            return final_text
        else:
            print("⚠️ 擴寫失敗：未在回傳中找到【改寫版本】標記。")
            return draft_content  # 擴寫失敗時回傳原文