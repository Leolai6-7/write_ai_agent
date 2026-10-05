"""Per-story receipts for required chapter steps and optional semantic indexing."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

try:
    from .story_snapshot import StorySnapshot
    from .story_snapshot import chapter_log_entry as chapter_log_entry
except ImportError:  # Standalone CLI and the existing script imports.
    from story_snapshot import StorySnapshot
    from story_snapshot import chapter_log_entry as chapter_log_entry

STATE_NAME = "chapter_workflow.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _context_signature(story_dir: Path, chapter: int) -> str:
    return StorySnapshot(story_dir).context_signature(chapter)


def _load(story_dir: Path) -> dict:
    path = story_dir / "runtime" / STATE_NAME
    if not path.exists():
        return {"version": 1, "chapters": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("chapters"), dict):
        raise ValueError(f"Invalid workflow state: {path}")
    return data


@contextmanager
def _edit(story_dir: Path):
    runtime = story_dir / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime / ".chapter_workflow.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = _load(story_dir)
        yield data
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=runtime,
                                         prefix=".chapter_workflow-", delete=False) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        tmp_path.replace(runtime / STATE_NAME)


def _entry(data: dict, chapter: int) -> dict:
    if isinstance(chapter, bool) or not isinstance(chapter, int) or chapter < 1:
        raise ValueError("chapter must be a positive integer")
    return data["chapters"].setdefault(str(chapter), {})


def source_fingerprints(story_dir: Path, chapter: int, entry: dict | None = None,
                        *, snapshot: StorySnapshot | None = None) -> dict:
    snapshot = snapshot or StorySnapshot(story_dir)
    if snapshot.story_dir != Path(story_dir).resolve():
        raise ValueError("Snapshot belongs to a different story")
    return snapshot.source_fingerprints(chapter, entry)


def _evidence(snapshot: StorySnapshot, chapter: int, entry: dict) -> dict:
    sources = snapshot.source_fingerprints(chapter, entry)
    try:
        context = snapshot.context_signature(chapter)
    except (ValueError, OSError, AttributeError, TypeError):
        context = None
    return {**sources, "context_sha256": context,
            "history_sha256": snapshot.graph_signature(chapter),
            "chapter_diff_sha256": snapshot.chapter_diff_signature(chapter)}


def _completion_receipt(entry: dict, evidence: dict) -> dict | None:
    """Migrate only evidence that proves the old graph receipt's local diff.

    Older receipts have no per-chapter diff hash. A changed graph prefix cannot
    establish whether its own diff stayed unchanged, so it is not inferred.
    """
    completion = entry.get("completion")
    if isinstance(completion, dict) and completion.get("chapter_diff_sha256"):
        return completion
    graph = entry.get("graph", {})
    context = entry.get("context", {})
    if (context.get("prior_story_sha256") and evidence["history_sha256"]
            and graph.get("history_sha256") == evidence["history_sha256"]
            and all(graph.get(key) == evidence[key] and evidence[key]
                    for key in ("chapter_sha256", "log_sha256"))):
        return {**evidence, "context_sha256": context["prior_story_sha256"],
                "at": graph.get("at"), "inferred": True}
    return None


def _status(story_dir: Path, chapter: int, entry: dict,
            snapshot: StorySnapshot | None = None) -> dict:
    snapshot = snapshot or StorySnapshot(story_dir)
    evidence = _evidence(snapshot, chapter, entry)
    sources = {key: evidence[key] for key in ("chapter_sha256", "log_sha256")}
    missing = []
    context_signature = evidence["context_sha256"]
    if not context_signature or entry.get("context", {}).get("prior_story_sha256") != context_signature:
        missing.append("context")
    if not sources["chapter_sha256"]:
        missing.append("chapter")
    if not sources["log_sha256"]:
        missing.append("story_log")
    graph_receipt = entry.get("graph", {})
    graph_signature = evidence["history_sha256"]
    if (not graph_signature or graph_receipt.get("history_sha256") != graph_signature
            or any(graph_receipt.get(key) != value or value is None
                   for key, value in sources.items())):
        missing.append("story_graph")
    index = dict(entry.get("index", {"status": "not_started"}))
    if index.get("status") in {"ok", "pending"} and any(
            index.get(k) != v for k, v in sources.items()):
        index["status"] = "stale"
    completion = _completion_receipt(entry, evidence)
    unchanged = bool(completion and all(
        evidence[key] and completion.get(key) == evidence[key]
        for key in ("chapter_sha256", "log_sha256", "chapter_diff_sha256")
    ))
    reviewable = bool(missing and unchanged and not snapshot.graph_error
                      and context_signature and graph_signature
                      and not entry.get("active_writing"))
    lifecycle = "complete" if not missing else "needs_review" if reviewable else "writing"
    review_unavailable_reason = None
    if missing and not reviewable:
        if snapshot.graph_error:
            review_unavailable_reason = "Graph history is invalid; repair it before reviewing"
        elif entry.get("active_writing"):
            review_unavailable_reason = "Chapter writing has been reopened; finish the required steps"
        elif not completion:
            review_unavailable_reason = "No completion receipt proves the unchanged chapter and its own graph diff"
        else:
            review_unavailable_reason = "The chapter, log, or its own graph diff changed; update the required steps"
    return {"story_dir": str(story_dir), "chapter": chapter,
            "complete": not missing, "missing": missing, "index": index,
            "session_id": entry.get("session_id"), "lifecycle": lifecycle,
            "blocking": lifecycle == "writing", "review_allowed": reviewable,
            "graph_error": snapshot.graph_error,
            "review_unavailable_reason": review_unavailable_reason}


def chapter_status(story_dir: Path, chapter: int,
                   *, snapshot: StorySnapshot | None = None) -> dict:
    story_dir = Path(story_dir).resolve()
    snapshot = snapshot or StorySnapshot(story_dir)
    if snapshot.story_dir != story_dir:
        raise ValueError("Snapshot belongs to a different story")
    return _status(story_dir, chapter, snapshot.workflow["chapters"].get(str(chapter), {}), snapshot)


def _remember_completion(story_dir: Path, chapter: int, entry: dict,
                         snapshot: StorySnapshot) -> dict:
    status = _status(story_dir, chapter, entry, snapshot)
    if status["complete"]:
        evidence = _evidence(snapshot, chapter, entry)
        entry["completion"] = {"at": _now(), **evidence}
        entry.pop("active_writing", None)
    return status


def record_context(story_dir: Path, chapter: int, context_path: Path | None = None,
                   *, snapshot: StorySnapshot | None = None) -> dict:
    story_dir = Path(story_dir).resolve()
    snapshot = snapshot or StorySnapshot(story_dir)
    if snapshot.story_dir != story_dir:
        raise ValueError("Snapshot belongs to a different story")
    receipt = {"at": _now(), "prior_story_sha256": snapshot.context_signature(chapter)}
    # Planning evolves at arc review; retain evidence without reopening old chapters.
    receipt["planning_sha256"] = {
        str(path.relative_to(story_dir)): _hash(snapshot.read_text(path))
        for path in sorted((story_dir / "planning").glob("*"))
        if path.is_file() and path.suffix in {".md", ".yaml", ".yml"}
    }
    if context_path is not None:
        receipt["sha256"] = _hash(snapshot.read_text(Path(context_path)))
    with _edit(story_dir) as data:
        if not snapshot.is_current():
            raise ValueError("Story changed while assembling context; assemble it again")
        entry = _entry(data, chapter)
        if not _status(story_dir, chapter, entry, snapshot)["complete"]:
            entry["active_writing"] = True
        entry["context"] = receipt
        status = _remember_completion(story_dir, chapter, entry, snapshot)
    return status


def record_chapter(story_dir: Path, chapter: int, chapter_file: Path | None = None,
                   session_id: str | None = None) -> dict:
    story_dir = Path(story_dir).resolve()
    with _edit(story_dir) as data:
        snapshot = StorySnapshot(story_dir)
        entry = _entry(data, chapter)
        if chapter_file is not None:
            path = Path(chapter_file).resolve()
            if path.parent != story_dir / "outputs" or not re.fullmatch(
                    rf"chapter_0*{chapter}\.md", path.name):
                raise ValueError("Chapter path does not match story/chapter")
            entry["chapter_file"] = str(path.relative_to(story_dir))
        if session_id:
            entry["session_id"] = session_id
        entry["chapter_written_at"] = _now()
        entry["chapter_sha256"] = snapshot.source_fingerprints(chapter, entry)["chapter_sha256"]
        status = _remember_completion(story_dir, chapter, entry, snapshot)
    return status


def record_graph(story_dir: Path, chapter: int) -> dict:
    """Call only after successfully validating and saving this chapter's diff.

    The receipt binds chapter/log content; graph SHA is historical evidence,
    because subsequent chapters may legitimately extend the shared graph.
    """
    story_dir = Path(story_dir).resolve()
    snapshot = StorySnapshot(story_dir)
    signature = snapshot.graph_signature(chapter)
    if not signature:
        raise ValueError("story_graph has no validated diff history for this chapter")
    with _edit(story_dir) as data:
        if not snapshot.is_current():
            raise ValueError("Story changed before recording its graph receipt; retry the graph update")
        entry = _entry(data, chapter)
        sources = snapshot.source_fingerprints(chapter, entry)
        entry["active_writing"] = True
        entry["graph"] = {"at": _now(),
                          "graph_sha256": _hash(json.dumps(snapshot.graph, ensure_ascii=False, sort_keys=True)),
                          "history_sha256": signature, **sources}
        status = _remember_completion(story_dir, chapter, entry, snapshot)
    return status


def acknowledge_review(story_dir: Path, chapter: int, reason: str,
                       *, snapshot: StorySnapshot | None = None) -> dict:
    """Accept unchanged downstream content after checking changed prior evidence."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Review acknowledgement requires a nonempty reason")
    story_dir = Path(story_dir).resolve()
    snapshot = snapshot or StorySnapshot(story_dir)
    if snapshot.story_dir != story_dir:
        raise ValueError("Snapshot belongs to a different story")
    with _edit(story_dir) as data:
        if not snapshot.is_current():
            raise ValueError("Story changed during review; review the current evidence again")
        entry = _entry(data, chapter)
        status = _status(story_dir, chapter, entry, snapshot)
        if not status["review_allowed"]:
            raise ValueError("Review can acknowledge only unchanged completed chapters with prior-source drift")
        evidence = _evidence(snapshot, chapter, entry)
        review = {"at": _now(), "reason": reason.strip(), **evidence,
                  "evidence_sha256": _hash(json.dumps(evidence, sort_keys=True))}
        entry.setdefault("reviews", []).append(review)
        entry["context"]["prior_story_sha256"] = evidence["context_sha256"]
        entry["graph"]["history_sha256"] = evidence["history_sha256"]
        status = _remember_completion(story_dir, chapter, entry, snapshot)
    return status


