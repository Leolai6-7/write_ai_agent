"""Pipeline orchestrator - drives the full novel generation workflow."""

from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from config.models import VolumeSpec, ArcSpec, ChapterObjective
from config.settings import NovelConfig
from agents.volume_architect import VolumeArchitectAgent
from agents.arc_planner import ArcPlannerAgent
from agents.chapter_planner import ChapterPlannerAgent
from agents.chapter_generator import ChapterGeneratorAgent
from agents.judge_agent import JudgeAgent
from agents.rewrite_agent import RewriteAgent
from agents.summarizer import SummarizerAgent
from infrastructure.llm_client import LLMClient
from infrastructure.db import Database
from infrastructure.logger import get_logger
from memory.memory_manager import MemoryManager
from memory.token_budget import TokenBudget
from pipeline.chapter_graph import ChapterGraphBuilder, ChapterState

logger = get_logger("orchestrator")


class NovelOrchestrator:
    """Orchestrates the full novel generation pipeline.

    Uses LangGraph for single-chapter processing and Python loops for
    volume/arc/chapter iteration.
    """

    def __init__(self, config: NovelConfig):
        self.config = config
        config.ensure_dirs()

        # Initialize infrastructure
        self.llm = LLMClient(
            openai_api_key=config.llm.openai_api_key,
            anthropic_api_key=config.llm.anthropic_api_key,
        )
        self.db = Database(config.db_path)
        self.db.initialize()

        # Initialize memory
        self.memory = MemoryManager(
            db=self.db,
            llm=self.llm,
            short_term_window=config.memory.short_term_window,
            compression_interval=config.memory.compression_interval,
            token_budget=TokenBudget(
                total=config.memory.context_token_budget,
                short_term=config.memory.short_term_budget,
                long_term=config.memory.long_term_budget,
                character=config.memory.character_budget,
                world=config.memory.world_budget,
                instruction=config.memory.instruction_budget,
            ),
        )

        # Initialize agents
        self.architect = VolumeArchitectAgent(
            self.llm, config.llm.planning_model,
        )
        self.arc_planner = ArcPlannerAgent(
            self.llm, config.llm.planning_model,
        )
        self.chapter_planner = ChapterPlannerAgent(
            self.llm, config.llm.planning_model,
        )

        generator = ChapterGeneratorAgent(self.llm, config.llm.generation_model)
        judge = JudgeAgent(self.llm, config.llm.judge_model)
        rewriter = RewriteAgent(self.llm, config.llm.rewrite_model)
        summarizer = SummarizerAgent(self.llm, config.llm.summary_model)

        # Build LangGraph
        builder = ChapterGraphBuilder(generator, judge, rewriter, summarizer, self.memory)
        self.chapter_graph = builder.build().compile(
            checkpointer=MemorySaver(),
        )

    def run_chapter(self, objective: ChapterObjective) -> ChapterState:
        """Run single chapter through the full pipeline."""
        logger.info("Starting chapter %d: %s", objective.chapter_id, objective.title)

        initial_state: ChapterState = {
            "chapter_objective": objective,
            "context": None,
            "draft": "",
            "judgement": None,
            "rewrite_count": 0,
            "final_chapter": "",
            "summary": None,
            "consistency": None,
        }

        result = self.chapter_graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": f"chapter_{objective.chapter_id}"}},
        )

        # Save chapter text to file
        if result.get("final_chapter"):
            output_path = self.config.outputs_dir / f"chapter_{objective.chapter_id:03d}.md"
            output_path.write_text(result["final_chapter"], encoding="utf-8")
            logger.info("Chapter %d saved to %s", objective.chapter_id, output_path)

        return result

    def run_arc(self, arc: ArcSpec) -> list[ChapterState]:
        """Run all chapters in an arc."""
        logger.info("Starting arc: %s (%d-%d)", arc.arc_name, arc.start_chapter, arc.end_chapter)

        # Plan chapters
        objectives = self.chapter_planner.run(arc=arc)

        results = []
        for obj in objectives:
            # Skip already completed chapters
            if obj.chapter_id <= self.memory.get_last_chapter_id():
                logger.info("Skipping chapter %d (already completed)", obj.chapter_id)
                continue

            try:
                result = self.run_chapter(obj)
                results.append(result)
            except Exception as e:
                logger.error("Chapter %d failed: %s", obj.chapter_id, e)
                # Continue with next chapter instead of stopping
                continue

        logger.info("Arc '%s' completed: %d/%d chapters", arc.arc_name, len(results), len(objectives))
        return results

    def run_volume(self, volume: VolumeSpec) -> None:
        """Run all arcs in a volume."""
        logger.info("Starting volume: %s", volume.name)

        arcs = self.arc_planner.run(volume=volume)

        for arc in arcs:
            self.run_arc(arc)

        # Print cost summary
        summary = self.llm.get_usage_summary()
        logger.info("Volume '%s' completed. Cost summary:", volume.name)
        for model, stats in summary.items():
            logger.info(
                "  %s: %d calls, %d prompt tokens, %d completion tokens, $%.4f",
                model, stats["calls"], stats["prompt_tokens"],
                stats["completion_tokens"], stats["cost"],
            )
        logger.info("Total cost: $%.4f", self.llm.get_total_cost())

    def close(self) -> None:
        """Clean up resources."""
        self.db.close()
