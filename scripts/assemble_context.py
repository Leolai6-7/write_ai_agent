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


def check_graph_conditions(story_dir: Path, characters: list[str], chapter_num: int,
                           foreshadow_names: list[str] = None) -> dict:
    """Query the NetworkX story graph for structured context."""
    from story_graph_nx import StoryGraph

    json_path = story_dir / "runtime" / "story_graph.json"
    result = {"needed": False, "numerical_values": "", "graph_context": ""}

    if not json_path.exists():
        md_path = story_dir / "runtime" / "story_graph.md"
        if md_path.exists():
            graph = StoryGraph(json_path)
            graph.sync_from_markdown(md_path)
            graph.save()
        else:
            return result

    graph = StoryGraph(json_path)
    graph.load()

    sections = []

    # 1. Active foreshadows (planted but not resolved)
    active = graph.get_active_foreshadows()
    if active:
        lines = ["Active foreshadows (planted but not resolved):"]
        for f in active:
            chain = f"planted ch{','.join(map(str, f['planted_in']))}" if f['planted_in'] else ""
            hint = f", hinted ch{','.join(map(str, f['hinted_in']))}" if f['hinted_in'] else ""
            lines.append(f"  {f['name']} — {f['status']} ({chain}{hint})")
        sections.append("\n".join(lines))

    # 2. This chapter's foreshadow chains
    if foreshadow_names:
        chains = []
        for name in foreshadow_names:
            chain = graph.get_foreshadow_chain(name)
            if chain:
                parts = []
                if chain['planted_in']:
                    parts.append(f"planted ch{','.join(map(str, chain['planted_in']))}")
                if chain['hinted_in']:
                    parts.append(f"hinted ch{','.join(map(str, chain['hinted_in']))}")
                if chain['resolved_in']:
                    parts.append(f"resolved ch{','.join(map(str, chain['resolved_in']))}")
                chains.append(f"  {chain['name']} — {' → '.join(parts)} [{chain['status']}]")
        if chains:
            sections.append("This chapter's foreshadow chains:\n" + "\n".join(chains))

    # 3. Causal context — trace back from characters' recent events
    causal_lines = []
    for char in characters:
        history = graph.get_character_history(char)
        if history.get("found") and history["events"]:
            # Extract keywords from events for causal tracing
            events_text = history["events"]
            for keyword in re.findall(r'[\u4e00-\u9fff]{2,6}', events_text):
                causes = graph.trace_causation(keyword, depth=2)
                if causes:
                    for c in causes:
                        if c not in causal_lines:
                            causal_lines.append(c)
        # Also flag absent characters
        if history.get("found") and history["chapters"]:
            last_ch = max(history["chapters"])
            if chapter_num - last_ch > 5:
                causal_lines.append(f"⚠ {char} 最後出場在 ch{last_ch}")

    if causal_lines:
        sections.append("Causal context:\n" + "\n".join(f"  {c}" for c in causal_lines[:10]))

    # 4. Dual-line mirrors
    mirrors = graph.get_mirrors()
    if mirrors:
        mirror_lines = [f"  R: {m['r_line']} ↔ S: {m['s_line']}" for m in mirrors]
        sections.append("Dual-line mirrors:\n" + "\n".join(mirror_lines))

    # 5. Numerical values (always)
    values_text = graph.get_all_values()
    if values_text:
        result["numerical_values"] = values_text

    if sections:
        result["graph_context"] = "\n\n".join(sections)
        result["needed"] = True

    return result


def get_concept_tracking(story_dir: Path) -> str:
    """Read concept introduction tracking table from story_graph."""
    graph_path = story_dir / "runtime" / "story_graph.md"
    if not graph_path.exists():
        return "N/A"
    text = graph_path.read_text(encoding="utf-8")
    section = extract_section(text, "概念引入追蹤", "## ")
    if not section:
        return "N/A"

    # Extract just the not-yet-introduced concepts
    lines = ["Concepts NOT yet introduced to the reader (introduce naturally when first used):"]
    found_any = False
    for line in section.split("\n"):
        if not line.strip().startswith("|"):
            continue
        if ("❌" in line or "⚠" in line) and "概念" not in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2:
                lines.append(f"  ⚠ {cells[0]}")
                found_any = True

    if not found_any:
        return "All concepts have been introduced to the reader."
    return "\n".join(lines)


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
    # Parse foreshadow names from beat sheet for chain lookup
    foreshadow_names_for_graph = []
    num_map = {"①": "一", "②": "二", "③": "三", "④": "四", "⑤": "五",
               "⑥": "六", "⑦": "七", "⑧": "八", "⑨": "九", "⑩": "十"}
    for symbol, chinese in num_map.items():
        if symbol in beat.get("foreshadow", ""):
            foreshadow_names_for_graph.append(chinese)
    graph_data = check_graph_conditions(story_dir, beat["characters"], chapter_num, foreshadow_names_for_graph)

    # === Path 3: Semantic search ===
    query = f"{beat['objective']} {beat['key_events']}"
    semantic_results = do_semantic_search(story_dir, query)

    # === Concept introduction tracking ===
    concept_tracking = get_concept_tracking(story_dir)

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

--- GRAPH CONTEXT ---
{graph_data['graph_context'] if graph_data.get('graph_context') else 'N/A'}

--- NUMERICAL VALUES (metadata — not all values should appear in prose) ---
{graph_data['numerical_values'] if graph_data['numerical_values'] else 'Check story_graph if referencing previously established numbers.'}
Note: Characters may not know exact numbers — use sensory descriptions instead of stating precise values unless the character has measuring instruments.

--- SEMANTIC RECALL ---
{semantic_results}

--- KEYWORD SUPPLEMENTS ---
{chr(10).join(keyword_supplements) if keyword_supplements else '(none)'}

--- CONCEPT INTRODUCTION STATUS ---
{concept_tracking}

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