def record_index(story_dir: Path, chapter: int, status: str, detail: str = "",
                 sources: dict | None = None) -> dict:
    if status not in {"pending", "ok", "unavailable", "error", "not_selected"}:
        raise ValueError(f"Unknown index status: {status}")
    story_dir = Path(story_dir).resolve()
    with _edit(story_dir) as data:
        snapshot = StorySnapshot(story_dir)
        entry = _entry(data, chapter)
        entry["index"] = {"status": status, "at": _now(), "detail": detail,
                          **(sources if sources is not None else
                             snapshot.source_fingerprints(chapter, entry))}
        result = _remember_completion(story_dir, chapter, entry, snapshot)
    return result


def queue_index(story_dir: Path, chapter: int) -> dict:
    """Queue the baseline index only when selected by the story's memory mode."""
    story_dir = Path(story_dir).resolve()
    try:
        # The hooks also run this module as a standalone script.
        project_root = str(Path(__file__).resolve().parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from memory.jev_bridge import memory_mode

        mode = memory_mode(story_dir)
    except (ValueError, OSError, ImportError) as exc:
        return record_index(story_dir, chapter, "error", f"Cannot select memory route: {exc}")
    with _edit(story_dir) as data:
        snapshot = StorySnapshot(story_dir)
        entry = _entry(data, chapter)
        status = _remember_completion(story_dir, chapter, entry, snapshot)
        if mode == "active":
            entry["index"] = {
                "status": "not_selected", "at": _now(),
                "detail": "Jev-Mem active mode selects its own memory index; baseline Chroma is not selected.",
                **snapshot.source_fingerprints(chapter, entry),
            }
            return _status(story_dir, chapter, entry, snapshot)
        if not status["complete"] or status["index"]["status"] in {"ok", "pending"}:
            return status
        entry["index"] = {"status": "pending", "at": _now(),
                          **snapshot.source_fingerprints(chapter, entry)}
        filename = entry.get("chapter_file", f"outputs/chapter_{chapter:03d}.md")
    try:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("index_chapter.py")),
             "--story-dir", str(story_dir), "--chapter-num", str(chapter),
             "--chapter-file", str(story_dir / filename)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return record_index(story_dir, chapter, "error", str(exc))
    return chapter_status(story_dir, chapter)


