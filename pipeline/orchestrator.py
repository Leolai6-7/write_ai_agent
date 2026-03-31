"""Pipeline orchestrator - drives the complete novel generation workflow.

Four stages: Conception → Creation → Editing → Assembly
"""

from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from config.models import VolumeSpec, ArcSpec, ChapterObjective, WorldBible, CharacterCast
from config.settings import NovelConfig
from agents.volume_architect import VolumeArchitectAgent
from agents.arc_planner import ArcPlannerAgent
from agents.chapter_planner import ChapterPlannerAgent
from agents.chapter_generator import ChapterGeneratorAgent
from agents.judge_agent import JudgeAgent
from agents.rewrite_agent import RewriteAgent
from agents.summarizer import SummarizerAgent
from agents.consistency_checker import ConsistencyChecker
from agents.world_builder import WorldBuilderAgent
from agents.character_designer import CharacterDesignerAgent
from agents.foreshadowing_manager import ForeshadowingManager
from agents.pacing_advisor import PacingAdvisor
from agents.story_bible_keeper import StoryBibleKeeper
from agents.style_editor import StyleEditorAgent
from agents.novel_assembler import NovelAssembler
from infrastructure.llm_client import LLMClient
from infrastructure.db import Database
from infrastructure.logger import get_logger
from memory.memory_manager import MemoryManager
from memory.repositories import (
    SummaryRepository, CharacterRepository, ThreadRepository,
    CompressedRepository, ForeshadowRepository, WorldRepository, ProfileRepository,
)
from memory.retrieval import SemanticRetriever
from memory.token_budget import TokenBudget
from memory.world_state import WorldState
from prompts.loader import PromptLoader
from pipeline.chapter_graph import ChapterGraphBuilder, ChapterState

logger = get_logger("orchestrator")


