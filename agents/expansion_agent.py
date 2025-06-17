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
            "你是一位資深小說編輯，專門負責將簡短的初稿擴寫成豐富精彩的完整章節。\n\n"
            "【擴寫要求 - 必須嚴格執行】\n"
            "1. **篇幅強制要求**：最終版本必須達到原稿的**2.5倍字數**，這是不可商量的硬性指標\n"
            "2. **場景豐富化**：每個場景都要增加具體的動作序列、環境變化、聲音效果\n"
            "3. **對話深度擴展**：每段對話後必須加入角色的動作反應、表情變化、心理活動\n"
            "4. **感官細節密集**：大量增加視覺、聽覺、觸覺、嗅覺的具體描述\n"
            "5. **心理層次挖掘**：將每個心理變化都擴展成完整的思考過程或回憶片段\n"
            "6. **時間節奏控制**：將原稿中快速的情節轉換慢化成詳細的過程描述\n\n"
            "【具體擴寫策略】\n"
            "- 將每句對話擴展成包含動作、表情、語調的完整描述\n"
            "- 將每個動作分解成具體的步驟和細節\n"
            "- 將每個場景轉換增加過渡描述和環境變化\n"
            "- 將每個情緒反應深化成內心獨白或回憶觸發\n\n"
            "請按此格式輸出：\n"
            "【擴寫策略】\n"
            "- (條列3-5個具體的擴寫重點)\n\n"
            "【最終版本】\n"
            "(擴寫後的完整內容 - 必須達到2.5倍字數)\n\n"
            "=== 待擴寫初稿 ===\n"
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
            final_text = result.split("【最終版本】")[-1].strip()
        elif "【改寫版本】" in result:
            final_text = result.split("【改寫版本】")[-1].strip()
        else:
            # 嘗試尋找其他可能的標記
            lines = result.split('\n')
            start_idx = -1
            for i, line in enumerate(lines):
                if any(keyword in line for keyword in ['最終版本', '改寫版本', '完整版本', '擴寫後', '最終稿']):
                    start_idx = i + 1
                    break
            
            if start_idx > 0:
                final_text = '\n'.join(lines[start_idx:]).strip()
                print(f"⚠️ 使用備用解析方法，從第 {start_idx} 行開始提取內容")
            else:
                print("❌ 擴寫失敗：無法找到任何版本標記，回傳原文")
                return draft_content
        
        # 驗證擴寫效果並動態調整警告閾值
        original_length = len(draft_content)
        final_length = len(final_text)
        expansion_ratio = final_length / original_length if original_length > 0 else 0
        
        print(f"📊 擴寫統計: 原文 {original_length} 字 -> 最終 {final_length} 字 (比例: {expansion_ratio:.1f}x)")
        
        if expansion_ratio < 2.0:
            print(f"⚠️ 警告：擴寫比例{expansion_ratio:.1f}x未達目標2.5x，下次迭代可進一步優化")
        elif expansion_ratio >= 2.5:
            print("🎯 優秀：達到2.5x目標擴寫比例！")
        else:
            print("✅ 良好：擴寫比例超過2.0x")
        
        print("✅ 擴寫完成。")
        return final_text