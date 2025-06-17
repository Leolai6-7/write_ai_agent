"""卷級架構師代理 - 設計分卷式小說的整體架構"""
import yaml
from common import settings, utils


class VolumeArchitectAgent:
    def __init__(self):
        self.client = settings.CLIENT
        self.model = settings.PLANNING_MODEL
        
    def design_novel_structure(self, main_goal: str, target_volumes: int = 3) -> dict:
        """設計整部小說的卷級結構"""
        prompt = f"""你是一位資深的網路小說架構師，擅長設計分卷式長篇小說。

【總體目標】{main_goal}

請設計一部 {target_volumes} 卷的網路小說架構：

1. 每卷應有明確的主題和階段性目標
2. 每卷約100-200章，內容豐富有層次
3. 卷與卷之間要有承接關係，逐步推進總體目標
4. 每卷內部要有起承轉合，有小高潮和大高潮

請按以下格式回答：
第一卷：[卷名]
- 主題：[這一卷要解決什麼問題]
- 章數範圍：1-100章
- 核心情節：[3-5個主要情節點]

第二卷：[卷名]
- 主題：[這一卷要解決什麼問題] 
- 章數範圍：101-200章
- 核心情節：[3-5個主要情節點]

以此類推..."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ 卷級設計失敗: {e}")
            return self._fallback_structure(target_volumes)
    
    def _fallback_structure(self, target_volumes: int) -> str:
        """備用的卷級結構設計"""
        if target_volumes >= 1:
            return """第一卷：圖書館秘境篇
- 主題：追尋父親足跡，掌握基礎力量
- 章數範圍：1-120章
- 核心情節：進入圖書館、通過守護者考驗、學習禁咒知識、獲得救贖魔法、遭遇競爭對手

第二卷：家鄉拯救篇  
- 主題：運用所學力量，拯救被詛咒的家鄉
- 章數範圍：121-240章
- 核心情節：返回家鄉、調查詛咒源頭、與黑暗勢力對抗、解救村民、與父親重逢

第三卷：大陸風雲篇
- 主題：發現更大陰謀，成長為真正的魔導士
- 章數範圍：241-360章  
- 核心情節：揭露大陸危機、前往星環之塔、師父傳承、最終決戰、和平回歸"""

    def plan_volume_chapters(self, volume_theme: str, start_chapter: int, target_chapters: int) -> list:
        """規劃單卷的章節結構"""
        prompt = f"""你是網路小說章節規劃專家。

【卷主題】{volume_theme}
【章節範圍】第{start_chapter}-{start_chapter + target_chapters - 1}章
【目標章數】{target_chapters}章

請將這一卷分為若干個階段，每個階段10-20章，每階段要有：
1. 明確的小目標
2. 情節發展節奏
3. 角色成長元素
4. 承接上下的轉折點

請按以下格式輸出章節規劃：
第{start_chapter}-{start_chapter + 19}章：[階段名稱]
- 小目標：[這個階段要完成什麼]
- 重點情節：[主要發生什麼事件]

第{start_chapter + 20}-{start_chapter + 39}章：[階段名稱]  
- 小目標：[這個階段要完成什麼]
- 重點情節：[主要發生什麼事件]

以此類推..."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1200
            )
            return response.choices[0].message.content.strip().split('\n')
        except Exception as e:
            print(f"❌ 章節規劃失敗: {e}")
            return self._fallback_chapter_plan(start_chapter, target_chapters)
    
    def _fallback_chapter_plan(self, start_chapter: int, target_chapters: int) -> list:
        """備用的章節規劃"""
        stages = []
        chapters_per_stage = 20
        current_chapter = start_chapter
        
        while current_chapter < start_chapter + target_chapters:
            end_chapter = min(current_chapter + chapters_per_stage - 1, start_chapter + target_chapters - 1)
            stage_name = f"第{current_chapter}-{end_chapter}章：發展階段"
            stages.append(stage_name)
            current_chapter += chapters_per_stage
            
        return stages

    def save_novel_structure(self, structure: str, file_path: str = None):
        """保存小說架構到文件"""
        if not file_path:
            file_path = "novel_structure.md"
        
        utils.save_text(file_path, structure)
        print(f"✅ 小說架構已保存到: {file_path}")

    def run(self, main_goal: str, target_volumes: int = 3):
        """執行完整的卷級架構設計"""
        print("🏗️ 正在設計分卷式小說架構...")
        
        # 1. 設計整體結構
        structure = self.design_novel_structure(main_goal, target_volumes)
        
        # 2. 保存結構
        self.save_novel_structure(structure, "novel_architecture.md")
        
        print("\n📚 小說架構設計完成：")
        print(structure)
        
        return structure


if __name__ == "__main__":
    agent = VolumeArchitectAgent()
    main_goal = input("請輸入小說的總體目標：\n> ")
    volumes = int(input("計劃分幾卷？(建議3-5卷): ") or "3")
    agent.run(main_goal, volumes)