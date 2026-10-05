"""Assemble a CHAPTER CONTEXT PACKAGE for chapter generation.

Three-path recall:
  Path 1: Structured lookup (beat sheet tags + keyword extraction)
  Path 2: Graph traversal (conditional — causal chains, absent characters)
  Path 3: Selected memory recall (Chroma baseline OR Jev-Mem)

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
    get_args,
    get_retriever,
)
from story_snapshot import StorySnapshot
from foreshadowing import directive_threads, normalize_directives, parse_legacy_directives


def _read_text(path: Path, snapshot: StorySnapshot | None = None) -> str:
    return snapshot.read_text(path) if snapshot is not None else path.read_text(encoding="utf-8")


def _require_valid_graph(snapshot: StorySnapshot) -> None:
    if snapshot.graph_error:
        raise ValueError(f"Invalid story graph: {snapshot.graph_error}")

def load_beat(story_dir: Path, chapter_num: int,
              *, snapshot: StorySnapshot | None = None) -> dict | None:
    """Load a chapter's beat data from YAML volume plan, with markdown fallback.

    Returns a normalized dict with keys:
        title, line, objective, key_events (str), tone,
        characters (list[str]), locations (list[str]),
        foreshadow_threads (compatibility identities), foreshadow_directives
        (identity, optional display name, action, legacy matching flag),
        decision_points (only when supplied; author plans, not recorded facts)
    """
    planning_dir = story_dir / "planning"

    # Try YAML first
    for plan_file in sorted(planning_dir.glob("arc_plan_*.yaml")):
        data = yaml.safe_load(_read_text(plan_file, snapshot))
        if not data or "chapters" not in data:
            continue
        for ch in data["chapters"]:
            if ch.get("chapter") == chapter_num:
                directives = normalize_directives(ch.get("foreshadowing"))
                # Normalize key_events to string
                events = ch.get("key_events", [])
                if isinstance(events, list):
                    events = "；".join(events)
                beat = {
                    "title": ch.get("title", ""),
                    "line": ch.get("line", ""),
                    "objective": ch.get("objective", ""),
                    "key_events": events,
                    "tone": ch.get("tone", ""),
                    "characters": ch.get("characters", []),
                    "locations": ch.get("locations", []),
                    "foreshadow": "",  # raw tag (empty for YAML)
                    "foreshadow_threads": directive_threads(directives),
                    "foreshadow_directives": directives,
                    "pov": ch.get("pov"),
                    "target_length": ch.get("target_length"),
                    "source": _yaml_beat_source(plan_file, chapter_num, snapshot),
                }
                # Preserve optional decision plans verbatim. Their field types
                # are checked at context construction, like POV/target_length;
                # older YAML and markdown beats must not gain invented plans.
                if "decision_points" in ch:
                    beat["decision_points"] = ch["decision_points"]
                return beat

    # Fallback: try markdown (structure.md or arc_plan_*.md)
    beat = _load_beat_markdown(planning_dir, chapter_num, snapshot=snapshot)
    if beat:
        directives = parse_legacy_directives(beat.get("foreshadow", ""))
        beat["foreshadow_directives"] = directives
        beat["foreshadow_threads"] = directive_threads(directives)
    return beat


def _yaml_beat_source(path: Path, chapter: int, snapshot: StorySnapshot | None) -> dict | None:
    """Locate isolated chapter lines, never a sibling or an external alias target.

    Block collection end marks can point at the *next* entry's indentation.
    Actual tokens determine the content end; boundary checks reject flow entries
    sharing a line with another entry/parent rather than widening the citation.
    """
    text = _read_text(path, snapshot)
    node = yaml.compose(text)
    if not isinstance(node, yaml.MappingNode):
        return None
    for key, value in node.value:
        if key.value != "chapters":
            continue
        if (not isinstance(value, yaml.SequenceNode)
                or value.start_mark.index < key.end_mark.index):
            return None  # The chapter sequence itself is an external alias.
        for entry in value.value:
            if not isinstance(entry, yaml.MappingNode) or not any(
                k.value == "chapter" and v.value == str(chapter) for k, v in entry.value
            ):
                continue
            start, boundary = entry.start_mark.index, entry.end_mark.index
            if not value.start_mark.index <= start < boundary <= value.end_mark.index:
                return None

            def inside(current, active: set[int]) -> bool:
                # compose reuses the anchor's node/marks for aliases. Refuse
                # external anchors (and cycles), but allow aliases within a beat.
                if (id(current) in active or current.start_mark.index < start
                        or current.end_mark.index > boundary):
                    return False
                children = ([child for pair in current.value for child in pair]
                            if isinstance(current, yaml.MappingNode) else current.value
                            if isinstance(current, yaml.SequenceNode) else [])
                return all(inside(child, active | {id(current)}) for child in children)

            if not inside(entry, set()):
                return None
            ends = [token.end_mark.index for token in yaml.scan(text)
                    if start <= token.start_mark.index < token.end_mark.index <= boundary]
            if not ends:
                return None
            end = max(ends)
            while end > start and text[end - 1].isspace():
                end -= 1
            first_line = text.rfind("\n", 0, start) + 1
            last_line = text.find("\n", end)
            if last_line < 0:
                last_line = len(text)
            if (not re.fullmatch(r"[ \t]*(?:-[ \t]+)?", text[first_line:start])
                    or not re.fullmatch(r"[ \t]*,?[ \t]*(?:#[^\r\n]*)?", text[end:last_line])):
                return None
            return {"path": str(path.relative_to(path.parent.parent)),
                    "start_line": text.count("\n", 0, start) + 1,
                    "end_line": text.count("\n", 0, end - 1) + 1}
    return None


def _load_beat_markdown(planning_dir: Path, chapter_num: int,
                       *, snapshot: StorySnapshot | None = None) -> dict | None:
    """Legacy: parse beat sheet from markdown table."""
    # Try arc_plan_*.md first, then structure.md
    candidates = sorted(planning_dir.glob("arc_plan_*.md"))
    structure = planning_dir / "structure.md"
    if structure.exists():
        candidates.append(structure)

    pattern = rf"^\|\s*{chapter_num}\s*\|"
    for plan_file in candidates:
        text = _read_text(plan_file, snapshot)
        for line_num, line in enumerate(text.split("\n"), 1):
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
                        "pov": None,
                        "target_length": None,
                        "source": {"path": str(plan_file.relative_to(planning_dir.parent)),
                                   "start_line": line_num, "end_line": line_num},
                    }
    return None


def _parse_foreshadow_tag_legacy(tag: str) -> list[str]:
    """Compatibility list view; load_beat also retains each directive's action."""
    return directive_threads(parse_legacy_directives(tag))


