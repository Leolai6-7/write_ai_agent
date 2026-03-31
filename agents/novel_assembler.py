"""Novel assembler - combines chapters into a complete novel with TOC and metadata."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from infrastructure.logger import get_logger

logger = get_logger("novel_assembler")


class NovelAssembler:
    """Assembles individual chapter files into a complete novel document."""

    def assemble(
        self,
        title: str,
        author: str,
        chapter_dir: Path,
        output_path: Path | None = None,
    ) -> Path:
        """Combine all chapters into a single markdown file with TOC.

        Args:
            title: Novel title.
            author: Author name.
            chapter_dir: Directory containing chapter_NNN.md files.
            output_path: Output file path. Defaults to chapter_dir/novel_complete.md.

        Returns:
            Path to the assembled novel file.
        """
        chapter_files = sorted(chapter_dir.glob("chapter_*.md"))
        if not chapter_files:
            raise FileNotFoundError(f"No chapter files found in {chapter_dir}")

        output = output_path or chapter_dir / "novel_complete.md"

        parts = []

        # Title page
        parts.append(f"# {title}\n")
        parts.append(f"**作者**：{author}\n")
        parts.append(f"**生成日期**：{datetime.now():%Y-%m-%d}\n")
        parts.append(f"**總章數**：{len(chapter_files)}\n")

        # Word count
        total_chars = 0
        chapters_text = []
        for f in chapter_files:
            text = f.read_text(encoding="utf-8")
            total_chars += len(text)
            chapters_text.append((f.stem, text))

        parts.append(f"**總字數**：約 {total_chars:,} 字\n")
        parts.append("---\n")

        # Table of contents
        parts.append("## 目錄\n")
        for i, (stem, _) in enumerate(chapters_text, 1):
            ch_num = stem.split("_")[-1]
            parts.append(f"{i}. [第{ch_num}章](#第{ch_num}章)")
        parts.append("\n---\n")

        # Chapters
        for stem, text in chapters_text:
            ch_num = stem.split("_")[-1]
            parts.append(f"## 第{ch_num}章\n")
            parts.append(text)
            parts.append("\n---\n")

        output.write_text("\n".join(parts), encoding="utf-8")
        logger.info("Novel assembled: %s (%d chapters, %d chars)", output, len(chapter_files), total_chars)
        return output
