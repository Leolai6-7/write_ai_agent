"""擴寫代理 - 將章節初稿擴寫為完整版本"""
import os
from common import settings


class ExpansionAgent:
    def __init__(self):
        self.client = settings.CLIENT
        self.model = settings.EXPANSION_MODEL
    
    def _build_prompt(self, original_text: str):
        """建構擴寫提示詞"""
        prompt = (
            "你是一位專業小說編輯，你的任務是將以下【小說初稿】大幅擴寫成一個細節豐富、情感飽滿的【最終版本】。\n\n"
            "請嚴格遵守以下擴寫規則：\n"
            "1. **增加篇幅**：【最終版本】的字數必須**至少是【小說初稿】的兩倍**。這是硬性要求。\n"
            "2. **豐富描寫**：為場景增加環境細節（光影、聲音、氣味），為角色增加微表情和肢體動作。\n"
            "3. **深化內心**：深入挖掘主角在每個時刻的內心活動、回憶閃現和情緒波動，而不僅僅是他的行為。\n"
            "4. **強化對話**：讓角色對話更具個性，增加潛台詞和情感張力。\n"
            "5. **保持核心**：不得改變或刪減初稿中的核心情節和對話。\n\n"
            "請嚴格按照以下格式輸出，不要包含任何額外的解釋：\n"
            "【擴寫建議】\n"
            "- (在此處條列你計畫增加的3個具體細節)\n\n"
            "【最終版本】\n"
            "(在此處輸出擴寫後的完整小說內容)\n\n"
            "--- 小說初稿如下 ---\n"
            f"{original_text}"
        )
        return prompt

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

        # 詳細日誌記錄 - 診斷用
        log_path = os.path.join(settings.OUTPUTS_DIR, "expansion_log.txt")
        log_content = f"=== EXPANSION LOG ===\n時間: {__import__('datetime').datetime.now()}\n\n--- DRAFT INPUT ---\n{draft_content}\n\n--- LLM RAW OUTPUT ---\n{result}\n\n{'='*50}\n\n"
        os.makedirs(settings.OUTPUTS_DIR, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_content)
        
        # Debug: 顯示回傳結果預覽
        print("\n🧪 GPT 回傳結果預覽（前 300 字）：")
        print(result[:300])
        print(f"\n📝 完整結果已記錄至: {log_path}")

        # 改進的格式解析邏輯
        if "【最終版本】" in result:
            # 優先尋找「最終版本」標記
            final_text = result.split("【最終版本】")[-1].strip()
        elif "【改寫版本】" in result:
            # 備用：尋找舊格式「改寫版本」標記
            final_text = result.split("【改寫版本】")[-1].strip()
        else:
            # 如果都沒找到，嘗試尋找可能的分隔符號
            lines = result.split('\n')
            start_idx = -1
            for i, line in enumerate(lines):
                if any(keyword in line for keyword in ['最終版本', '改寫版本', '完整版本', '擴寫後']):
                    start_idx = i + 1
                    break
            
            if start_idx > 0:
                final_text = '\n'.join(lines[start_idx:]).strip()
                print(f"⚠️ 使用備用解析方法，從第 {start_idx} 行開始提取內容")
            else:
                print("❌ 擴寫失敗：無法找到任何版本標記，回傳原文")
                return draft_content
        
        # 驗證擴寫效果
        original_length = len(draft_content)
        final_length = len(final_text)
        expansion_ratio = final_length / original_length if original_length > 0 else 0
        
        print(f"📊 擴寫統計: 原文 {original_length} 字 -> 最終 {final_length} 字 (比例: {expansion_ratio:.1f}x)")
        
        if expansion_ratio < 1.5:
            print("⚠️ 警告：擴寫比例不足1.5倍，可能需要調整 Prompt")
        
        print("✅ 擴寫完成。")
        return final_text