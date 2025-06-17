"""目標規劃代理 - 將主要目標拆解為子目標"""
from common import settings, utils


class GoalPlannerAgent:
    def __init__(self):
        self.client = settings.CLIENT
        self.model = settings.PLANNING_MODEL
        self.log_file = settings.OBJECTIVES_EXPANDED_FILE

    def suggest_subgoals(self, main_goal: str, story_context: str = "") -> list:
        """根據主要目標，建議數個子目標"""
        prompt_content = (
            "你是一位小說策劃顧問，擅長將一個主要故事目標拆解為 3 到 6 個子目標，"
            "以便在多章節中逐步推進故事發展。子目標應具備明確行動與情境，並能帶出人物互動或衝突。"
            "請列出子目標清單，每行一項，語氣簡潔。"
        )
        
        if story_context:
            prompt_content += f"\n\n【故事背景】\n{story_context}"
        
        prompt_content += f"\n\n【主要目標】\n{main_goal}\n\n【子目標建議】"
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位經驗豐富的小說故事規劃顧問。"},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.7,
            max_tokens=800
        )
        return response.choices[0].message.content.strip().split("\n")

    def load_subgoals(self, main_goal: str):
        """載入指定主要目標的子目標"""
        data = utils.load_yaml(self.log_file) or {}
        return data.get(main_goal, [])

    def get_chapter_objective(self, main_goal: str, chapter_id: int):
        """取得指定章節的目標"""
        subgoals = self.load_subgoals(main_goal)
        if not subgoals:
            print("⚠️ 無子目標紀錄，請先建立。")
            return None
        if chapter_id <= len(subgoals):
            return subgoals[chapter_id - 1]
        print("⚠️ 所有子目標已用盡。請新增目標或中止寫作流程。")
        return None

    def run(self, main_goal: str, story_context: str = ""):
        """執行目標規劃流程"""
        print("🧠 正在啟動目標規劃代理...")
        subgoals = self.suggest_subgoals(main_goal, story_context)
        
        print("\n🎯 子目標建議：\n")
        for g in subgoals:
            print(f"- {g}")
        
        data = utils.load_yaml(self.log_file) or {}
        data[main_goal] = subgoals
        utils.save_yaml(self.log_file, data)
        print(f"\n✅ 子目標已記錄至：{self.log_file}")
        return subgoals


if __name__ == "__main__":
    agent = GoalPlannerAgent()
    main_goal = input("請輸入主要故事目標：\n> ")
    context = input("（可選）請輸入故事背景摘要：\n> ")
    agent.run(main_goal, context)