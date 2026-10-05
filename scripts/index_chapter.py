"""Index a chapter into ChromaDB for semantic search.

Usage:
    python scripts/index_chapter.py \
        --story-dir data/stories/civilization-disease \
        --chapter-num 2 \
        --chapter-file data/stories/civilization-disease/outputs/chapter_002.md
"""

import argparse
import json
import re
import sys
from pathlib import Path

from chapter_workflow import chapter_log_entry, record_chapter, record_index, source_fingerprints


def parse_story_log_entry(story_log_text: str, chapter_num: int) -> dict | None:
    """Parse a chapter entry from story_log.md."""
    entry_text = chapter_log_entry(story_log_text, chapter_num)
    if not entry_text:
        return None
    title = re.split(r"[：:]", entry_text.splitlines()[0], maxsplit=1)[1].strip()

    def extract_field(field_name: str) -> str:
        m = re.search(rf"^-[ \t]+{field_name}[：:][ \t]*(.*?)(?=\n-[ \t]|\Z)",
                      entry_text, re.MULTILINE | re.DOTALL)
        return m.group(1).strip() if m else ""

    return {
        "title": title,
        "summary": extract_field("摘要"),
        "character_changes": extract_field("角色變化"),
        "foreshadow": extract_field("伏筆進展"),
        "emotional_arc": extract_field("情感基調"),
    }


def extract_character_names(character_changes: str) -> list[str]:
    """Extract character names from the 角色變化 field."""
    names = []
    for part in re.split(r"[；;]", character_changes):
        m = re.match(r"\s*([一-龥]{2,4}?)(?:的|從|展現|開始|登場|首次|建立|以|在|把|被|和|與|跟)", part)
        if m:
            names.append(m.group(1))
    return list(dict.fromkeys(names))


def index_chapter(story_dir: Path, chapter_num: int, chapter_file: Path,
                  *, allow_model_download: bool = False, retriever_factory=None) -> dict:
    """Index a real log summary and persist an honest result, even on dependency failure."""
    story_dir = Path(story_dir).resolve()
    chapter_file = Path(chapter_file).resolve()
    if not story_dir.exists():
        return {"status": "error", "error": f"Story directory not found: {story_dir}"}
    sources = None
    try:
        if chapter_num < 1 or chapter_file.parent != story_dir / "outputs" or not re.fullmatch(
                rf"chapter_0*{chapter_num}\.md", chapter_file.name):
            raise ValueError("Chapter path does not match this story/chapter")
        if not chapter_file.is_file() or not chapter_file.read_text(encoding="utf-8").strip():
            raise ValueError("Chapter file is missing or empty")
        story_log_path = story_dir / "runtime" / "story_log.md"
        if not story_log_path.is_file():
            raise ValueError("story_log.md is missing")
        entry = parse_story_log_entry(story_log_path.read_text(encoding="utf-8"), chapter_num)
        if not entry or not entry["summary"]:
            raise ValueError(f"No nonempty story_log summary for chapter {chapter_num}")
        record_chapter(story_dir, chapter_num, chapter_file)
        sources = source_fingerprints(story_dir, chapter_num,
                                      {"chapter_file": str(chapter_file.relative_to(story_dir))})
        record_index(story_dir, chapter_num, "pending", sources=sources)
        if retriever_factory is None:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from memory.retrieval import SemanticRetriever
            retriever_factory = SemanticRetriever
        retriever = retriever_factory(story_dir / "chroma",
                                      allow_model_download=allow_model_download)
        characters = extract_character_names(entry["character_changes"])
        retriever.add_chapter(chapter_id=chapter_num, summary=entry["summary"],
                              characters=characters)
        state = record_index(story_dir, chapter_num, "ok", sources=sources)
        return {"status": state["index"]["status"], "chapter_id": chapter_num,
                "title": entry["title"], "summary": entry["summary"],
                "characters": characters, "chroma_path": str(story_dir / "chroma")}
    except Exception as exc:
        status = "unavailable" if isinstance(exc, (ImportError, OSError)) else "error"
        if chapter_num > 0:
            record_index(story_dir, chapter_num, status, str(exc), sources=sources)
        return {"status": status, "chapter_id": chapter_num, "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story-dir", type=Path, required=True)
    parser.add_argument("--chapter-num", type=int, required=True)
    parser.add_argument("--chapter-file", type=Path, required=True)
    parser.add_argument("--allow-model-download", action="store_true",
                        help="Explicitly allow downloading the embedding model")
    args = parser.parse_args()
    result = index_chapter(args.story_dir, args.chapter_num, args.chapter_file,
                           allow_model_download=args.allow_model_download)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
