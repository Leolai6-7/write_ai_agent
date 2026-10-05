"""Source-backed canon facts and explicit character knowledge/beliefs.

Only chapter narrative updates populate this state. Existing graph events,
reader-facing concept introductions, and author plans are not inferred knowledge.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re


KINDS = {"fact", "knowledge", "belief"}
STATUSES = {"active", "retired"}


def _positive(value, label: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value


def normalized_hash(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def narrative_identity(record: dict) -> tuple[str, str | None]:
    return record["kind"], record.get("character")


def validate_narrative_record(record: dict, *, chapter: int | None = None,
                              stored: bool = False, require_hash: bool = False) -> None:
    if not isinstance(record, dict):
        raise ValueError("narrative_updates entries must be objects")
    allowed = {"id", "kind", "character", "text", "status", "source"}
    if stored:
        allowed |= {"introduced_in", "updated_in"}
    if set(record) - allowed:
        raise ValueError("Unknown narrative record fields")
    _text(record.get("id"), "narrative id")
    _text(record.get("text"), "narrative text")
    if not isinstance(record.get("kind"), str) or record["kind"] not in KINDS:
        raise ValueError("narrative kind must be fact, knowledge, or belief")
    if record["kind"] == "fact":
        if "character" in record:
            raise ValueError("fact records must not assign character knowledge")
    else:
        _text(record.get("character"), "narrative character")
    if not isinstance(record.get("status", "active"), str) or record.get("status", "active") not in STATUSES:
        raise ValueError("narrative status must be active or retired")
    source = record.get("source")
    if not isinstance(source, dict) or set(source) - {"chapter", "start_line", "end_line", "sha256"}:
        raise ValueError("narrative source must contain chapter, start_line, end_line, and optional sha256")
    source_chapter = _positive(source.get("chapter"), "source.chapter")
    start = _positive(source.get("start_line"), "source.start_line")
    end = _positive(source.get("end_line"), "source.end_line")
    if start > end:
        raise ValueError("source.start_line must not exceed source.end_line")
    digest = source.get("sha256")
    if (require_hash or "sha256" in source) and (
            not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
        raise ValueError("source.sha256 must be a verified 64-character digest; prepare chapter sources first")
    if chapter is not None and source_chapter != chapter:
        raise ValueError("source.chapter must equal diff.chapter (the chapter containing textual evidence)")
    if stored:
        introduced = _positive(record.get("introduced_in"), "introduced_in")
        updated = _positive(record.get("updated_in"), "updated_in")
        if introduced > updated or source_chapter != updated:
            raise ValueError("Narrative dates must follow the chapter of the update's textual evidence")


def validate_narrative_updates(updates, chapter: int, *, require_hash: bool = False) -> None:
    if not isinstance(updates, list):
        raise ValueError("narrative_updates must be a list")
    seen = set()
    for record in updates:
        validate_narrative_record(record, chapter=chapter, require_hash=require_hash)
        if record["id"] in seen:
            raise ValueError(f"Duplicate narrative id in one chapter: {record['id']}")
        seen.add(record["id"])


def validate_narrative_state(state) -> None:
    if not isinstance(state, dict):
        raise ValueError("narrative_state must be an object keyed by stable id")
    for record_id, record in state.items():
        validate_narrative_record(record, stored=True, require_hash=True)
        if record_id != record["id"]:
            raise ValueError("narrative_state key must equal record.id")


def prepare_narrative_sources(diff: dict, story_or_snapshot) -> dict:
    """Validate actual manuscript spans and stamp a copy before graph mutation."""
    try:
        from .story_graph_nx import validate_chapter_diff
        from .story_snapshot import StorySnapshot
    except ImportError:
        from story_graph_nx import validate_chapter_diff
        from story_snapshot import StorySnapshot

    validate_chapter_diff(diff)
    prepared = deepcopy(diff)
    updates = prepared.get("narrative_updates", [])
    if not updates:
        return prepared
    snapshot = (story_or_snapshot if hasattr(story_or_snapshot, "chapter_path")
                else StorySnapshot(Path(story_or_snapshot)))
    if snapshot.graph_error:
        raise ValueError(f"Invalid story graph: {snapshot.graph_error}")
    for record in updates:
        source = record["source"]
        path = snapshot.chapter_path(source["chapter"])
        text = snapshot.read_text(path)
        if not text.strip():
            raise ValueError(f"Narrative source manuscript missing or empty: {path.name}")
        lines = text.splitlines()
        if source["end_line"] > len(lines):
            raise ValueError(f"Narrative source line range exceeds {path.name}")
        excerpt = "\n".join(lines[source["start_line"] - 1:source["end_line"]])
        if not excerpt.strip():
            raise ValueError(f"Narrative source span is empty: {path.name}")
        digest = normalized_hash(text)
        if "sha256" in source and source["sha256"].lower() != digest:
            raise ValueError(f"Narrative source hash does not match current {path.name}")
        source["sha256"] = digest
        record.setdefault("status", "active")
    if not snapshot.is_current():
        raise ValueError("Story changed while preparing narrative sources; retry with current sources")
    return prepared


def select_narrative_state(snapshot, projected_flat: dict, before_chapter: int,
                           pov: list[str]) -> dict:
    """Select verified latest records from a chapter-bounded graph projection."""
    _positive(before_chapter, "before_chapter")
    if not isinstance(pov, list) or any(not isinstance(name, str) or not name.strip() for name in pov):
        raise ValueError("pov must be an explicit list of character names (or an empty list)")
    if snapshot.graph_error:
        raise ValueError(f"Invalid story graph: {snapshot.graph_error}")
    state = projected_flat.get("narrative_state", {})
    validate_narrative_state(state)
    output = {"status": "missing_pov" if not pov else "empty", "canon": [], "pov": [], "excluded": []}
    for record_id, original in sorted(state.items()):
        record = deepcopy(original)
        source = record["source"]
        reason = ""
        if record.get("status", "active") == "retired":
            reason = "retired"
        elif max(record["introduced_in"], record["updated_in"], source["chapter"]) >= before_chapter:
            reason = "future"
        elif record["kind"] != "fact" and record["character"] not in pov:
            reason = "wrong_pov" if pov else "missing_pov"
        else:
            path = snapshot.chapter_path(source["chapter"])
            text = snapshot.read_text(path)
            lines = text.splitlines()
            if not text.strip():
                reason = "missing_source"
            elif source["sha256"].lower() != normalized_hash(text):
                reason = "stale_source"
            elif source["end_line"] > len(lines):
                reason = "invalid_span"
            else:
                excerpt = "\n".join(lines[source["start_line"] - 1:source["end_line"]])
                if not excerpt.strip():
                    reason = "empty_span"
                else:
                    source["path"] = path.relative_to(snapshot.story_dir).as_posix()
                    record["excerpt"] = excerpt
        if reason:
            output["excluded"].append({"id": record_id, "reason": reason})
            continue
        output["canon" if record["kind"] == "fact" else "pov"].append(record)
    if not snapshot.is_current():
        return {"status": "source_changed", "canon": [], "pov": [],
                "excluded": [{"id": record_id, "reason": "source_changed"} for record_id in sorted(state)]}
    if pov and (output["canon"] or output["pov"]):
        output["status"] = "ok"
    return output
