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

import json
import re
from pathlib import Path

import yaml

from _common import (
    get_args, get_retriever, extract_section, extract_sections_from_files,
    parse_md_table, PROJECT_ROOT,
)

# --- Thread number mapping (shared by YAML and legacy markdown) ---
THREAD_NUM_MAP = {
    1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
    6: "六", 7: "七", 8: "八", 9: "九", 10: "十",
    11: "十一", 12: "十二",
}
THREAD_SYMBOL_MAP = {"①": 1, "②": 2, "③": 3, "④": 4, "⑤": 5,
                     "⑥": 6, "⑦": 7, "⑧": 8, "⑨": 9, "⑩": 10,
                     "⑪": 11, "⑫": 12}


def load_beat(story_dir: Path, chapter_num: int) -> dict | None:
    """Load a chapter's beat data from YAML volume plan, with markdown fallback.

    Returns a normalized dict with keys:
        title, line, objective, key_events (str), tone,
        characters (list[str]), locations (list[str]),
        foreshadow_threads (list[str] like ['伏筆九'])
    """
    planning_dir = story_dir / "planning"

    # Try YAML first
    for plan_file in sorted(planning_dir.glob("arc_plan_*.yaml")):
        data = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
        if not data or "chapters" not in data:
            continue
        for ch in data["chapters"]:
            if ch.get("chapter") == chapter_num:
                # Normalize foreshadowing to thread names
                threads = []
                for f in ch.get("foreshadowing") or []:
                    if isinstance(f, dict):
                        # {thread: 9, action: plant}
                        num = f.get("thread")
                        if num and num in THREAD_NUM_MAP:
                            threads.append(f"伏筆{THREAD_NUM_MAP[num]}")
                    elif isinstance(f, str):
                        # "⑨plant" format — extract circled number
                        for symbol, num in THREAD_SYMBOL_MAP.items():
                            if symbol in f:
                                threads.append(f"伏筆{THREAD_NUM_MAP[num]}")
                # Normalize key_events to string
                events = ch.get("key_events", [])
                if isinstance(events, list):
                    events = "；".join(events)
                return {
                    "title": ch.get("title", ""),
                    "line": ch.get("line", ""),
                    "objective": ch.get("objective", ""),
                    "key_events": events,
                    "tone": ch.get("tone", ""),
                    "characters": ch.get("characters", []),
                    "locations": ch.get("locations", []),
                    "foreshadow": "",  # raw tag (empty for YAML)
                    "foreshadow_threads": threads,
                }

    # Fallback: try markdown (structure.md or arc_plan_*.md)
    beat = _load_beat_markdown(planning_dir, chapter_num)
    if beat:
        beat["foreshadow_threads"] = _parse_foreshadow_tag_legacy(beat.get("foreshadow", ""))
    return beat


def _load_beat_markdown(planning_dir: Path, chapter_num: int) -> dict | None:
    """Legacy: parse beat sheet from markdown table."""
    # Try arc_plan_*.md first, then structure.md
    candidates = sorted(planning_dir.glob("arc_plan_*.md"))
    structure = planning_dir / "structure.md"
    if structure.exists():
        candidates.append(structure)

    pattern = rf"^\|\s*{chapter_num}\s*\|"
    for plan_file in candidates:
        text = plan_file.read_text(encoding="utf-8")
        for line in text.split("\n"):
            if re.match(pattern, line):
                cells = [c.strip() for c in line.split("|")]
                if len(cells) >= 10:
                    # Split characters on both , and 、
                    chars = re.split(r"[,、]", cells[7])
                    chars = [c.strip() for c in chars if c.strip()]
                    locs = re.split(r"[,、]", cells[8])
                    locs = [c.strip() for c in locs if c.strip()]
                    return {
                        "title": cells[2],
                        "line": cells[3],
                        "objective": cells[4],
                        "key_events": cells[5],
                        "tone": cells[6],
                        "characters": chars,
                        "locations": locs,
                        "foreshadow": cells[9],
                    }
    return None


def _parse_foreshadow_tag_legacy(tag: str) -> list[str]:
    """Legacy: convert markdown foreshadow tags like '⑨plant' to thread names."""
    threads = []
    for symbol, num in THREAD_SYMBOL_MAP.items():
        if symbol in tag:
            threads.append(f"伏筆{THREAD_NUM_MAP[num]}")
    return threads