def _match_wiki_location(loc_name: str, wiki_stems: dict[str, Path]) -> Path | None:
    """Compatibility entry point for compound location matching."""
    from chapter_context import match_wiki_location
    return match_wiki_location(loc_name, wiki_stems)


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


def _log_entries(story_dir: Path, before_chapter: int | None = None,
                 *, snapshot: StorySnapshot | None = None) -> list[tuple[int, str]]:
    """Read chapter-labelled entries; a missing chapter ID cannot pass a time bound."""
    snapshot = snapshot or StorySnapshot(story_dir)
    return sorted((chapter, entries[0]) for chapter, entries in snapshot.log_entries.items()
                  if len(entries) == 1 and (before_chapter is None or chapter < before_chapter))


def _bounded(text: str, chars: int) -> str:
    return text if len(text) <= chars else text[:chars - 1] + "…"


def build_recall_query(beat: dict) -> str:
    """Share one bounded evidence query, preserving the legacy query if absent.

    Decision clues are complete actor/field items, not inferred knowledge. Give
    them at most half of the existing 1200-character budget before using the
    remaining space for the legacy fields; a long event list cannot crowd them
    all out. Oversized individual clues are skipped, not summarized or clipped.
    This changes query input only, not recall count, result ranking or evidence.
    """
    legacy = "\n".join(str(beat.get(key, "")) for key in
                       ("objective", "key_events", "characters", "locations"))
    if "decision_points" not in beat:
        return _bounded(legacy, 1200)
    from chapter_context import normalize_decision_points

    decisions = normalize_decision_points(beat["decision_points"])
    header = "決策計畫查詢線索（待回查，不是已發生事實或角色知情）：\n"
    clues = []
    for decision in decisions:
        for field in ("character", "choice", "trigger", "reasoning", "uncertainty"):
            value = decision.get(field)
            if value is None or not value.strip():
                continue
            item = (f"character: {value}" if field == "character"
                    else f"{decision['character']}｜{field}: {value}")
            if len(header) + len("\n".join(clues + [item])) <= 600:
                clues.append(item)
    if not clues:
        return _bounded(legacy, 1200)
    decision_query = header + "\n".join(clues)
    return decision_query + "\n" + _bounded(legacy, 1200 - len(decision_query) - 1)


