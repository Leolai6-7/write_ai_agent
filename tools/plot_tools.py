from plot_planner_agent import PlotPlannerAgent

planner = PlotPlannerAgent()

def tool_suggest_next_objectives(summary_text: str):
    return planner.suggest_next_objectives(summary_text)

def tool_log_objective(chapter_id: int, objective: str):
    return planner.log_objective(chapter_id, objective)

plot_tools = [
    {
        "type": "function",
        "function": {
            "name": "suggest_next_objectives",
            "description": "根據前情摘要與主角性格，建議下一章小說的可能發展目標",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary_text": {
                        "type": "string",
                        "description": "上一章的故事摘要內容"
                    }
                },
                "required": ["summary_text"]
            }
        }
    },
    {
    "type": "function",
    "function": {
        "name": "log_objective",
        "description": "將該章節的故事目標寫入 objectives.yaml 進行記錄",
        "parameters": {
            "type": "object",
            "properties": {
                "chapter_id": {
                    "type": "integer",
                    "description": "章節編號，例如 6"
                },
                "objective": {
                    "type": "string",
                    "description": "該章節的故事目標內容，例如：主角潛入禁咒資料庫"
                }
            },
            "required": ["chapter_id", "objective"]
        }
    }
}

]