def extract_keywords(key_events: str) -> list[str]:
    """Extract Chinese names/nouns from key events text."""
    text = re.sub(r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫]", "", key_events)
    names = re.findall(r"[\u4e00-\u9fff]{2,4}", text)
    stopwords = {"模擬", "文明", "世界", "研究", "日常", "第一", "注意", "微小", "異常", "所有",
                 "完全", "相同", "產生", "懷疑", "完美", "崩潰", "規律", "學者"}
    return list(set(n for n in names if n not in stopwords))


# Legacy compat alias (unused but kept for any external callers)
def parse_foreshadow_tag(tag: str) -> list[str]:
    return _parse_foreshadow_tag_legacy(tag)


# Legacy compat alias
def parse_beat_sheet_row(structure_text: str, chapter_num: int) -> dict:
    """Legacy wrapper — prefer load_beat()."""
    pattern = rf"^\|\s*{chapter_num}\s*\|"
    for line in structure_text.split("\n"):
        if re.match(pattern, line):
            cells = [c.strip() for c in line.split("|")]
            if len(cells) >= 10:
                chars = re.split(r"[,、]", cells[7])
                chars = [c.strip() for c in chars if c.strip()]
                locs = re.split(r"[,、]", cells[8])
                locs = [c.strip() for c in locs if c.strip()]
                return {
                    "title": cells[2], "line": cells[3],
                    "objective": cells[4], "key_events": cells[5],
                    "tone": cells[6], "characters": chars,
                    "locations": locs, "foreshadow": cells[9],
                }
    return {}


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


def get_previous_chapter_ending(story_dir: Path, chapter_num: int, current_line: str,
                                 structure_text: str, chars: int = 500) -> str:
    """Read the last N chars of the previous SAME-LINE chapter for tone continuity.

    For dual-narrative stories: ch6(S) continues from ch4(S), not ch5(R).
    For single-line stories: same as reading ch N-1.
    """
    if chapter_num <= 1:
        return "N/A — this is the first chapter"

    # Scan backwards through beat sheet to find the most recent same-line chapter
    for prev in range(chapter_num - 1, 0, -1):
        prev_row = parse_beat_sheet_row(structure_text, prev)
        if not prev_row:
            continue
        # Match line (R, S, R+S, 融合 etc.)
        # For R+S or 融合, treat as matching both lines
        prev_line = prev_row.get("line", "").strip()
        if current_line in prev_line or prev_line in current_line or prev_line == current_line:
            prev_file = story_dir / "outputs" / f"chapter_{prev:03d}.md"
            if prev_file.exists():
                text = prev_file.read_text(encoding="utf-8")
                label = f"(from ch{prev}, same line '{current_line}')"
                if len(text) <= chars:
                    return f"{label}\n{text}"
                return f"{label}\n...{text[-chars:]}"

    return f"N/A — no previous '{current_line}' chapter found"


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
        return result

    graph = StoryGraph(json_path)

    # Try flat JSON format first, fall back to node_link_data
    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)
    if "characters" in raw:
        # Flat format (produced by progress-updater agent)
        graph.load_flat(raw)
    else:
        # Legacy node_link_data format
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
    """Read concept introduction tracking from story_graph.json (or legacy .md)."""
    json_path = story_dir / "runtime" / "story_graph.json"

    # Try JSON first (flat format has "concepts" key)
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            raw = json.load(f)
        concepts = raw.get("concepts")
        if concepts:
            lines = ["Concepts NOT yet introduced to the reader (introduce naturally when first used):"]
            found_any = False
            for name, info in concepts.items():
                if info.get("introduced_in") is None:
                    lines.append(f"  ⚠ {name}")
                    found_any = True
            if not found_any:
                return "All concepts have been introduced to the reader."
            return "\n".join(lines)

    # Legacy fallback: read from story_graph.md
    md_path = story_dir / "runtime" / "story_graph.md"
    if not md_path.exists():
        return "N/A"
    text = md_path.read_text(encoding="utf-8")
    section = extract_section(text, "概念引入追蹤", "## ")
    if not section:
        return "N/A"

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

    import sys as _sys

    # === Path 1: Structured lookup ===

    # Load beat data (YAML first, markdown fallback)
    beat = load_beat(story_dir, chapter_num)
    if not beat:
        print(f"ERROR: chapter {chapter_num} not found in any volume plan or structure.md", file=_sys.stderr)
        _sys.exit(1)

    # For same-line chapter lookup, we need all beat sheets (markdown format)
    # concatenated so get_previous_chapter_ending can scan backwards
    all_beat_text = ""
    structure_path = story_dir / "planning" / "structure.md"
    if structure_path.exists():
        all_beat_text = structure_path.read_text(encoding="utf-8")
    for plan_file in sorted((story_dir / "planning").glob("arc_plan_*.md")):
        all_beat_text += "\n" + plan_file.read_text(encoding="utf-8")

    # Read always-needed files
    brief_path = story_dir / "planning" / "story_brief.md"
    brief_text = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""

    recent_log = get_recent_log_entries(story_dir)

    # Build navigation references (agent reads files itself)
    char_file = story_dir / "world" / "character_cast.md"
    world_file = story_dir / "world" / "world_bible.md"
    foreshadow_file = story_dir / "planning" / "foreshadowing.md"

    # Character references — verify each exists in file
    char_refs = []
    char_text = char_file.read_text(encoding="utf-8") if char_file.exists() else ""
    for name in beat["characters"]:
        # Find the actual heading
        heading_match = re.search(rf"^(## .+{re.escape(name)}.*)$", char_text, re.MULTILINE)
        if heading_match:
            char_refs.append(f"  {name} → {char_file} {heading_match.group(1)}")
        else:
            char_refs.append(f"  ⚠ {name} — NOT FOUND in character_cast.md")

    # Location references
    loc_refs = []
    world_text = world_file.read_text(encoding="utf-8") if world_file.exists() else ""
    for loc in beat["locations"]:
        heading_match = re.search(rf"^(###? .+{re.escape(loc)}.*)$", world_text, re.MULTILINE)
        if heading_match:
            loc_refs.append(f"  {loc} → {world_file} {heading_match.group(1)}")
        else:
            loc_refs.append(f"  ⚠ {loc} — NOT FOUND in world_bible.md")

    # Foreshadowing references
    thread_names = beat.get("foreshadow_threads", []) or _parse_foreshadow_tag_legacy(beat.get("foreshadow", ""))
    foreshadow_refs = []
    for thread_name in thread_names:
        foreshadow_refs.append(f"  {thread_name} → {foreshadow_file} ### {thread_name}")

    # === Path 2: Graph traversal ===
    # Extract foreshadow thread names for graph chain lookup
    foreshadow_names_for_graph = []
    for t in thread_names:
        # thread_names are like "伏筆九" — extract the Chinese numeral part
        name = t.replace("伏筆", "")
        if name:
            foreshadow_names_for_graph.append(name)
    graph_data = check_graph_conditions(story_dir, beat["characters"], chapter_num, foreshadow_names_for_graph)

    # === Path 3: Semantic search ===
    query = f"{beat['objective']} {beat['key_events']}"
    semantic_results = do_semantic_search(story_dir, query)

    # === Previous chapter ending ===
    prev_ending = get_previous_chapter_ending(story_dir, chapter_num, beat["line"], all_beat_text)

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

