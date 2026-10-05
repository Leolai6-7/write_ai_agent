"""Narrow JSON source references that cannot spill into adjacent story history.

A line reference is safe only when its boundary lines contain the requested
member/array entry and whitespace (plus an optional trailing comma). Compact
JSON therefore deliberately has no usable child spans. Callers may describe the
projection instead, but must not replace a missing span with the entire graph.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

try:
    from .context_bundle import SourceRef
    from .story_snapshot import text_hash
except ImportError:
    from context_bundle import SourceRef
    from story_snapshot import text_hash


@lru_cache(maxsize=4)
def _json_spans(text: str) -> dict[tuple, tuple[int, int]]:
    """Decode structure while retaining exact offsets, including member names."""
    decoder = json.JSONDecoder()
    spans: dict[tuple, tuple[int, int]] = {}

    def whitespace(pos: int) -> int:
        while pos < len(text) and text[pos] in " \t\r\n":
            pos += 1
        return pos

    def scan(pos: int, pointer: tuple, member_start: int | None = None) -> int:
        pos = whitespace(pos)
        start = pos if member_start is None else member_start
        if pos >= len(text):
            raise ValueError("Missing JSON value")
        if text[pos] == "{":
            pos = whitespace(pos + 1)
            keys = set()
            if pos < len(text) and text[pos] == "}":
                end = pos + 1
            else:
                while True:
                    key_start = pos
                    key, pos = decoder.raw_decode(text, pos)
                    if not isinstance(key, str) or key in keys:
                        raise ValueError("Invalid or duplicate JSON key")
                    keys.add(key)
                    pos = whitespace(pos)
                    if pos >= len(text) or text[pos] != ":":
                        raise ValueError("Missing JSON member colon")
                    pos = whitespace(scan(pos + 1, pointer + (key,), key_start))
                    if pos < len(text) and text[pos] == "}":
                        end = pos + 1
                        break
                    if pos >= len(text) or text[pos] != ",":
                        raise ValueError("Missing JSON member separator")
                    pos = whitespace(pos + 1)
        elif text[pos] == "[":
            pos = whitespace(pos + 1)
            index = 0
            if pos < len(text) and text[pos] == "]":
                end = pos + 1
            else:
                while True:
                    pos = whitespace(scan(pos, pointer + (index,)))
                    index += 1
                    if pos < len(text) and text[pos] == "]":
                        end = pos + 1
                        break
                    if pos >= len(text) or text[pos] != ",":
                        raise ValueError("Missing JSON array separator")
                    pos = whitespace(pos + 1)
        else:
            _, end = decoder.raw_decode(text, pos)
        spans[pointer] = (start, end)
        return end

    if whitespace(scan(0, ())) != len(text):
        raise ValueError("Trailing JSON content")
    return spans


def json_source_ref(snapshot, path: Path, pointer: list[str | int]) -> SourceRef | None:
    """Locate one exact JSON member, or return None if its lines are not isolated."""
    if (not isinstance(pointer, list)
            or any(type(part) not in (str, int) or (type(part) is int and part < 0)
                   for part in pointer)):
        raise ValueError("JSON pointer must contain text keys or nonnegative integer indexes")
    if not pointer:
        return None  # Never turn a missing narrow reference into a whole-file one.
    path = Path(path)
    if not path.is_absolute():
        path = snapshot.story_dir / path
    path = path.resolve()
    try:
        relative = path.relative_to(snapshot.story_dir)
    except ValueError:
        return None
    text = snapshot.read_text(path)
    try:
        span = _json_spans(text).get(tuple(pointer))
    except (ValueError, TypeError, RecursionError):
        return None
    if span is None:
        return None
    start, end = span
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    if text[line_start:start].strip() or text[end:line_end].strip() not in ("", ","):
        return None
    return SourceRef(str(relative), text.count("\n", 0, start) + 1,
                     text.count("\n", 0, end - 1) + 1, text_hash(text))


_NAMED_SECTIONS = {
    "foreshadowing": ("foreshadowing_updates", "thread"),
    "values": ("new_values", "setting"),
    "concepts": ("concepts_introduced", "name"),
}
_LIST_SECTIONS = {"causal_chains": ("cause", "effect"), "mirrors": ("r_line", "s_line")}


def _matches(section: str, candidate: dict, item) -> bool:
    if not isinstance(candidate, dict):
        return False
    if section in _NAMED_SECTIONS:
        return candidate.get(_NAMED_SECTIONS[section][1]) == item
    if not isinstance(item, dict):
        return False
    if not all(candidate.get(field) == item.get(field) for field in _LIST_SECTIONS[section]):
        return False
    if section == "causal_chains":
        # Identical prose may describe different chapter pairs. When a projected
        # item identifies them, do not cite another occurrence with the same text.
        return all(str(candidate.get(field, "")) == str(item[field])
                   for field in ("cause_ch", "effect_ch") if item.get(field) not in (None, ""))
    return True


def _section_pointers(data: dict, prefix: list, section: str, item) -> list[list]:
    rows = data.get(section) or ({} if section in _NAMED_SECTIONS else [])
    if section in _NAMED_SECTIONS:
        return [prefix + [section, item]] if isinstance(item, str) and item in rows else []
    return [prefix + [section, index] for index, row in enumerate(rows)
            if _matches(section, row, item)]


def _graph_pointers(snapshot, before_chapter: int, section: str, item) -> list[list]:
    if type(before_chapter) is not int or before_chapter <= 0:
        raise ValueError("before_chapter must be positive")
    if section not in _NAMED_SECTIONS and section not in _LIST_SECTIONS:
        raise ValueError(f"Unsupported graph source section: {section}")
    if snapshot.graph_error:
        return []
    graph = snapshot.graph
    history = graph.get("_history")
    if history:
        pointers = _section_pointers(history["baseline"], ["_history", "baseline"], section, item)
        diff_section = _NAMED_SECTIONS.get(section, (section, None))[0]
        for chapter, diff in sorted(history["diffs"].items(), key=lambda pair: int(pair[0])):
            if int(chapter) >= before_chapter:
                continue
            for index, candidate in enumerate(diff.get(diff_section) or []):
                if _matches(section, candidate, item):
                    pointer = ["_history", "diffs", chapter, diff_section, index]
                    if section == "values":
                        pointers = [pointer]
                    else:
                        pointers.append(pointer)
    else:
        pointers = _section_pointers(graph, [], section, item)
    return pointers


def graph_sources(snapshot, before_chapter: int, section: str, item) -> tuple[SourceRef, ...]:
    """Cite only the baseline/prior diffs contributing to one projected graph item.

    ``item`` is a name for mapping sections, or the projected record for causal
    chains/mirrors. The caller must first establish that a legacy flat graph can
    be projected at this boundary. Tracked graphs never cite the latest derived
    outer snapshot. Overwritten numerical settings cite only the latest source;
    accumulated thread/concept/edge histories retain their contributing sources.
    """
    pointers = _graph_pointers(snapshot, before_chapter, section, item)
    path = snapshot.story_dir / "runtime" / "story_graph.json"
    return tuple(dict.fromkeys(ref for pointer in pointers
                               if (ref := json_source_ref(snapshot, path, pointer)) is not None))


def graph_source_chapters(snapshot, before_chapter: int, section: str, item) -> tuple[int, ...]:
    """Return explicitly recorded contributor chapters, even for compact JSON.

    Legacy/baseline records with no chapter metadata cannot identify a workflow
    receipt; they contribute no invented chapter. This helper does not itself
    decide lifecycle validity or authorize an otherwise unsafe legacy projection.
    """
    chapters: set[int] = set()
    for pointer in _graph_pointers(snapshot, before_chapter, section, item):
        if pointer[:2] == ["_history", "diffs"]:
            chapters.add(int(pointer[2]))
            continue
        record = snapshot.graph
        for part in pointer:
            record = record[part]
        for field in {
            "foreshadowing": ("planted_in", "hinted_in", "resolved_in"),
            "concepts": ("introduced_in",),
            "causal_chains": ("cause_ch", "effect_ch"),
        }.get(section, ()):
            values = record.get(field)
            for value in values if isinstance(values, list) else [values]:
                if value is not None and str(value).isdigit() and 0 < int(value) < before_chapter:
                    chapters.add(int(value))
    return tuple(sorted(chapters))
