from chapter_generator import generate_chapter
import os

def main():
    print("📖 歡迎使用小說創作 AI Agent")
    print("請輸入本章節目標，例如：")
    print("  主角抵達星環之塔，並與其他學徒產生魔法衝突。\n")

    # 輸入章節目標
    objective = input("📌 請輸入本章節目標：\n> ").strip()
    if not objective:
        print("❗ 章節目標不得為空。")
        return

    # 輸入章節編號
    try:
        chapter_id = int(input("\n📎 請輸入章節編號（如 5）：\n> ").strip())
    except ValueError:
        print("❗ 章節編號必須是數字。")
        return

    # 建立儲存檔案路徑
    output_path = f"outputs/chapter_{chapter_id:02d}.md"

    print("\n🧠 GPT 開始創作中，請稍候...\n")

    # 執行主函數
    chapter_text = generate_chapter(
        character_path="main_character.yaml",
        world_path="world_setting.yaml",
        objective=objective,
        chapter_id=chapter_id,
        save_to=output_path
    )

    print("✅ 小說段落生成完成，內容如下：\n")
    print("=" * 40)
    print(chapter_text)
    print("=" * 40)

    print(f"\n📁 小說儲存於：{output_path}")
    print(f"📝 摘要已存於：summaries/chapter_{chapter_id:02d}_summary.md")

if __name__ == "__main__":
    main()
