"""Style editor agent - audits style consistency across chapters."""

from __future__ import annotations

from pathlib import Path

from config.models import StyleReport
from agents.base_agent import BaseAgent


class StyleEditorAgent(BaseAgent):
    """Audits a volume for style consistency across chapters."""

    def audit(
        self,
        volume_name: str,
        chapter_dir: Path,
        character_voices: str = "",
        batch_size: int = 5,
    ) -> StyleReport:
        """Audit style consistency for a volume.

        Processes chapters in batches to fit context window.

        Args:
            volume_name: Name of the volume being audited.
            chapter_dir: Directory containing chapter_NNN.md files.
            character_voices: Character speaking style reference.
            batch_size: Number of chapters to process at once.

        Returns:
            StyleReport with issues and consistency score.
        """
        chapter_files = sorted(chapter_dir.glob("chapter_*.md"))
        if not chapter_files:
            return StyleReport(
                volume_name=volume_name, total_chapters=0,
                overall_consistency_score=10.0, summary="No chapters to audit.",
            )

        all_issues = []
        for i in range(0, len(chapter_files), batch_size):
            batch = chapter_files[i:i + batch_size]
            chapters_text = ""
            for f in batch:
                text = f.read_text(encoding="utf-8")
                ch_num = f.stem.split("_")[-1]
                chapters_text += f"\n### 第{ch_num}章\n{text[:2000]}\n"  # First 2000 chars

            messages = self.prompt.render(
                volume_name=volume_name,
                total_chapters=len(chapter_files),
                character_voices=character_voices or "（無角色聲音參考）",
                chapters_text=chapters_text,
            )

            try:
                report = self.call_llm(
                    messages, response_model=StyleReport,
                    temperature=0.3, max_tokens=2000,
                )
                all_issues.extend(report.issues)
            except Exception as e:
                self.logger.warning("Style audit batch failed: %s", e)

        final = StyleReport(
            volume_name=volume_name,
            total_chapters=len(chapter_files),
            issues=all_issues,
            overall_consistency_score=max(0, 10.0 - len(all_issues) * 0.5),
            summary=f"Found {len(all_issues)} style issues across {len(chapter_files)} chapters.",
        )
        self.logger.info("Style audit: %s", final.summary)
        return final
