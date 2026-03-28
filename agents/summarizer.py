"""Summarizer agent - generates structured chapter summaries."""

from __future__ import annotations

from config.models import ChapterSummary
from agents.base_agent import BaseAgent


class SummarizerAgent(BaseAgent):
    """Generates structured chapter summaries for memory management."""

    def run(self, chapter_id: int, chapter_text: str) -> ChapterSummary:
        """Generate a structured summary of a chapter.

        Returns:
            ChapterSummary with events, character changes, and threads.
        """
        system_prompt = (
            "你是一位小說分析師。請為給定的章節生成結構化摘要。\n\n"
            "請以 JSON 格式回應，包含以下欄位：\n"
            "- chapter_id: 章節編號\n"
            "- plot_events: 3-5個關鍵事件（字串陣列）\n"
            "- character_changes: 角色變化（物件，key=角色名，value=變化描述）\n"
            "- world_state_changes: 世界狀態變化（字串陣列）\n"
            "- unresolved_threads: 未解決的伏筆（字串陣列）\n"
            "- emotional_arc: 情感走向（一個詞或短語）\n"
            "- one_line_summary: 一句話摘要（20字以內）\n"
        )

        result = self.call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"章節編號：{chapter_id}\n\n{chapter_text}",
                },
            ],
            response_model=ChapterSummary,
            temperature=0.3,
            max_tokens=1500,
        )

        # Ensure chapter_id matches
        result.chapter_id = chapter_id
        self.logger.info("Summarized chapter %d: %s", chapter_id, result.one_line_summary)
        return result
