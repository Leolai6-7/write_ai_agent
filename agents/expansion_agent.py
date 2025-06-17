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
            "1. 條列出可以強化劇情推進、角色發展或對話張力的部分（不少於 3 項）\n"
            "2. 根據原稿與這些補充建議，重新改寫成更完整、更生動的版本。\n\n"
            "請務必遵守以下規則：\n"
            "- 【改寫版本】必須達到至少 2000 字（約 3000 個中文字元）\n"
            "- 優先強化：角色心理變化、對話衝突、劇情轉折\n"
            "- 環境描寫應服務於劇情，避免過度裝飾性描述\n"
            "- 確保每個場景都推進故事發展或深化角色\n"
            "- 對話要體現角色個性，避免過於正式或相似\n"
            "- 節奏控制：行動場面40%，對話30%，心理描寫20%，環境描寫10%\n\n"
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