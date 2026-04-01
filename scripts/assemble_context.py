"""Assemble a CHAPTER CONTEXT PACKAGE for chapter generation.

Three-path recall:
  Path 1: Structured lookup (beat sheet tags + keyword extraction)
  Path 2: Graph traversal (conditional — causal chains, absent characters)
  Path 3: Semantic search (ChromaDB vector similarity)

Usage:
    python scripts/assemble_context.py \
        --story-dir data/stories/civilization-disease \
        --chapter 2
"""

import re
from pathlib import Path

from _common import (
    get_args, get_retriever, extract_section, extract_sections_from_files,
    parse_md_table, PROJECT_ROOT,
)


def parse_beat_sheet_row(structure_text: str, chapter_num: int) -> dict:
    """Parse a single row from the beat sheet table."""
    pattern = rf"^\|\s*{chapter_num}\s*\|"
    for line in structure_text.split("\n"):
        if re.match(pattern, line):
            cells = [c.strip() for c in line.split("|")]
            # cells: ['', num, title, line, objective, events, tone, characters, location, foreshadow, '']
            if len(cells) >= 10:
                return {
                    "title": cells[2],
                    "line": cells[3],
                    "objective": cells[4],
                    "key_events": cells[5],
                    "tone": cells[6],
                    "characters": [c.strip() for c in cells[7].split(",") if c.strip()],
                    "locations": [c.strip() for c in cells[8].split(",") if c.strip()],
                    "foreshadow": cells[9],
                }
    return {}


def extract_keywords(key_events: str) -> list[str]:
    """Extract Chinese names/nouns from key events text."""
    # Remove numbering like ① ② etc
    text = re.sub(r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫]", "", key_events)
    # Find Chinese name-like tokens (2-4 chars between punctuation/spaces)
    names = re.findall(r"[\u4e00-\u9fff]{2,4}", text)
    # Filter out common non-name words
    stopwords = {"模擬", "文明", "世界", "研究", "日常", "第一", "注意", "微小", "異常", "所有",
                 "完全", "相同", "產生", "懷疑", "完美", "崩潰", "規律", "學者"}
    return list(set(n for n in names if n not in stopwords))


def parse_foreshadow_tag(tag: str) -> list[str]:
    """Convert foreshadow tags like '①plant ⑨hint' to thread names."""
    num_map = {"①": "一", "②": "二", "③": "三", "④": "四", "⑤": "五",
               "⑥": "六", "⑦": "七", "⑧": "八", "⑨": "九", "⑩": "十",
               "⑪": "十一", "⑫": "十二"}
    threads = []
    for symbol, chinese in num_map.items():
        if symbol in tag:
            threads.append(f"伏筆{chinese}")
    return threads


def get_recent_log_entries(story_dir: Path, n: int = 5) -> str:
    """Get the last N entries from story_log.md."""
    log_path = story_dir / "runtime" / "story_log.md"
    if not log_path.exists():
        return "（尚無記錄）"
    text = log_path.read_text(encoding="utf-8")
    # Split by ## entries
    entries = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    entries = [e.strip() for e in entries if e.strip() and e.strip().startswith("## ")]
    recent = entries[-n:] if len(entries) > n else entries
    return "\n\n".join(recent) if recent else "（尚無記錄）"


def get_dual_line_info(story_dir: Path, current_line: str) -> str:
    """Get info about the other narrative line from story_log."""
    log_path = story_dir / "runtime" / "story_log.md"
    if not log_path.exists():
        return "N/A"
    text = log_path.read_text(encoding="utf-8")
    entries = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    entries = [e.strip() for e in entries if e.strip() and e.strip().startswith("## ")]
    if not entries:
        return "N/A — 尚無已完成章節"
    # Return the most recent entry (which is likely the other line)
    return entries[-1]


def check_graph_conditions(story_dir: Path, characters: list[str], chapter_num: int) -> dict:
    """Query the NetworkX story graph for context."""
    from story_graph_nx import StoryGraph

    json_path = story_dir / "runtime" / "story_graph.json"
    result = {"needed": False, "numerical_values": "", "causal_context": ""}

    if not json_path.exists():
        # Fallback: try to build from markdown
        md_path = story_dir / "runtime" / "story_graph.md"
        if md_path.exists():
            graph = StoryGraph(json_path)
            graph.sync_from_markdown(md_path)
            graph.save()
        else:
            return result

    graph = StoryGraph(json_path)
    graph.load()

    # Always get numerical values
    values_text = graph.get_all_values()
    if values_text:
        result["numerical_values"] = values_text
        result["needed"] = True

    # Check for absent characters
    for char in characters:
        history = graph.get_character_history(char)
        if history.get("found") and history["chapters"]:
            last_ch = max(history["chapters"])
            if chapter_num - last_ch > 5:
                result["causal_context"] += f"\n{char} 最後出場在 ch{last_ch}：{history['events']}"
                result["needed"] = True

    # Get causal context for this chapter
    ch_context = graph.get_chapter_context(chapter_num)
    if ch_context.get("found"):
        if ch_context["events"]:
            result["causal_context"] += "\n相關事件：" + "；".join(ch_context["events"])
            result["needed"] = True

    # Get all causal chains (for general context)
    mirrors = graph.get_mirrors()
    if mirrors:
        mirror_lines = [f"R: {m['r_line']} ↔ S: {m['s_line']}" for m in mirrors]
        result["causal_context"] += "\n\n雙線鏡像：\n" + "\n".join(mirror_lines)
        result["needed"] = True

    return result