LINE: {beat['line']}
TARGET LENGTH: 5,000-8,000 字
OBJECTIVE: {beat['objective']}
KEY EVENTS: {beat['key_events']}
EMOTIONAL TONE: {beat['tone']}

--- READ THESE (character profiles, settings, foreshadowing) ---
CHARACTERS:
{chr(10).join(char_refs)}

LOCATIONS:
{chr(10).join(loc_refs)}

FORESHADOWING:
{chr(10).join(foreshadow_refs) if foreshadow_refs else '  (none for this chapter)'}

--- PREVIOUS CHAPTER ENDING (for tone continuity) ---
{prev_ending}

--- RECENT CHAPTERS (story_log) ---
{recent_log}

--- GRAPH WARNINGS ---
{graph_data['graph_context'] if graph_data.get('graph_context') else 'N/A'}

--- NUMERICAL VALUES (use sensory descriptions, not exact numbers unless character has instruments) ---
{graph_data['numerical_values'] if graph_data['numerical_values'] else 'N/A'}

--- CONCEPT INTRODUCTION STATUS ---
{concept_tracking}

--- DUAL-LINE AWARENESS ---
{dual_line}
==="""

    # Preflight warnings to stderr
    missing_locs = [r for r in loc_refs if "NOT FOUND" in r]
    if missing_locs:
        print(f"⚠ PREFLIGHT: locations not found in world_bible — agent will improvise", file=_sys.stderr)

    if args.format == "json":
        import json
        json.dump({"context_package": package, "chapter": chapter_num, "title": beat["title"]},
                  __import__('sys').stdout, ensure_ascii=False, indent=2)
    else:
        print(package)


if __name__ == "__main__":
    main()
