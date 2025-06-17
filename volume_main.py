"""分卷式小說生成主流程"""
import os
import sys
from common import settings, utils
from agents.volume_architect_agent import VolumeArchitectAgent
from agents.enhanced_goal_planner import EnhancedGoalPlannerAgent
from agents.chapter_generator import ChapterGeneratorAgent
from agents.expansion_agent import ExpansionAgent
from agents.summarizer_agent import SummarizerAgent


class VolumeNovelPipeline:
    def __init__(self):
        self.architect = VolumeArchitectAgent()
        self.enhanced_planner = EnhancedGoalPlannerAgent()
        self.generator = ChapterGeneratorAgent()
        self.expander = ExpansionAgent()
        self.summarizer = SummarizerAgent()
        
    def initialize_novel_structure(self, main_goal: str, target_volumes: int = 3):
        """初始化小說整體架構"""
        print("🏗️ 正在初始化分卷式小說架構...")
        structure = self.architect.run(main_goal, target_volumes)
        return structure
    
    def plan_volume(self, volume_info: dict):
        """規劃單卷內容"""
        volume_name = volume_info["name"]
        volume_theme = volume_info["theme"] 
        start_chapter = volume_info["start_chapter"]
        end_chapter = volume_info["end_chapter"]
        
        print(f"\n📋 開始規劃《{volume_name}》...")
        planning = self.enhanced_planner.run_volume_planning(
            volume_name, volume_theme, start_chapter, end_chapter
        )
        return planning
    
    def generate_chapter_batch(self, chapter_objectives: list, start_chapter: int):
        """批量生成章節"""
        print(f"\n✍️ 開始批量生成章節 {start_chapter}-{start_chapter + len(chapter_objectives) - 1}...")
        
        for i, objective in enumerate(chapter_objectives):
            chapter_id = start_chapter + i
            print(f"\n--- 處理第 {chapter_id} 章 ---")
            
            try:
                # A. 生成初稿
                draft_content = self.generator.run(objective=objective, chapter_id=chapter_id)
                draft_path = os.path.join(settings.OUTPUTS_DIR, f"chapter_{chapter_id:03d}_draft.md")
                utils.save_text(draft_path, draft_content)
                print(f"📄 初稿已儲存至：{draft_path}")

                # B. 擴寫與精煉
                final_content = self.expander.run(draft_content)
                final_path = os.path.join(settings.OUTPUTS_DIR, f"chapter_{chapter_id:03d}_final.md")
                utils.save_text(final_path, final_content)
                print(f"📂 最終版本已儲存至：{final_path}")

                # C. 生成並儲存摘要
                summary_text = self.summarizer.run(final_content)
                summary_path = os.path.join(settings.SUMMARIES_DIR, f"chapter_{chapter_id:03d}_summary.md")
                utils.save_text(summary_path, summary_text)
                print(f"📝 摘要已儲存至：{summary_path}")

                # D. 更新角色記憶和時間線
                utils.update_all_active_characters_memory(final_content, chapter_id)
                utils.update_timeline()
                print(f"🧠 第 {chapter_id} 章記憶已更新")
                
            except Exception as e:
                print(f"❌ 第 {chapter_id} 章生成失敗: {e}")
                print("⏸️ 暫停流程，請檢查API配額或網路連接")
                return False
        
        return True
    
    def generate_volume(self, volume_planning: dict, batch_size: int = 10):
        """生成完整卷的內容"""
        volume_name = volume_planning["volume_name"]
        print(f"\n🚀 開始生成《{volume_name}》...")
        
        all_objectives = []
        start_chapter = None
        
        # 收集所有章節目標
        for arc_name, arc_data in volume_planning["arcs"].items():
            arc_objectives = arc_data["chapter_objectives"]
            all_objectives.extend(arc_objectives)
            
            if start_chapter is None:
                # 從第一個目標中提取起始章節號
                first_obj = arc_objectives[0] if arc_objectives else ""
                if "第" in first_obj and "章" in first_obj:
                    try:
                        start_chapter = int(first_obj.split("第")[1].split("章")[0])
                    except:
                        start_chapter = 1
        
        if start_chapter is None:
            start_chapter = 1
        
        print(f"📊 總計 {len(all_objectives)} 章待生成，從第 {start_chapter} 章開始")
        print(f"🔄 將以每批 {batch_size} 章的方式生成")
        
        # 分批生成
        for i in range(0, len(all_objectives), batch_size):
            batch_objectives = all_objectives[i:i + batch_size]
            batch_start = start_chapter + i
            
            print(f"\n📦 生成批次 {i//batch_size + 1}：第 {batch_start}-{batch_start + len(batch_objectives) - 1} 章")
            
            success = self.generate_chapter_batch(batch_objectives, batch_start)
            if not success:
                print(f"⚠️ 在第 {batch_start} 章附近停止，請解決問題後繼續")
                return False
                
            print(f"✅ 批次 {i//batch_size + 1} 完成")
        
        print(f"\n🎉 《{volume_name}》 生成完成！")
        return True

    def interactive_mode(self):
        """互動模式"""
        print("📚 歡迎使用分卷式AI小說生成系統")
        print("1. 初始化整體架構")
        print("2. 規劃特定卷")
        print("3. 生成特定卷")
        print("4. 查看已有規劃")
        
        choice = input("\n請選擇操作 (1-4): ")
        
        if choice == "1":
            main_goal = input("請輸入小說總目標：\n> ")
            volumes = int(input("計劃分幾卷？(建議3-5): ") or "3")
            self.initialize_novel_structure(main_goal, volumes)
            
        elif choice == "2":
            volume_name = input("請輸入卷名：\n> ")
            volume_theme = input("請輸入卷主題：\n> ")
            start_chapter = int(input("起始章節號：\n> "))
            end_chapter = int(input("結束章節號：\n> "))
            
            volume_info = {
                "name": volume_name,
                "theme": volume_theme,
                "start_chapter": start_chapter,
                "end_chapter": end_chapter
            }
            self.plan_volume(volume_info)
            
        elif choice == "3":
            planning_file = input("請輸入規劃文件名（如 volume_1_120_planning.yaml）：\n> ")
            if os.path.exists(planning_file):
                planning = utils.load_yaml(planning_file)
                batch_size = int(input("每批生成多少章？(建議5-20): ") or "10")
                self.generate_volume(planning, batch_size)
            else:
                print(f"❌ 文件 {planning_file} 不存在")
                
        elif choice == "4":
            print("\n📋 當前目錄下的規劃文件：")
            for file in os.listdir("."):
                if file.endswith("_planning.yaml"):
                    print(f"  - {file}")


def main():
    pipeline = VolumeNovelPipeline()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        pipeline.interactive_mode()
    else:
        # 默認流程：示例第一卷
        main_goal = "主角必須追隨父親的足跡，在神秘的圖書館中找到失落的魔法書籍，以拯救即將被詛咒吞噬的家鄉阿羅恩村"
        
        # 規劃第一卷
        volume_info = {
            "name": "第一卷：圖書館秘境篇",
            "theme": "追尋父親足跡，掌握基礎力量，獲得救贖魔法",
            "start_chapter": 1,
            "end_chapter": 120
        }
        
        planning = pipeline.plan_volume(volume_info)
        
        # 詢問是否開始生成
        if input("\n是否開始生成第一卷？(y/N): ").lower() == 'y':
            pipeline.generate_volume(planning, batch_size=5)


if __name__ == "__main__":
    main()