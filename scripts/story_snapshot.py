"""Read-once source view shared by workflow checks and memory adapters.

Snapshots are operation-local, not persistent caches. Recreate after a worker
returns; use is_current before saving a receipt for data assembled from this view.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

try:
    from .story_graph_nx import validate_flat_history
except ImportError:  # Direct scripts/*.py invocation.
    from story_graph_nx import validate_flat_history


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def value_hash(value) -> str:
    return text_hash(json.dumps(value, ensure_ascii=False, sort_keys=True))


def parse_log_entries(text: str) -> dict[int, list[str]]:
    """One parser, retaining duplicates so no caller silently picks a version."""
    entries: dict[int, list[str]] = {}
    for match in re.finditer(
        r"^##[ \t]+第[ \t]*(\d+)[ \t]*章[ \t]*[：:].*?(?=^##[ \t]|\Z)",
        text, re.MULTILINE | re.DOTALL,
    ):
        chapter = int(match.group(1))
        if chapter > 0:
            entries.setdefault(chapter, []).append(match.group(0).strip())
    return entries


def chapter_log_entry(text: str, chapter: int) -> str | None:
    matches = parse_log_entries(text).get(chapter, [])
    return matches[0] if len(matches) == 1 else None


def has_summary(entry: str | None) -> bool:
    summary = re.search(r"^-[ \t]+摘要[：:][ \t]*(.*?)(?=\n-[ \t]|\Z)",
                        entry or "", re.MULTILINE | re.DOTALL)
    return bool(summary and summary.group(1).strip())


def _token(path: Path):
    try:
        stat = path.stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
    except FileNotFoundError:
        return None


class StorySnapshot:
    """Canonical graph and immutable-by-convention source bytes for one operation."""

    def __init__(self, story_dir: Path):
        self.story_dir = Path(story_dir).resolve()
        self._bytes: dict[Path, bytes] = {}
        self._tokens: dict[Path, tuple | None] = {}
        self._unstable = False
        self._context_signatures: dict[int, str] = {}
        self._graph_signatures: dict[int, str | None] = {}
        self._outputs = self._output_paths()
        self._planning = self._planning_paths()
        for path in self._outputs:
            self.read_bytes(path)
        self.log_text = self.read_text(self.story_dir / "runtime" / "story_log.md")
        self.log_entries = parse_log_entries(self.log_text)
        workflow_text = self.read_text(self.story_dir / "runtime" / "chapter_workflow.json")
        self.workflow = json.loads(workflow_text) if workflow_text else {"version": 1, "chapters": {}}
        if (not isinstance(self.workflow, dict) or self.workflow.get("version") != 1
                or not isinstance(self.workflow.get("chapters"), dict)):
            raise ValueError("Invalid workflow state")
        self.graph: dict = {}
        self.graph_error: str | None = None
        try:
            text = self.read_text(self.story_dir / "runtime" / "story_graph.json")
            self.graph = json.loads(text) if text else {}
            validate_flat_history(self.graph)
        except (ValueError, OSError, AttributeError, TypeError) as exc:
            self.graph_error = str(exc)
        # Preserve v1 normalized-text hashes while Jev observations keep raw-byte
        # manuscript hashes. No CRLF-only migration is required by this refactor.
        self._manuscript_hashes = {
            path.name: text_hash(self.read_text(path)) for path in self._outputs
        }

    def _output_paths(self) -> tuple[Path, ...]:
        return tuple(sorted(path for path in (self.story_dir / "outputs").glob("chapter_*.md")
                            if re.fullmatch(r"chapter_\d+\.md", path.name) and path.is_file()))

    def _planning_paths(self) -> tuple[Path, ...]:
        return tuple(sorted(path for path in (self.story_dir / "planning").glob("*")
                            if path.is_file() and path.suffix in {".md", ".yaml", ".yml", ".json"}))

    def read_bytes(self, path: Path) -> bytes:
        path = Path(path).absolute()
        if path not in self._bytes:
            before = _token(path)
            try:
                data = path.read_bytes()
            except FileNotFoundError:
                data = b""
            after = _token(path)
            self._unstable |= before != after
            self._tokens[path] = after
            self._bytes[path] = data
        return self._bytes[path]

    def read_text(self, path: Path) -> str:
        return self.read_bytes(path).decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")

    def is_current(self) -> bool:
        return (not self._unstable and self._outputs == self._output_paths()
                and self._planning == self._planning_paths()
                and all(_token(path) == token for path, token in self._tokens.items()))

    def log_entry(self, chapter: int) -> str | None:
        entries = self.log_entries.get(chapter, [])
        return entries[0] if len(entries) == 1 else None

    def chapter_path(self, chapter: int, entry: dict | None = None) -> Path:
        entry = entry if entry is not None else self.workflow["chapters"].get(str(chapter), {})
        path = (self.story_dir / entry.get("chapter_file", f"outputs/chapter_{chapter:03d}.md")).resolve()
        if path.parent != self.story_dir / "outputs":
            raise ValueError("Chapter must be in this story's outputs directory")
        return path

    def manuscript_bytes(self, chapter: int, entry: dict | None = None) -> bytes:
        return self.read_bytes(self.chapter_path(chapter, entry))

    def source_fingerprints(self, chapter: int, entry: dict | None = None) -> dict:
        text = self.read_text(self.chapter_path(chapter, entry))
        log_entry = self.log_entry(chapter)
        return {"chapter_sha256": text_hash(text) if text.strip() else None,
                "log_sha256": text_hash(log_entry) if has_summary(log_entry) else None}

    def context_signature(self, chapter: int) -> str:
        if self.graph_error:
            raise ValueError(self.graph_error)
        if chapter not in self._context_signatures:
            history = self.graph.get("_history")
            if history:
                baseline = history["baseline"]
                diffs = {key: diff for key, diff in history["diffs"].items() if int(key) < chapter}
            else:
                baseline, diffs = self.graph, {}
            baseline = {key: value for key, value in baseline.items() if value not in ({}, [], None)}
            logs = {str(ch): items[0] for ch, items in self.log_entries.items()
                    if 0 < ch < chapter and len(items) == 1}
            manuscripts = {name: digest for name, digest in self._manuscript_hashes.items()
                           if 0 < int(re.fullmatch(r"chapter_(\d+)\.md", name).group(1)) < chapter}
            self._context_signatures[chapter] = value_hash({
                "baseline": baseline, "diffs": diffs, "logs": logs, "manuscripts": manuscripts,
            })
        return self._context_signatures[chapter]

    def chapter_diff_signature(self, chapter: int) -> str | None:
        if self.graph_error:
            return None
        diff = self.graph.get("_history", {}).get("diffs", {}).get(str(chapter))
        return value_hash(diff) if diff is not None else None

    def graph_signature(self, chapter: int) -> str | None:
        if self.graph_error or self.chapter_diff_signature(chapter) is None:
            return None
        if chapter not in self._graph_signatures:
            history = self.graph["_history"]
            prefix = {key: diff for key, diff in history["diffs"].items() if int(key) <= chapter}
            self._graph_signatures[chapter] = value_hash({"baseline": history["baseline"], "diffs": prefix})
        return self._graph_signatures[chapter]