def do_semantic_search(story_dir: Path, query: str) -> str:
    """Run semantic search if ChromaDB has indexed chapters."""
    chroma_dir = story_dir / "chroma"
    if not chroma_dir.exists():
        return "N/A — no indexed chapters yet"
    try:
        retriever = get_retriever(story_dir)
        if retriever.get_count() == 0:
            return "N/A — no indexed chapters yet"
        results = retriever.query(query_text=query, n_results=3, max_distance=1.0)
        if not results:
            return "N/A — no relevant results"
        lines = []
        for r in results:
            lines.append(f"Chapter {r['chapter_id']} (distance: {r['distance']:.3f}): {r['summary']}")
        return "\n".join(lines)
    except Exception as e:
        return f"N/A — error: {e}"


def main():
    args = get_args(
        ("--chapter", {"type": int, "required": True}),
        ("--format", {"type": str, "default": "text", "choices": ["text", "json"]}),
    )

    story_dir = Path(args.story_dir)
    chapter_num = args.chapter

    # === Path 1: Structured lookup ===

    # Parse beat sheet
    structure_path = story_dir / "planning" / "structure.md"
    if not structure_path.exists():
        print(f"ERROR: structure.md not found at {structure_path}", file=__import__('sys').stderr)
        __import__('sys').exit(1)

    structure_text = structure_path.read_text(encoding="utf-8")
    beat = parse_beat_sheet_row(structure_text, chapter_num)
    if not beat:
        print(f"ERROR: chapter {chapter_num} not found in beat sheet", file=__import__('sys').stderr)
        __import__('sys').exit(1)

    # Read always-needed files
    brief_path = story_dir / "planning" / "story_brief.md"
    brief_text = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""

    recent_log = get_recent_log_entries(story_dir)

    # Source files for structured search
    world_files = [
        story_dir / "world" / "world_bible.md",
    ]
    char_file = story_dir / "world" / "character_cast.md"
    foreshadow_file = story_dir / "planning" / "foreshadowing.md"

    # Extract character profiles
    character_profiles = []
    for name in beat["characters"]:
        section = extract_sections_from_files([char_file], name, "## ")
        if section:
            character_profiles.append(section)
        else:
            character_profiles.append(f"⚠ {name} not found in character_cast.md — profile missing")

    # Extract location descriptions
    location_descriptions = []
    for loc in beat["locations"]:
        section = extract_sections_from_files(world_files, loc, "### ")
        if not section:
            # Try ## level
            section = extract_sections_from_files(world_files, loc, "## ")
        if section:
            location_descriptions.append(section)

    # Extract foreshadowing threads
    foreshadow_threads = []
    thread_names = parse_foreshadow_tag(beat["foreshadow"])
    for thread_name in thread_names:
        if foreshadow_file.exists():
            text = foreshadow_file.read_text(encoding="utf-8")
            section = extract_section(text, thread_name, "### ")
            if section:
                foreshadow_threads.append(section)

    # Keyword-based supplementary search
    keywords = extract_keywords(beat["key_events"])
    keyword_supplements = []
    for kw in keywords:
        if kw not in beat["characters"] and kw not in beat["locations"]:
            for f in world_files + [char_file]:
                section = extract_sections_from_files([f], kw, "### ")
                if section and section not in keyword_supplements:
                    keyword_supplements.append(section)

    # === Path 2: Graph traversal ===
    graph_data = check_graph_conditions(story_dir, beat["characters"], chapter_num)

    # === Path 3: Semantic search ===
    query = f"{beat['objective']} {beat['key_events']}"
    semantic_results = do_semantic_search(story_dir, query)

    # === Dual-line awareness ===
    dual_line = get_dual_line_info(story_dir, beat["line"])

    # === Extract prose style from brief ===
    prose_style = ""
    style_match = re.search(r"\*\*散文風格\*\*[：:]\s*(.+?)(?=\n-|\n\n|\Z)", brief_text, re.DOTALL)
    if style_match:
        prose_style = style_match.group(1).strip()

    # === Format output ===
    package = f"""=== CHAPTER CONTEXT PACKAGE — Chapter {chapter_num}: {beat['title']} ===

STORY: {prose_style if prose_style else '(see story_brief.md)'}
LINE: {beat['line']}
TARGET LENGTH: 5,000-8,000 字
OBJECTIVE: {beat['objective']}
KEY EVENTS: {beat['key_events']}
EMOTIONAL TONE: {beat['tone']}

--- CHARACTER PROFILES ---
{chr(10).join(character_profiles) if character_profiles else '(none)'}

--- SETTING ---
{chr(10).join(location_descriptions) if location_descriptions else '(no location descriptions found)'}

--- FORESHADOWING ---
{chr(10).join(foreshadow_threads) if foreshadow_threads else '(none for this chapter)'}

--- RECENT CHAPTERS ---
{recent_log}

--- CAUSAL CONTEXT ---
{graph_data['causal_context'] if graph_data['causal_context'] else 'N/A — no cross-arc references'}

--- NUMERICAL VALUES (metadata — not all values should appear in prose) ---
{graph_data['numerical_values'] if graph_data['numerical_values'] else 'Check story_graph if referencing previously established numbers.'}
Note: Characters may not know exact numbers — use sensory descriptions instead of stating precise values unless the character has measuring instruments.

--- SEMANTIC RECALL ---
{semantic_results}

--- KEYWORD SUPPLEMENTS ---
{chr(10).join(keyword_supplements) if keyword_supplements else '(none)'}

--- DUAL-LINE AWARENESS ---
{dual_line}
==="""

    if args.format == "json":
        import json
        json.dump({"context_package": package, "chapter": chapter_num, "title": beat["title"]},
                  __import__('sys').stdout, ensure_ascii=False, indent=2)
    else:
        print(package)


if __name__ == "__main__":
    main()
