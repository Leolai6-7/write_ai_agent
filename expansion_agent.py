# ✍️ expansion_agent.py
# 擴寫小說初稿，提出細節建議並改寫為完整版本，覆寫原始章節，並自動更新 timeline

import openai
from dotenv import load_dotenv
import os
from timeline_generator import update_timeline

load_dotenv()
client = openai.OpenAI()


def expand_chapter_text(original_text: str):
    """
    接收原始小說內容，回傳擴寫建議與改寫版本
    """
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


    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "你是一位專業小說編輯，擅長細節擴寫與章節潤飾。"},
            {"role": "user", "content": prompt + "\n\n" + original_text}
        ],
        temperature=0.7,
        max_tokens=4096
    )

    result = response.choices[0].message.content.strip()

    # ✅ debug: 印出前幾百字，確保真的有結果
    print("\n🧪 GPT 回傳結果預覽（前 300 字）：\n")
    print(result[:300])
    
    return result




def expand_chapter_file(path):
    if not os.path.exists(path):
        print(f"❌ 找不到章節檔案：{path}")
        return None

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()
    result = expand_chapter_text(original)

    # 儲存擴寫版本為 _expanded 檔案
    save_path = path.replace(".md", "_expanded.md")
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"✅ 擴寫版本已儲存至：{save_path}")

    # 擷取【改寫版本】段落，覆蓋原始章節為定稿
    if result and "【改寫版本】" in result:
        final_text = result.split("【改寫版本】")[-1].strip()
        with open(path, "w", encoding="utf-8") as f:
            f.write(final_text)
        print(f"✅ 原始章節已覆寫為擴寫後定稿：{path}")
        update_timeline()
    else:
        print("⚠️ 未找到【改寫版本】，未覆寫原始章節。\n🧪 GPT 回傳如下：\n")
        print(result[:500])

    return result



if __name__ == "__main__":
    path = input("請輸入要擴寫的章節檔案路徑（例如 outputs/chapter_03.md）：\n> ")
    result = expand_chapter_file(path)
    if result:
        print("\n✅ 擴寫完成：\n")
        print(result)