def handle_post_tool(project_dir: Path, payload: dict) -> list[dict]:
    tool_input = payload.get("tool_input", {})
    filename = tool_input.get("file_path", tool_input.get("file", ""))
    if not filename:
        return []
    path = Path(filename)
    if not path.is_absolute():
        path = project_dir / path
    path = path.resolve()
    if path.parent.parent.parent != (project_dir / "data" / "stories").resolve():
        return []
    match = re.fullmatch(r"chapter_(\d+)\.md", path.name)
    if match and path.parent.name == "outputs":
        return [record_chapter(path.parent.parent, int(match.group(1)), path,
                               payload.get("session_id"))]
    if path.name in {"story_log.md", "story_graph.json"} and path.parent.name == "runtime":
        story_dir = path.parent.parent
        snapshot = StorySnapshot(story_dir)
        return [chapter_status(story_dir, int(ch), snapshot=snapshot)
                for ch in snapshot.workflow["chapters"]]
    return []


def pending_chapters(project_dir: Path, session_id: str | None = None) -> list[dict]:
    pending = []
    for path in (project_dir / "data" / "stories").glob(f"*/runtime/{STATE_NAME}"):
        story_dir = path.parent.parent
        snapshot = StorySnapshot(story_dir)
        for ch, entry in snapshot.workflow["chapters"].items():
            if session_id and entry.get("session_id") not in (None, session_id):
                continue
            status = _status(story_dir, int(ch), entry, snapshot)
            if not status["complete"]:
                pending.append(status)
    return pending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["post-tool", "stop", "status", "review"])
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--story-dir", type=Path)
    parser.add_argument("--chapter-num", type=int)
    parser.add_argument("--reason", help="Why unchanged chapter content still fits the changed prior evidence")
    args = parser.parse_args()
    try:
        if args.command in {"status", "review"}:
            if args.story_dir is None or args.chapter_num is None:
                parser.error(f"{args.command} requires --story-dir and --chapter-num")
            result = (acknowledge_review(args.story_dir, args.chapter_num, args.reason)
                      if args.command == "review" else chapter_status(args.story_dir, args.chapter_num))
            print(json.dumps(result, ensure_ascii=False))
            return 0
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        statuses = (handle_post_tool(args.project_dir, payload) if args.command == "post-tool"
                    else pending_chapters(args.project_dir, payload.get("session_id")))
        for status in statuses:
            message = ("complete" if status["complete"] else
                       "needs review: " + ", ".join(status["missing"])
                       if status["lifecycle"] == "needs_review" else
                       "writing; missing " + ", ".join(status["missing"]))
            print(f"WORKFLOW: {Path(status['story_dir']).name} chapter {status['chapter']}: "
                  f"{message}; index={status['index']['status']}", file=sys.stderr)
        return 2 if args.command == "stop" and any(status["blocking"] for status in statuses) else 0
    except (ValueError, OSError) as exc:
        print(f"WORKFLOW ERROR: {exc}", file=sys.stderr)
        return 2 if args.command == "stop" else 1


if __name__ == "__main__":
    raise SystemExit(main())
