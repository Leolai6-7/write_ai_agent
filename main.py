"""統一入口 - AI 小說家寫作流水線"""
import os
from common import settings, utils
from agents.goal_planner_agent import GoalPlannerAgent
from agents.chapter_generator import ChapterGeneratorAgent
from agents.expansion_agent import ExpansionAgent
from agents.summarizer_agent import SummarizerAgent


def main_workflow():
    print("📖 歡迎使用 AI 小說家寫作流水線")
    
    # 1. 讀取並確認主要目標
    main_goal_data = utils.load_yaml(settings.MAIN_GOAL_FILE)
    main_goal = main_goal_data.get("main_goal") if main_goal_data else None
    
    if not main_goal:
        print(f"❌ 在 {settings.MAIN_GOAL_FILE} 中找不到 'main_goal'。")
        main_goal = input("請手動輸入主要故事目標：\n> ")
    print(f"🚀 當前主要目標：{main_goal}\n")

    # 2. (可選) 執行目標規劃
    # 這裡可以加入邏輯，判斷是否需要重新規劃
    planner = GoalPlannerAgent()
    subgoals = planner.run(main_goal=main_goal)
    if not subgoals:
        print("❌ 目標規劃失敗，流程中止。")
        return
    
    print("\n" + "="*50)
    print("🚀 寫作流水線啟動！")
    print("="*50 + "\n")

    # 3. 實例化所有代理
    generator = ChapterGeneratorAgent()
    expander = ExpansionAgent()
    summarizer = SummarizerAgent()

    # 4. 為每個子目標執行完整的寫作循環
    for i, objective in enumerate(subgoals):
        chapter_id = i + 1
        print(f"--- 正在處理第 {chapter_id} 章：{objective} ---")

        # A. 生成初稿
        draft_content = generator.run(objective=objective, chapter_id=chapter_id)
        draft_path = os.path.join(settings.OUTPUTS_DIR, f"chapter_{chapter_id:02d}_draft.md")
        utils.save_text(draft_path, draft_content)
        print(f"📄 初稿已儲存至：{draft_path}")

        # B. 擴寫與精煉
        final_content = expander.run(draft_content)
        final_path = os.path.join(settings.OUTPUTS_DIR, f"chapter_{chapter_id:02d}_final.md")
        utils.save_text(final_path, final_content)
        print(f"📂 最終版本已儲存至：{final_path}")

        # C. 生成並儲存摘要
        summary_text = summarizer.run(final_content)
        summary_path = os.path.join(settings.SUMMARIES_DIR, f"chapter_{chapter_id:02d}_summary.md")
        utils.save_text(summary_path, summary_text)
        print(f"📝 摘要已儲存至：{summary_path}")

        # D. 更新角色記憶和時間線
        utils.update_all_active_characters_memory(final_content, chapter_id)
        utils.update_timeline()
        print(f"🧠 角色記憶已更新")
        print(f"🌍 故事時間線已更新")
        
        print(f"\n--- 第 {chapter_id} 章處理完畢 ---\n")

    print("🎉 全部章節處理完畢！寫作流水線執行成功！")


if __name__ == "__main__":
    main_workflow()