def get_recent_log_entries(story_dir: Path, n: int = 5,
                           before_chapter: int | None = None,
                           *, snapshot: StorySnapshot | None = None) -> str:
    """Get the last N entries from story_log.md."""
    entries = _log_entries(story_dir, before_chapter, snapshot=snapshot)
    recent = entries[-n:] if n > 0 else []
    return "\n\n".join(_bounded(text, 1500) for _, text in recent) if recent else "（尚無記錄）"


def _lines_overlap(first: str, second: str) -> bool:
    first, second = first.strip(), second.strip()
    if not first or not second:
        return first == second
    if "融合" in (first, second):
        return True
    return bool(set(re.split(r"\s*[+＋/、,]\s*", first)) &
                set(re.split(r"\s*[+＋/、,]\s*", second)))


def get_previous_chapter_ending(story_dir: Path, chapter_num: int, current_line: str,
                                 structure_text: str = "", chars: int = 500,
                                 *, snapshot: StorySnapshot | None = None) -> str:
    """Read the last N chars of the previous SAME-LINE chapter for tone continuity.

    For dual-narrative stories: ch6(S) continues from ch4(S), not ch5(R).
    For single-line stories: same as reading ch N-1.
    """
    if chapter_num <= 1:
        return "N/A — this is the first chapter"

    # Scan backwards through beat sheet to find the most recent same-line chapter
    for prev in range(chapter_num - 1, 0, -1):
        prev_row = load_beat(story_dir, prev, snapshot=snapshot) or parse_beat_sheet_row(structure_text, prev)
        if not prev_row:
            continue
        # Match line (R, S, R+S, 融合 etc.)
        # For R+S or 融合, treat as matching both lines
        prev_line = prev_row.get("line", "").strip()
        if _lines_overlap(current_line, prev_line):
            prev_file = story_dir / "outputs" / f"chapter_{prev:03d}.md"
            text = _read_text(prev_file, snapshot) if snapshot is not None or prev_file.exists() else ""
            if text:
                label = f"(from ch{prev}, same line '{current_line}')"
                if len(text) <= chars:
                    return f"{label}\n{text}"
                return f"{label}\n...{text[-chars:]}"

    return f"N/A — no previous '{current_line}' chapter found"


def get_dual_line_info(story_dir: Path, current_line: str,
                       before_chapter: int | None = None,
                       *, snapshot: StorySnapshot | None = None) -> str:
    """Get info about the other narrative line from story_log."""
    for chapter, text in reversed(_log_entries(story_dir, before_chapter, snapshot=snapshot)):
        beat = load_beat(story_dir, chapter, snapshot=snapshot)
        if beat and not _lines_overlap(current_line, beat.get("line", "")):
            return _bounded(text, 1500)
    return "N/A — 尚無另一敘事線的已完成章節"


