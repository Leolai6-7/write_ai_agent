"""增強版目標規劃代理 - 支持三層目標結構"""
import yaml
from common import settings, utils


class EnhancedGoalPlannerAgent:
    def __init__(self):
        self.client = settings.CLIENT
        self.model = settings.PLANNING_MODEL
        
    def plan_arc_objectives(self, volume_theme: str, start_chapter: int, end_chapter: int) -> list:
        """為指定卷規劃弧線目標(每弧線約20-30章)"""
        chapter_count = end_chapter - start_chapter + 1
        arcs_count = max(3, chapter_count // 25)  # 每25章一個弧線
        
        prompt = f"""你是網路小說情節規劃師。

【卷主題】{volume_theme}
【章節範圍】第{start_chapter}-{end_chapter}章 (共{chapter_count}章)
【目標弧線數】{arcs_count}個主要弧線

請將這一卷分為{arcs_count}個主要弧線，每個弧線20-30章：

弧線1 (第{start_chapter}-{start_chapter + chapter_count//arcs_count - 1}章)：[弧線名稱]
- 核心目標：[這個弧線要達成什麼]
- 主要衝突：[面臨什麼挑戰]
- 結尾轉折：[如何連接下個弧線]

弧線2 (第{start_chapter + chapter_count//arcs_count}-{start_chapter + chapter_count*2//arcs_count - 1}章)：[弧線名稱]
- 核心目標：[這個弧線要達成什麼]
- 主要衝突：[面臨什麼挑戰]  
- 結尾轉折：[如何連接下個弧線]

以此類推..."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content.strip().split('\n弧線')
        except Exception as e:
            return self._fallback_arc_plan(start_chapter, end_chapter, arcs_count)
    
    def plan_chapter_objectives(self, arc_theme: str, start_chapter: int, end_chapter: int) -> list:
        """為指定弧線規劃具體章節目標"""
        chapter_count = end_chapter - start_chapter + 1
        
        prompt = f"""你是章節目標規劃師。

【弧線主題】{arc_theme}
【章節範圍】第{start_chapter}-{end_chapter}章 (共{chapter_count}章)

請為這{chapter_count}章設計具體的章節目標，要求：
1. 每章都有明確的小目標
2. 章與章之間有邏輯連接
3. 整體推進弧線主題
4. 包含戰鬥、對話、探索、成長等多元素

格式：
第{start_chapter}章：[章節目標描述]
第{start_chapter + 1}章：[章節目標描述]
...
第{end_chapter}章：[章節目標描述]"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            lines = response.choices[0].message.content.strip().split('\n')
            return [line.strip() for line in lines if line.strip() and '章：' in line]
        except Exception as e:
            return self._fallback_chapter_objectives(start_chapter, end_chapter)
    
    def _fallback_arc_plan(self, start_chapter: int, end_chapter: int, arcs_count: int) -> list:
        """備用弧線規劃"""
        arcs = []
        chapters_per_arc = (end_chapter - start_chapter + 1) // arcs_count
        
        for i in range(arcs_count):
            arc_start = start_chapter + i * chapters_per_arc
            arc_end = arc_start + chapters_per_arc - 1 if i < arcs_count - 1 else end_chapter
            arcs.append(f"弧線{i+1} (第{arc_start}-{arc_end}章)：發展階段{i+1}")
        
        return arcs
    
    def _fallback_chapter_objectives(self, start_chapter: int, end_chapter: int) -> list:
        """備用章節目標"""
        objectives = []
        for i in range(start_chapter, end_chapter + 1):
            objectives.append(f"第{i}章：推進主線情節，深化角色發展")
        return objectives
    
    def save_planning_result(self, planning_data: dict, file_path: str):
        """保存規劃結果"""
        utils.save_yaml(file_path, planning_data)
        print(f"✅ 規劃結果已保存到: {file_path}")

    def run_volume_planning(self, volume_name: str, volume_theme: str, start_chapter: int, end_chapter: int):
        """執行單卷的完整規劃"""
        print(f"📋 正在規劃《{volume_name}》({start_chapter}-{end_chapter}章)...")
        
        # 1. 規劃弧線
        arcs = self.plan_arc_objectives(volume_theme, start_chapter, end_chapter)
        
        # 2. 為每個弧線規劃章節
        volume_planning = {
            "volume_name": volume_name,
            "volume_theme": volume_theme,
            "chapter_range": f"{start_chapter}-{end_chapter}",
            "arcs": {}
        }
        
        print(f"\n📚 {volume_name} 弧線規劃：")
        for i, arc in enumerate(arcs, 1):
            print(f"  {arc}")
            
            # 計算弧線章節範圍（簡化版）
            arc_chapters = (end_chapter - start_chapter + 1) // len(arcs)
            arc_start = start_chapter + (i - 1) * arc_chapters
            arc_end = arc_start + arc_chapters - 1 if i < len(arcs) else end_chapter
            
            # 規劃弧線的具體章節
            arc_name = f"弧線{i}"
            chapter_objectives = self.plan_chapter_objectives(arc, arc_start, arc_end)
            
            volume_planning["arcs"][arc_name] = {
                "theme": arc,
                "chapter_range": f"{arc_start}-{arc_end}",
                "chapter_objectives": chapter_objectives
            }
        
        # 3. 保存結果
        filename = f"volume_{start_chapter}_{end_chapter}_planning.yaml"
        self.save_planning_result(volume_planning, filename)
        
        return volume_planning


if __name__ == "__main__":
    planner = EnhancedGoalPlannerAgent()
    volume_name = input("請輸入卷名：\n> ")
    volume_theme = input("請輸入卷主題：\n> ")
    start_chapter = int(input("起始章節：\n> "))
    end_chapter = int(input("結束章節：\n> "))
    
    planner.run_volume_planning(volume_name, volume_theme, start_chapter, end_chapter)