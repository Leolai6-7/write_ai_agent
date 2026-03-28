"""Tests for import validation — ensure all modules can be imported."""


def test_import_all_agents():
    from agents.base_agent import BaseAgent
    from agents.chapter_generator import ChapterGeneratorAgent
    from agents.judge_agent import JudgeAgent
    from agents.rewrite_agent import RewriteAgent
    from agents.summarizer import SummarizerAgent
    from agents.volume_architect import VolumeArchitectAgent
    from agents.arc_planner import ArcPlannerAgent
    from agents.chapter_planner import ChapterPlannerAgent


def test_import_memory():
    from memory.memory_manager import MemoryManager
    from memory.token_budget import TokenBudget


def test_import_pipeline():
    from pipeline.chapter_graph import ChapterGraphBuilder, build_chapter_graph
    from pipeline.orchestrator import NovelOrchestrator


def test_import_infrastructure():
    from infrastructure.llm_client import LLMClient, TokenUsage
    from infrastructure.db import Database
    from infrastructure.logger import setup_logger, get_logger


def test_import_config():
    from config.models import (
        VolumeStructure, VolumeSpec, ArcSpec, ChapterObjective,
        JudgementResult, ConsistencyReport, ChapterSummary,
        CharacterState, ChapterContext,
    )
    from config.settings import NovelConfig