def recall_semantic_candidates(story_dir: Path, chapter_num: int, beat: dict,
                               limit: int = 3, retriever=None,
                               *, snapshot: StorySnapshot | None = None) -> dict:
    """Recall bounded evidence with source IDs, ready for an optional candidate judge.

    Injection allows offline tests and alternative retrievers. Never initialize
    a missing store or download a model as a side effect of context assembly.
    Only summaries with current source hashes and an index receipt enter context;
    older unreceipted indexes require explicit reindexing.
    """
    snapshot = snapshot or StorySnapshot(story_dir)
    _require_valid_graph(snapshot)
    limit = min(max(limit, 0), 5)
    if chapter_num <= 1 or limit == 0:
        return {"status": "empty", "results": []}
    if retriever is None and not (story_dir / "chroma" / "chroma.sqlite3").exists():
        return {"status": "not_indexed", "results": []}
    query = build_recall_query(beat)
    try:
        retriever = retriever or get_retriever(story_dir)
        candidates = retriever.query(query_text=query, n_results=limit,
                                     max_distance=1.0, before_chapter=chapter_num)
    except Exception as exc:
        return {"status": "unavailable", "results": [], "error": type(exc).__name__}
    from chapter_workflow import chapter_status

    entries_by_chapter = snapshot.log_entries
    results, seen, skipped = [], set(), []
    for candidate in candidates:
        chapter = candidate.get("chapter_id")
        if (not isinstance(chapter, int) or isinstance(chapter, bool)
                or not 0 < chapter < chapter_num or chapter in seen):
            continue
        seen.add(chapter)
        source = snapshot.chapter_path(chapter)
        entries = entries_by_chapter.get(chapter, [])
        summaries = re.findall(r"^-[ \t]+摘要[：:][ \t]*(.*?)(?=\n-[ \t]|\Z)",
                               entries[0], re.MULTILINE | re.DOTALL) if len(entries) == 1 else []
        reason = ""
        try:
            if not snapshot.read_text(source).strip():
                reason = "missing_source"
            elif len(entries) != 1 or len(summaries) != 1 or not summaries[0].strip():
                reason = "missing_or_ambiguous_log"
            elif candidate.get("summary") != summaries[0].strip():
                reason = "summary_changed"
            else:
                state = chapter_status(story_dir, chapter, snapshot=snapshot)
                receipt = state["index"]
                if (receipt.get("status") != "ok" or not receipt.get("chapter_sha256")
                        or not receipt.get("log_sha256")):
                    reason = "index_receipt_not_current"
                else:
                    workflow = snapshot.workflow["chapters"].get(str(chapter), {})
                    tracked = any(workflow.get(key) for key in ("context", "graph", "completion"))
                    if tracked and state["lifecycle"] != "complete":
                        reason = "chapter_" + state["lifecycle"]
        except (OSError, ValueError, TypeError, AttributeError):
            reason = "unverifiable_source"
        if reason:
            skipped.append({"chapter_id": chapter, "reason": reason})
            continue
        results.append({
            "chapter_id": chapter,
            "source": str(source),
            "summary": _bounded(str(candidate.get("summary", "")), 600),
            "distance": candidate.get("distance"),
        })
        if len(results) >= limit:
            break
    if not snapshot.is_current():
        return {"status": "source_changed", "results": []}
    result = {"status": "ok" if results else "needs_reindex" if skipped else "empty",
              "results": results}
    if skipped:
        result["skipped"] = skipped
    return result


def recall_optional_memory(story_dir: Path, chapter_num: int, beat: dict,
                           query_fn=None, *, snapshot: StorySnapshot | None = None) -> tuple[dict, str]:
    """Only active Jev-Mem contributes story evidence; shadow exposes trace only.

    The explicit novel_memory query command provides shadow evidence for human
    comparison. Keeping it out of *both* context text and JSON prevents an agent
    consuming JSON from accidentally using the experimental shadow results.
    """
    if query_fn is None:
        from memory.jev_bridge import query_memory

        query_fn = query_memory
    query = build_recall_query(beat)
    try:
        kwargs = {"snapshot": snapshot} if snapshot is not None else {}
        result = query_fn(story_dir, before_chapter=chapter_num, query=query, limit=3, **kwargs)
    except Exception as exc:
        return {"status": "unavailable", "error": type(exc).__name__}, ""
    metadata = {key: result[key] for key in ("mode", "status", "trace", "error") if key in result}
    if result.get("mode") != "active" or result.get("status") != "ok":
        return metadata, ""
    evidence = [item for item in result.get("evidence", [])
                if type(item.get("chapter")) is int and 0 < item["chapter"] < chapter_num][:3]
    text = "\n".join(
        f"  [ch{item['chapter']}] {_bounded(str(item.get('text', '')), 1400)}\n"
        f"    記錄來源：{item.get('source_path', '')}；"
        f"原文：{story_dir / 'outputs' / ('chapter_%03d.md' % item['chapter'])}"
        for item in evidence
    )
    metadata["evidence"] = evidence
    return metadata, (f"\n--- JEV-MEM RECALL (past observations; verify against source) ---\n{text}\n"
                      if text else "")