class NovelOrchestrator:
    """Orchestrates the complete novel generation workflow.

    Stages:
        1. Conception: world building, character design, structure planning, foreshadowing
        2. Creation: chapter-by-chapter generation with pacing and bible updates
        3. Editing: style audit per volume
        4. Assembly: combine into complete novel
    """

    def __init__(self, config: NovelConfig):
        self.config = config
        config.ensure_dirs()

        # ── Infrastructure ──────────────────────────────────────
        self.llm = LLMClient(
            aws_region=config.llm.aws_region,
            aws_profile=config.llm.aws_profile or None,
            openai_api_key=config.llm.openai_api_key,
            anthropic_api_key=config.llm.anthropic_api_key,
        )
        self.db = Database(config.db_path)
        self.db.initialize()

        self.retriever = SemanticRetriever(config.chroma_dir)
        self.world = WorldState(config.world_dir)
        self.world.load()

        # ── Repositories ────────────────────────────────────────
        summary_repo = SummaryRepository(self.db)
        character_repo = CharacterRepository(self.db, max_memories=config.memory.max_character_memories)
        thread_repo = ThreadRepository(self.db)
        compressed_repo = CompressedRepository(self.db)
        self.foreshadow_repo = ForeshadowRepository(self.db)
        self.world_repo = WorldRepository(self.db)
        self.profile_repo = ProfileRepository(self.db)

        # ── Memory Manager ──────────────────────────────────────
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

        # ── Load Prompts ────────────────────────────────────────
        prompts = PromptLoader()

        # ── Stage 1: Conception Agents ──────────────────────────
        self.architect = VolumeArchitectAgent(
            self.llm, config.llm.planning_model,
            prompt=prompts.load("volume_architect"),
        )
        self.world_builder = WorldBuilderAgent(
            self.llm, config.llm.planning_model,
            prompt=prompts.load("world_builder"),
        )
        self.character_designer = CharacterDesignerAgent(
            self.llm, config.llm.planning_model,
            prompt=prompts.load("character_designer"),
        )
        self.arc_planner = ArcPlannerAgent(
            self.llm, config.llm.planning_model,
            prompt=prompts.load("arc_planner"),
        )
        self.chapter_planner = ChapterPlannerAgent(
            self.llm, config.llm.planning_model,
            prompt=prompts.load("chapter_planner"),
        )
        self.foreshadowing = ForeshadowingManager(
            self.llm, config.llm.planning_model,
            prompt=prompts.load("foreshadowing"),
            foreshadow_repo=self.foreshadow_repo,
        )

        # ── Stage 2: Creation Agents ────────────────────────────
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
            self.llm, config.llm.rewrite_model, prompt=prompts.load("rewrite"),
        )
        summarizer = SummarizerAgent(
            self.llm, config.llm.summary_model, prompt=prompts.load("summarizer"),
        )
        consistency = ConsistencyChecker(
            self.llm, config.llm.consistency_model,
            prompt=prompts.load("consistency_checker"),
        )
        pacing = PacingAdvisor(
            self.llm, config.llm.summary_model,  # Use cheaper model
            prompt=prompts.load("pacing_advisor"),
        )
        bible_keeper = StoryBibleKeeper(
            self.llm, config.llm.summary_model,
            prompt=prompts.load("story_bible_keeper"),
        )

        # ── Stage 3: Editing Agents ─────────────────────────────
        self.style_editor = StyleEditorAgent(
            self.llm, config.llm.judge_model,
            prompt=prompts.load("style_editor"),
        )

        # ── Stage 4: Assembly ───────────────────────────────────
        self.assembler = NovelAssembler()

        # ── Build LangGraph ─────────────────────────────────────
        from pipeline.nodes import (
            AssembleContextNode, GenerateNode, JudgeNode,
            RewriteNode, ConsistencyNode, SummarizeNode, UpdateMemoryNode,
            PacingAdvisorNode, StoryBibleKeeperNode,
        )
        from pipeline.nodes.rewrite import RewriteConsistencyNode

        nodes = {
            "assemble_context": AssembleContextNode(self.memory),
            "pacing_advisor": PacingAdvisorNode(pacing, self.memory),
            "generate": GenerateNode(generator, judge, dual_draft=config.generation.dual_draft),
            "judge": JudgeNode(judge, self.memory),
            "rewrite": RewriteNode(rewriter),
            "check_consistency": ConsistencyNode(consistency),
            "rewrite_consistency": RewriteConsistencyNode(rewriter),
            "summarize": SummarizeNode(summarizer),
            "story_bible_keeper": StoryBibleKeeperNode(bible_keeper, self.memory, self.world_repo),
            "update_memory": UpdateMemoryNode(self.memory),
        }
        builder = ChapterGraphBuilder(nodes)
        self.chapter_graph = builder.build().compile(checkpointer=MemorySaver())

    # ── Stage 1: Conception ─────────────────────────────────────

    def conceive(
        self,
        main_goal: str,
        genre: str = "奇幻冒險",
        target_volumes: int = 3,
        chapters_per_volume: int = 120,
    ) -> tuple:
        """Run conception stage: world building, character design, structure planning.

        Returns:
            (volume_structure, world_bible, character_cast)
        """
        logger.info("=== Stage 1: Conception ===")

        # Design volume structure
        logger.info("Designing volume structure...")
        volume_structure = self.architect.run(
            main_goal=main_goal, genre=genre,
            target_volumes=target_volumes,
            chapters_per_volume=chapters_per_volume,
        )

        # Expand world bible
        logger.info("Building world bible...")
        world_bible = self.world_builder.run(
            world_setting=self.world._world,
            main_goal=main_goal,
            genre=genre,
        )

        # Design character cast
        logger.info("Designing character cast...")
        character_cast = self.character_designer.run(
            protagonist=self.world._character,
            world_bible=world_bible,
            volume_structure=volume_structure,
            main_goal=main_goal,
        )

        # Save character profiles to DB
        self.profile_repo.save_cast(character_cast)
        logger.info("Conception complete: %d volumes, %d characters",
                     len(volume_structure.volumes), len(character_cast.characters))

        return volume_structure, world_bible, character_cast

    # ── Stage 2: Creation ───────────────────────────────────────

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

        if result.get("final_chapter"):
            output_path = self.config.outputs_dir / f"chapter_{objective.chapter_id:03d}.md"
            output_path.write_text(result["final_chapter"], encoding="utf-8")
            logger.info("Chapter %d saved to %s", objective.chapter_id, output_path)

        return result

    def run_arc(self, arc: ArcSpec) -> list[ChapterState]:
        """Run all chapters in an arc."""
        logger.info("Starting arc: %s (%d-%d)", arc.arc_name, arc.start_chapter, arc.end_chapter)

        objectives = self.chapter_planner.run(arc=arc)

        results = []
        for obj in objectives:
            if obj.chapter_id <= self.memory.get_last_chapter_id():
                logger.info("Skipping chapter %d (already completed)", obj.chapter_id)
                continue

            # Inject foreshadowing directive
            obj.foreshadow_directive = self.foreshadowing.get_directive(obj.chapter_id)

            max_retries = 2
            for attempt in range(1, max_retries + 1):
                try:
                    result = self.run_chapter(obj)
                    results.append(result)
                    break
                except Exception as e:
                    logger.error("Chapter %d failed (attempt %d/%d): %s",
                                 obj.chapter_id, attempt, max_retries, e)
                    if attempt == max_retries:
                        logger.error("Chapter %d skipped after %d failures",
                                     obj.chapter_id, max_retries)

        logger.info("Arc '%s' completed: %d/%d chapters",
                     arc.arc_name, len(results), len(objectives))
        return results

    def run_volume(self, volume: VolumeSpec) -> None:
        """Run all arcs in a volume with foreshadowing planning."""
        logger.info("=== Stage 2: Creation - %s ===", volume.name)

        # Plan arcs
        arcs = self.arc_planner.run(volume=volume)

        # Plan foreshadowing for this volume
        existing_threads = [t["description"] for t in self.memory.threads.get_unresolved()]
        self.foreshadowing.plan(volume, arcs, existing_threads)

        # Generate chapters
        for arc in arcs:
            self.run_arc(arc)

        # Print cost summary
        self._print_cost_summary(f"Volume '{volume.name}'")

    # ── Stage 3: Editing ────────────────────────────────────────

    def edit_volume(self, volume_name: str) -> None:
        """Run style audit on a completed volume."""
        logger.info("=== Stage 3: Editing - %s ===", volume_name)

        # Get character voices for reference
        profiles = self.profile_repo.get_all()
        voices = "\n".join(
            f"- {p.name}：{p.speaking_style}" for p in profiles if p.speaking_style
        )

        report = self.style_editor.audit(
            volume_name=volume_name,
            chapter_dir=self.config.outputs_dir,
            character_voices=voices,
        )
        logger.info("Style audit: %s (score: %.1f/10)",
                     report.summary, report.overall_consistency_score)

    # ── Stage 4: Assembly ───────────────────────────────────────

    def assemble(self) -> Path:
        """Assemble all chapters into a complete novel."""
        logger.info("=== Stage 4: Assembly ===")
        return self.assembler.assemble(
            title=self.config.title,
            author=self.config.author,
            chapter_dir=self.config.outputs_dir,
        )

    # ── Full Pipeline ───────────────────────────────────────────

    def run_full(
        self,
        main_goal: str,
        genre: str = "奇幻冒險",
        target_volumes: int = 3,
        chapters_per_volume: int = 120,
        volumes_to_generate: int = 1,
    ) -> None:
        """Run the complete 4-stage pipeline."""
        # Stage 1: Conception
        volume_structure, world_bible, character_cast = self.conceive(
            main_goal, genre, target_volumes, chapters_per_volume,
        )

        # Stage 2: Creation (generate requested volumes)
        for i, volume in enumerate(volume_structure.volumes[:volumes_to_generate]):
            self.run_volume(volume)

            # Stage 3: Editing (after each volume)
            self.edit_volume(volume.name)

        # Stage 4: Assembly
        output = self.assemble()
        logger.info("Novel complete: %s", output)

        self._print_cost_summary("Total")

    def _print_cost_summary(self, label: str) -> None:
        summary = self.llm.get_usage_summary()
        logger.info("%s cost summary:", label)
        for model, stats in summary.items():
            logger.info("  %s: %d calls, %d prompt, %d completion, $%.4f",
                         model, stats["calls"], stats["prompt_tokens"],
                         stats["completion_tokens"], stats["cost"])
        logger.info("Total cost: $%.4f", self.llm.get_total_cost())

    def close(self) -> None:
        """Clean up resources."""
        self.db.close()
