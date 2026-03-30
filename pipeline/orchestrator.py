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
from agents.consistency_checker import ConsistencyChecker
from infrastructure.llm_client import LLMClient
from infrastructure.db import Database
from infrastructure.logger import get_logger
from memory.memory_manager import MemoryManager
from memory.repositories import SummaryRepository, CharacterRepository, ThreadRepository, CompressedRepository
from memory.retrieval import SemanticRetriever
from memory.token_budget import TokenBudget
from memory.world_state import WorldState
from prompts.loader import PromptLoader
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
            aws_region=config.llm.aws_region,
            aws_profile=config.llm.aws_profile or None,
            openai_api_key=config.llm.openai_api_key,
            anthropic_api_key=config.llm.anthropic_api_key,
        )
        self.db = Database(config.db_path)
        self.db.initialize()

        # Initialize semantic retriever and world state
        self.retriever = SemanticRetriever(config.chroma_dir)
        self.world = WorldState(config.world_dir)
        self.world.load()

        # Initialize repositories
        summary_repo = SummaryRepository(self.db)
        character_repo = CharacterRepository(self.db, max_memories=config.memory.max_character_memories)
        thread_repo = ThreadRepository(self.db)
        compressed_repo = CompressedRepository(self.db)

        # Initialize memory manager
        self.memory = MemoryManager(
            summary_repo=summary_repo,
            character_repo=character_repo,
            thread_repo=thread_repo,
            compressed_repo=compressed_repo,
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
            retriever=self.retriever,
            world_state=self.world,
        )

        # Load prompt templates
        prompts = PromptLoader()

        # Initialize agents with prompt templates
        self.architect = VolumeArchitectAgent(
            self.llm, config.llm.planning_model,
            prompt=prompts.load("volume_architect"),
        )
        self.arc_planner = ArcPlannerAgent(
            self.llm, config.llm.planning_model,
            prompt=prompts.load("arc_planner"),
        )
        self.chapter_planner = ChapterPlannerAgent(
            self.llm, config.llm.planning_model,
            prompt=prompts.load("chapter_planner"),
        )

        generator = ChapterGeneratorAgent(
            self.llm, config.llm.generation_model,
            prompt=prompts.load("chapter_generator"),
        )
        judge = JudgeAgent(
            self.llm, config.llm.judge_model,
            prompt=prompts.load("judge"),
            voting_rounds=config.generation.judge_voting_rounds,
        )
        rewriter = RewriteAgent(
            self.llm, config.llm.rewrite_model,
            prompt=prompts.load("rewrite"),
        )
        summarizer = SummarizerAgent(
            self.llm, config.llm.summary_model,
            prompt=prompts.load("summarizer"),
        )
        consistency = ConsistencyChecker(
            self.llm, config.llm.consistency_model,
            prompt=prompts.load("consistency_checker"),
        )

        # Build LangGraph with node classes
        from pipeline.nodes import (
            AssembleContextNode, GenerateNode, JudgeNode,
            RewriteNode, ConsistencyNode, SummarizeNode, UpdateMemoryNode,
        )
        from pipeline.nodes.rewrite import RewriteConsistencyNode

        nodes = {
            "assemble_context": AssembleContextNode(self.memory),
            "generate": GenerateNode(generator, judge, dual_draft=config.generation.dual_draft),
            "judge": JudgeNode(judge, self.memory),
            "rewrite": RewriteNode(rewriter),
            "check_consistency": ConsistencyNode(consistency),
            "rewrite_consistency": RewriteConsistencyNode(rewriter),
            "summarize": SummarizeNode(summarizer),
            "update_memory": UpdateMemoryNode(self.memory),
        }
        builder = ChapterGraphBuilder(nodes)
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

            max_retries = 2
            for attempt in range(1, max_retries + 1):
                try:
                    result = self.run_chapter(obj)
                    results.append(result)
                    break
                except Exception as e:
                    logger.error(
                        "Chapter %d failed (attempt %d/%d): %s",
                        obj.chapter_id, attempt, max_retries, e,
                    )
                    if attempt == max_retries:
                        logger.error("Chapter %d skipped after %d failures", obj.chapter_id, max_retries)

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