def recall_chapter_memory(story_dir: Path, chapter_num: int, beat: dict,
                          *, snapshot: StorySnapshot | None = None) -> dict:
    """Select one evidence backend; shadow results never enter writer input.

    Structured context and the canonical story graph are assembled separately.
    An unavailable active backend does not silently activate another index.
    """
    from memory.jev_bridge import memory_mode

    semantic = {"status": "not_selected", "results": []}
    jev = {"mode": "off", "status": "disabled", "trace": {}}
    kwargs = {"snapshot": snapshot} if snapshot is not None else {}
    if snapshot is not None:
        _require_valid_graph(snapshot)
        snapshot.read_text(story_dir / "planning" / "memory_config.json")
    try:
        mode = memory_mode(story_dir)
    except (OSError, ValueError, TypeError) as exc:
        return {"selected_backend": "none", "semantic_recall": semantic,
                "jev_memory": {"status": "error", "error": type(exc).__name__},
                "text": "--- MEMORY RECALL ---\n  （記憶設定無效；僅使用結構化資料與故事圖譜）"}

    if mode == "active":
        jev, text = recall_optional_memory(story_dir, chapter_num, beat, **kwargs)
        if jev.get("mode") not in (None, mode):
            jev = {"mode": mode, "status": "configuration_changed", "trace": {}}
            text = ""
        jev.setdefault("mode", mode)
        if not text:
            text = f"--- JEV-MEM RECALL ---\n  （召回狀態：{jev['status']}；未改用 Chroma）"
        return {"selected_backend": "jev-mem", "semantic_recall": semantic,
                "jev_memory": jev, "text": text}

    semantic = recall_semantic_candidates(story_dir, chapter_num, beat, **kwargs)
    text = "\n".join(
        f"  [ch{item['chapter_id']}] {item['summary']}\n    原文：{item['source']}"
        for item in semantic["results"]
    ) or f"  （語意召回狀態：{semantic['status']}）"
    if mode == "shadow":
        jev, _ = recall_optional_memory(story_dir, chapter_num, beat, **kwargs)
        # A concurrent config edit must not turn shadow JSON into active evidence.
        jev.pop("evidence", None)
        if jev.get("mode") not in (None, mode):
            jev = {"mode": mode, "status": "configuration_changed", "trace": {}}
        jev.setdefault("mode", mode)
    return {"selected_backend": "chroma", "semantic_recall": semantic,
            "jev_memory": jev,
            "text": "--- SEMANTIC RECALL (past chapter summaries; verify against source text) ---\n" + text}


def _graph_has_later_state(raw: dict, chapter_num: int) -> bool:
    """Cumulative graph prose has no historical snapshots; do not rewind it."""
    chapter_keys = {"chapters", "planted_in", "hinted_in", "resolved_in", "introduced_in",
                    "cause_ch", "effect_ch", "chapter", "number"}

    def visit(value, key=""):
        if isinstance(value, dict):
            return any(visit(item, name) for name, item in value.items())
        if isinstance(value, list):
            return any(visit(item, key) for item in value)
        if key in chapter_keys:
            ids = re.findall(r"\d+", str(value))
            return any(int(chapter) >= chapter_num for chapter in ids)
        return False

    return visit(raw)


def _graph_snapshot(story_dir: Path, raw: dict, chapter_num: int,
                    *, snapshot: StorySnapshot | None = None) -> dict | None:
    """Use recorded chapter diffs when available; legacy snapshots cannot rewind."""
    if "nodes" in raw and ("links" in raw or "edges" in raw):
        if "_history" in raw:
            raise ValueError("Tracked graph history requires the flat snapshot format")
        # Convert the already-read bytes; graph.load() would reopen a changed file.
        import networkx as nx
        from networkx.readwrite import json_graph
        from story_graph_nx import StoryGraph

        graph = StoryGraph(story_dir / "runtime" / "story_graph.json")
        try:
            graph.G = nx.MultiDiGraph(json_graph.node_link_graph(
                raw, directed=True, edges="edges" if "edges" in raw else "links"))
            raw = graph.to_flat()
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ValueError(f"Invalid legacy node-link graph: {exc}") from exc
    if raw.get("_history"):
        from story_graph_nx import StoryGraph

        graph = StoryGraph(story_dir / "runtime" / "story_graph.json")
        graph.load_flat(raw)
        try:
            return graph.flat_before(chapter_num)
        except ValueError:
            return None
    if (_graph_has_later_state(raw, chapter_num)
            or any(chapter >= chapter_num for chapter, _ in _log_entries(story_dir, snapshot=snapshot))):
        return None
    return raw


def check_graph_conditions(story_dir: Path, characters: list[str], chapter_num: int,
                           foreshadow_names: list[str] = None,
                           *, snapshot: StorySnapshot | None = None) -> dict:
    """Query the NetworkX story graph for structured context."""
    json_path = story_dir / "runtime" / "story_graph.json"
    result = {"needed": False, "numerical_values": "", "graph_context": "", "status": "missing"}

    snapshot = snapshot or StorySnapshot(story_dir)
    _require_valid_graph(snapshot)
    if not snapshot.read_bytes(json_path):
        return result

    raw = _graph_snapshot(story_dir, snapshot.graph, chapter_num, snapshot=snapshot)
    if raw is None:
        result["status"] = "skipped_newer_state"
        result["graph_context"] = "略過目前累積圖譜：含本章或後續章節，無可回溯的章前快照；請使用前章原文與記錄。"
        return result

    from story_graph_nx import StoryGraph

    graph = StoryGraph(json_path)
    result["status"] = "ok"
    graph.load_flat(raw)

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
        result["numerical_values"] = _bounded(values_text, 2000)

    if sections:
        result["graph_context"] = _bounded("\n\n".join(sections), 4000)
        result["needed"] = True

    return result


