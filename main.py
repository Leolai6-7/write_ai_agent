"""CLI entry point for the AI novel writing system."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from config.settings import NovelConfig
from config.models import VolumeSpec, ChapterObjective
from pipeline.orchestrator import NovelOrchestrator

app = typer.Typer(help="AI 小說家寫作系統 v2.0")
console = Console()


def _load_config() -> NovelConfig:
    """Load config with API keys from environment."""
    from config.settings import LLMConfig
    return NovelConfig(
        llm=LLMConfig(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        ),
        project_root=Path.cwd(),
    )


@app.command()
def generate(
    title: str = typer.Option("星環之塔的救贖者", help="小說標題"),
    goal: str = typer.Option(
        "主角必須追隨父親的足跡，在神秘的圖書館中找到失落的魔法書籍，以拯救即將被詛咒吞噬的家鄉阿羅恩村",
        help="故事主線",
    ),
    genre: str = typer.Option("奇幻冒險", help="小說類型"),
    volumes: int = typer.Option(3, help="目標卷數"),
    chapters_per_volume: int = typer.Option(120, help="每卷章數"),
):
    """設計小說架構並開始生成。"""
    config = _load_config()
    config.title = title
    config.genre = genre

    console.print(f"\n[bold]AI 小說家 v2.0[/bold] — {title}", style="cyan")
    console.print(f"故事主線：{goal}")
    console.print(f"規劃：{volumes} 卷 × {chapters_per_volume} 章\n")

    orchestrator = NovelOrchestrator(config)

    try:
        # Design volume structure
        console.print("[yellow]正在設計分卷架構...[/yellow]")
        structure = orchestrator.architect.run(
            main_goal=goal, genre=genre,
            target_volumes=volumes, chapters_per_volume=chapters_per_volume,
        )

        # Show structure
        table = Table(title="分卷架構")
        table.add_column("卷", style="cyan")
        table.add_column("主題")
        table.add_column("章節")
        for v in structure.volumes:
            table.add_row(v.name, v.theme, f"{v.start_chapter}-{v.end_chapter}")
        console.print(table)

        # Generate first volume
        if typer.confirm("開始生成第一卷？"):
            orchestrator.run_volume(structure.volumes[0])
            _print_cost_summary(orchestrator)
    finally:
        orchestrator.close()


@app.command()
def resume():
    """從斷點繼續生成。"""
    config = _load_config()
    orchestrator = NovelOrchestrator(config)

    try:
        last_id = orchestrator.memory.get_last_chapter_id()
        if last_id == 0:
            console.print("[red]沒有找到已生成的章節。請先使用 generate 命令。[/red]")
            return

        console.print(f"[green]找到已完成的章節：第 1-{last_id} 章[/green]")
        console.print("從斷點繼續需要提供卷/弧線規劃，請使用 generate 命令。")
    finally:
        orchestrator.close()


@app.command()
def chapter(
    chapter_id: int = typer.Argument(help="章節編號"),
    title: str = typer.Option("測試章節", help="章節標題"),
    objective: str = typer.Option("測試章節內容生成", help="章節目標"),
):
    """生成單一章節（用於測試）。"""
    config = _load_config()
    orchestrator = NovelOrchestrator(config)

    try:
        obj = ChapterObjective(
            chapter_id=chapter_id,
            title=title,
            objective=objective,
            key_events=["事件一", "事件二"],
            characters_involved=["主角"],
            emotional_tone="期待",
        )

        console.print(f"[yellow]生成第 {chapter_id} 章：{title}[/yellow]")
        result = orchestrator.run_chapter(obj)

        if result.get("summary"):
            console.print(f"[green]完成！[/green] 摘要：{result['summary'].one_line_summary}")
        if result.get("judgement"):
            console.print(f"品質評分：{result['judgement'].overall_score}/10")

        _print_cost_summary(orchestrator)
    finally:
        orchestrator.close()


@app.command()
def status():
    """查看目前生成進度和成本。"""
    config = _load_config()
    db_path = config.db_path

    if not db_path.exists():
        console.print("[red]尚未開始生成（找不到資料庫）。[/red]")
        return

    from infrastructure.db import Database

    with Database(db_path) as db:
        chapters = db.conn.execute("SELECT COUNT(*) FROM chapter_summaries").fetchone()[0]
        compressed = db.conn.execute("SELECT COUNT(*) FROM compressed_memories").fetchone()[0]
        characters = db.conn.execute("SELECT COUNT(*) FROM character_states").fetchone()[0]
        threads = db.conn.execute(
            "SELECT COUNT(*) FROM unresolved_threads WHERE resolved_chapter IS NULL"
        ).fetchone()[0]

    table = Table(title="生成進度")
    table.add_column("項目", style="cyan")
    table.add_column("數量", justify="right")
    table.add_row("已完成章節", str(chapters))
    table.add_row("壓縮記憶段", str(compressed))
    table.add_row("追蹤角色", str(characters))
    table.add_row("未解決伏筆", str(threads))
    console.print(table)

    # List outputs
    outputs_dir = config.outputs_dir
    if outputs_dir.exists():
        files = sorted(outputs_dir.glob("chapter_*.md"))
        if files:
            console.print(f"\n[green]章節檔案位於：{outputs_dir}[/green]")
            console.print(f"最新：{files[-1].name}")


def _print_cost_summary(orchestrator: NovelOrchestrator) -> None:
    """Print LLM usage and cost summary."""
    summary = orchestrator.llm.get_usage_summary()
    if not summary:
        return

    table = Table(title="API 使用統計")
    table.add_column("模型", style="cyan")
    table.add_column("呼叫次數", justify="right")
    table.add_column("輸入 tokens", justify="right")
    table.add_column("輸出 tokens", justify="right")
    table.add_column("費用", justify="right", style="yellow")

    for model, stats in summary.items():
        table.add_row(
            model,
            str(stats["calls"]),
            f"{stats['prompt_tokens']:,}",
            f"{stats['completion_tokens']:,}",
            f"${stats['cost']:.4f}",
        )

    console.print(table)
    console.print(f"[bold yellow]總費用：${orchestrator.llm.get_total_cost():.4f}[/bold yellow]")


if __name__ == "__main__":
    app()