def get_concept_tracking(story_dir: Path, before_chapter: int | None = None,
                         *, snapshot: StorySnapshot | None = None) -> str:
    """Read concept introduction tracking from story_graph.json."""
    json_path = story_dir / "runtime" / "story_graph.json"
    snapshot = snapshot or StorySnapshot(story_dir)
    _require_valid_graph(snapshot)
    if not snapshot.read_bytes(json_path):
        return "N/A"

    raw = snapshot.graph
    if before_chapter is not None:
        raw = _graph_snapshot(story_dir, raw, before_chapter, snapshot=snapshot)
        if raw is None:
            return "N/A — 累積圖譜含本章或後續章節，無章前快照"
    concepts = raw.get("concepts")
    if not concepts:
        return "N/A"

    lines = ["Concepts NOT yet introduced to the reader (introduce naturally when first used):"]
    found_any = False
    for name, info in concepts.items():
        if info.get("introduced_in") is None:
            lines.append(f"  ⚠ {name}")
            found_any = True
    if not found_any:
        return "All concepts have been introduced to the reader."
    return _bounded("\n".join(lines), 1500)


def main():
    args = get_args(
        ("--chapter", {"type": int, "required": True}),
        ("--format", {"type": str, "default": "text", "choices": ["text", "json"]}),
        ("--max-context-chars", {"type": int, "help": "Exact character budget for writer context (not tokens)"}),
    )

    story_dir = Path(args.story_dir)
    chapter_num = args.chapter

    import sys as _sys

    try:
        snapshot = StorySnapshot(story_dir)
        _require_valid_graph(snapshot)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=_sys.stderr)
        _sys.exit(1)

    # === Path 1: Structured lookup ===

    # Load beat data (YAML first, markdown fallback)
    beat = load_beat(story_dir, chapter_num, snapshot=snapshot)
    if not beat:
        print(f"ERROR: chapter {chapter_num} not found in any volume plan or structure.md", file=_sys.stderr)
        _sys.exit(1)

    from chapter_context import build_chapter_context, context_budget, normalize_pov
    from chapter_workflow import record_context

    try:
        context_budget(snapshot, args.max_context_chars)
        normalize_pov(beat.get("pov"))
        graph_path = story_dir / "runtime" / "story_graph.json"
        projected = _graph_snapshot(story_dir, snapshot.graph, chapter_num, snapshot=snapshot)
        graph_status = "missing" if not graph_path.exists() else "skipped_newer_state" if projected is None else "ok"
        recall = recall_chapter_memory(story_dir, chapter_num, beat, snapshot=snapshot)
        prev_ending = get_previous_chapter_ending(story_dir, chapter_num, beat["line"], snapshot=snapshot)
        dual_line = get_dual_line_info(story_dir, beat["line"], before_chapter=chapter_num, snapshot=snapshot)
        bundle = build_chapter_context(snapshot, chapter_num, beat, projected, recall,
                                       max_chars=args.max_context_chars,
                                       previous_ending=prev_ending, graph_status=graph_status, dual_line=dual_line)
        if not snapshot.is_current():
            raise ValueError("Story changed while assembling context; assemble it again")
        record_context(story_dir, chapter_num, snapshot=snapshot)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=_sys.stderr)
        _sys.exit(1)

    if args.format == "json":
        # Evidence is present once, inside the bounded package. Diagnostics do
        # not re-expose omitted/clipped backend prose outside that budget.
        semantic = {k: v for k, v in recall["semantic_recall"].items() if k != "results"}
        jev = {k: v for k, v in recall["jev_memory"].items() if k != "evidence"}
        json.dump({"context_package": bundle.text, "chapter": chapter_num, "title": beat["title"],
                   "context_metadata": bundle.metadata,
                   "semantic_recall": semantic,
                   "graph_status": graph_status,
                   "jev_memory": jev,
                   "selected_memory_backend": recall["selected_backend"]},
                  __import__('sys').stdout, ensure_ascii=False, indent=2)
    else:
        print(bundle.text)
        from context_bundle import format_context_diagnostics

        diagnostics = format_context_diagnostics(bundle.metadata)
        if diagnostics:
            print("\n" + diagnostics)

if __name__ == "__main__":
    main()
