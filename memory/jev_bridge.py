"""Optional per-story Jev-Mem bridge; upstream runs in its own Python process.

Only ``sync_chapter`` captures an explicitly selected, completed chapter. Queries
never import upstream's conflicting ``memory`` package into the novel process.
"""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

from scripts.story_snapshot import StorySnapshot, has_summary
from memory.jev_session import JevWorkerSession, WorkerSessionError


SCHEMA = 1
DEFAULT_ENCODER = "BAAI/bge-small-zh-v1.5"
WORKER = Path(__file__).resolve().parents[1] / "scripts" / "jev_memory_worker.py"


class MemoryBridgeError(ValueError):
    """Configuration, source validation, or isolated worker failed."""


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _config(story_dir: Path) -> dict:
    path = story_dir / "planning" / "memory_config.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(config, dict):
        raise MemoryBridgeError("memory_config.json must contain an object")
    result = {"mode": "off", "mock": False, "encoder_model": DEFAULT_ENCODER,
              "jev_model": "jev-latest", "timeout_seconds": 60, **config}
    if result["mode"] not in ("off", "shadow", "active"):
        raise MemoryBridgeError("mode must be off, shadow, or active")
    if type(result["mock"]) is not bool:
        raise MemoryBridgeError("mock must be a boolean")
    timeout = result["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 5 <= timeout <= 600:
        raise MemoryBridgeError("timeout_seconds must be between 5 and 600")
    for key in ("encoder_model", "jev_model"):
        if not isinstance(result[key], str) or not result[key].strip():
            raise MemoryBridgeError(f"{key} must be non-empty text")
    result["python"] = os.environ.get("JEV_MEM_PYTHON") or result.get("python")
    result["source"] = os.environ.get("JEV_MEM_SOURCE") or result.get("source")
    return result


def memory_mode(story_dir: Path) -> str:
    """Read validated routing mode without starting a worker or touching a store."""
    return _config(Path(story_dir))["mode"]


def _backend(config: dict) -> dict:
    for key in ("python", "source"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise MemoryBridgeError(f"Set JEV_MEM_{key.upper()} or memory_config.json {key}")
    # Keep a venv's executable symlink: resolving it would bypass the venv.
    interpreter = Path(config["python"]).expanduser().absolute()
    source = Path(config["source"]).expanduser().resolve()
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise MemoryBridgeError("Jev-Mem Python interpreter is not executable")
    if not (source / "jev_mem" / "system.py").is_file():
        raise MemoryBridgeError("Jev-Mem source must be an upstream checkout")
    files = sorted([*(source / "memory").glob("*.py"), *(source / "utils").glob("*.py")])
    if not (source / "memory" / "memory_builder.py").is_file():
        raise MemoryBridgeError("Jev-Mem source is missing MemoryBuilder")
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(source)).encode())
        digest.update(path.read_bytes())
    return {"schema": SCHEMA, "python": str(interpreter), "source": str(source),
            "source_hash": digest.hexdigest(), "mock": config["mock"],
            "encoder_model": "mock-128" if config["mock"] else config["encoder_model"],
            "jev_model": config["jev_model"]}


def _story_id(story_dir: Path) -> str:
    return _hash(str(story_dir.resolve()).encode())[:24]


def _store(story_dir: Path) -> Path:
    return story_dir / "runtime" / "jev_memory"


def _atomic_json(path: Path, value: dict) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


@contextmanager
def _lock(store: Path, exclusive: bool, *, blocking: bool = True):
    store.mkdir(parents=True, exist_ok=True)
    with (store / ".lock").open("a+") as lock:
        flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(lock, flags if blocking else flags | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise MemoryBridgeError("Memory update is in progress; retry recall after sync") from error
        yield


def _current(store: Path, story_id: str) -> tuple[Path | None, dict | None]:
    pointer = store / "current.json"
    if not pointer.exists():
        return None, None
    data = json.loads(pointer.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise MemoryBridgeError("Invalid Jev-Mem generation pointer")
    generation = data.get("generation", "")
    if not isinstance(generation, str) or not re.fullmatch(r"gen-[a-f0-9]{32}", generation):
        raise MemoryBridgeError("Invalid Jev-Mem generation pointer")
    directory = store / generation
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA
            or manifest.get("story_id") != story_id):
        raise MemoryBridgeError("Memory belongs to another story or schema")
    if not isinstance(manifest.get("observations"), list) or not isinstance(manifest.get("backend"), dict):
        raise MemoryBridgeError("Memory manifest has no observations")
    chapters = set()
    for record in manifest["observations"]:
        if not isinstance(record, dict) or type(record.get("chapter")) is not int or record["chapter"] < 1:
            raise MemoryBridgeError("Memory manifest has an invalid chapter observation")
        if record["chapter"] in chapters:
            raise MemoryBridgeError("Memory manifest has duplicate chapter observations")
        chapters.add(record["chapter"])
        if (not isinstance(record.get("text"), str) or not 1 <= len(record["text"]) <= 4000
                or not isinstance(record.get("entities"), list)
                or any(not isinstance(name, str) for name in record["entities"])):
            raise MemoryBridgeError("Memory manifest observation is malformed")
        for field in ("chapter_hash", "log_hash", "source_hash"):
            if not isinstance(record.get(field), str) or not re.fullmatch(r"[a-f0-9]{64}", record[field]):
                raise MemoryBridgeError("Memory manifest has invalid source fingerprints")
        expected_id = f"chapter:{record['chapter']}:{record['source_hash']}"
        if (record.get("observation_id") != expected_id
                or record.get("source_path") != f"outputs/chapter_{record['chapter']:03d}.md"
                or _hash(record["text"].encode()) != record["log_hash"]
                or _hash(f"{record['chapter_hash']}:{record['log_hash']}".encode()) != record["source_hash"]):
            raise MemoryBridgeError("Memory manifest observation does not match its sources")
    return directory, manifest


def _log_entry(snapshot: StorySnapshot, chapter: int) -> str:
    entry = snapshot.log_entry(chapter)
    if entry is None:
        raise MemoryBridgeError(f"Chapter {chapter} needs exactly one story_log entry")
    if not has_summary(entry):
        raise MemoryBridgeError(f"Chapter {chapter} story_log has no summary")
    if len(entry) > 4000:
        raise MemoryBridgeError("Chapter observation exceeds 4000 characters; shorten its story_log entry")
    return entry


def _chapter_complete(snapshot: StorySnapshot, chapter: int) -> bool:
    from scripts.chapter_workflow import chapter_status
    status = chapter_status(snapshot.story_dir, chapter, snapshot=snapshot)
    return status.get("complete") is True


def _observation(snapshot: StorySnapshot, chapter: int) -> dict:
    if type(chapter) is not int or chapter < 1:
        raise MemoryBridgeError("chapter must be a positive integer")
    if not _chapter_complete(snapshot, chapter):
        raise MemoryBridgeError(f"Chapter {chapter} has no current complete workflow receipt")
    relative = f"outputs/chapter_{chapter:03d}.md"
    manuscript = snapshot.read_bytes(snapshot.story_dir / relative)
    if not manuscript.strip():
        raise MemoryBridgeError(f"Chapter {chapter} manuscript is empty")
    entry = _log_entry(snapshot, chapter)
    graph = snapshot.graph
    entities = sorted(name for name, item in graph.get("characters", {}).items()
                      if chapter in item.get("chapters", []))
    chapter_hash, log_hash = _hash(manuscript), _hash(entry.encode())
    source_hash = _hash(f"{chapter_hash}:{log_hash}".encode())
    return {"chapter": chapter, "observation_id": f"chapter:{chapter}:{source_hash}",
            "source_path": relative, "source_hash": source_hash,
            "chapter_hash": chapter_hash, "log_hash": log_hash,
            "text": entry, "entities": entities}


def _fresh(snapshot: StorySnapshot, record: dict) -> bool:
    try:
        chapter = record["chapter"]
        # Reconstruct the expected path, never trust a persisted arbitrary path.
        path = snapshot.story_dir / "outputs" / f"chapter_{chapter:03d}.md"
        return (_chapter_complete(snapshot, chapter)
                and _hash(snapshot.read_bytes(path)) == record["chapter_hash"]
                and _hash(_log_entry(snapshot, chapter).encode()) == record["log_hash"])
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _run_worker(config: dict, backend: dict, request: dict,
                *, session: JevWorkerSession | None = None) -> dict:
    payload = {**request, "source": backend["source"], "backend": backend}
    if session is not None:
        try:
            result = session.request(config, backend, payload, WORKER)
            return _validate_worker_result(result, request)
        except (WorkerSessionError, MemoryBridgeError):
            session.close()
            raise
    try:
        process = subprocess.run([backend["python"], "-I", str(WORKER)],
                                 input=json.dumps(payload, ensure_ascii=False), text=True,
                                 capture_output=True, timeout=config["timeout_seconds"],
                                 cwd=backend["source"], check=False)
    except subprocess.TimeoutExpired as error:
        raise MemoryBridgeError("Jev-Mem worker exceeded timeout_seconds") from error
    try:
        result = json.loads(process.stdout)
    except (ValueError, TypeError) as error:
        raise MemoryBridgeError("Jev-Mem worker did not return valid JSON") from error
    if not isinstance(result, dict):
        raise MemoryBridgeError("Jev-Mem worker returned an invalid response")
    if process.returncode or result.get("status") == "error":
        raise MemoryBridgeError(str(result.get("error", "Jev-Mem worker failed")))
    return _validate_worker_result(result, request)


def _validate_worker_result(result: dict, request: dict) -> dict:
    trace = result.get("trace")
    if (result.get("status") != "ok" or not isinstance(trace, dict)
            or trace.get("controller") != "jev-mem" or trace.get("llm_calls") != 0):
        raise MemoryBridgeError("Jev-Mem worker returned an invalid trace")
    if request["action"] == "build":
        if result.get("admitted") != len(request["observations"]):
            raise MemoryBridgeError("Jev-Mem worker did not capture all observations")
    else:
        hits = result.get("evidence")
        if not isinstance(hits, list) or len(hits) > request["limit"]:
            raise MemoryBridgeError("Jev-Mem worker returned invalid evidence")
        allowed = {r["chapter"]: r for r in request["allowed"]}
        seen = set()
        for hit in hits:
            record = allowed.get(hit.get("chapter")) if isinstance(hit, dict) else None
            if (record is None or type(hit.get("chapter")) is not int or hit["chapter"] in seen
                    or hit.get("source_hash") != record["source_hash"]
                    or hit.get("source_path") != record["source_path"]
                    or hit.get("text") != record["text"][:1400]
                    or not isinstance(hit.get("memory_id"), str) or not hit["memory_id"]):
                raise MemoryBridgeError("Jev-Mem worker evidence does not match allowed sources")
            seen.add(hit["chapter"])
    return result


def sync_chapter(story_dir: Path, chapter: int, *, mock: bool | None = None,
                 rebuild: bool = False) -> dict:
    """Explicitly capture one completed chapter; retain prior generations on revision."""
    story_dir = Path(story_dir).resolve()
    config = _config(story_dir)
    if config["mode"] == "off":
        return {"mode": "off", "status": "disabled", "stored": False}
    if mock is not None and mock != config["mock"]:
        raise MemoryBridgeError("mock must match this story's memory_config.json")
    backend = _backend(config)
    store, story_id = _store(story_dir), _story_id(story_dir)
    with _lock(store, exclusive=True):
        snapshot = StorySnapshot(story_dir)
        record = _observation(snapshot, chapter)
        if not snapshot.is_current():
            raise MemoryBridgeError("Chapter sources changed while loading; retry sync")
        current, previous = _current(store, story_id)
        if previous and previous["backend"]["mock"] != backend["mock"]:
            raise MemoryBridgeError("Mock and live memories require separate story fixtures")
        records = {r["chapter"]: r for r in previous["observations"]} if previous else {}
        stale = [n for n, item in records.items() if not _fresh(snapshot, item)]
        same_backend = previous is not None and previous["backend"] == backend
        if records.get(chapter) == record and same_backend and not stale and not rebuild:
            return {"mode": config["mode"], "status": "unchanged", "stored": False,
                    "chapter": chapter, "observations": len(records)}
        previous_max = max(records, default=0)
        old_record = records.get(chapter)
        for n in stale:
            records.pop(n)
        records[chapter] = record
        ordered = [records[n] for n in sorted(records)]
        # Revisions, out-of-order inserts and backend changes rebuild the derived
        # graph so relationships cannot refer to stale chapter observations.
        incremental = (same_backend and not stale and old_record is None
                       and chapter > previous_max and not rebuild)
        generation = store / f"gen-{uuid.uuid4().hex}"
        generation.mkdir()
        result = _run_worker(config, backend, {"action": "build", "story_id": story_id,
                             "load_dir": str(current) if incremental else None,
                             "save_dir": str(generation),
                             "observations": [record] if incremental else ordered})
        after = StorySnapshot(story_dir)
        if any(not _fresh(after, item) for item in ordered) or not after.is_current():
            raise MemoryBridgeError("Chapter sources changed during sync; previous generation retained")
        manifest = {"schema": SCHEMA, "story_id": story_id, "backend": backend,
                    "observations": ordered, "worker": result}
        _atomic_json(generation / "manifest.json", manifest)
        _atomic_json(store / "current.json", {"generation": generation.name})
        return {"mode": config["mode"], "status": "stored", "stored": True,
                "chapter": chapter, "observations": len(ordered),
                "rebuilt": not incremental, "stale_chapters_excluded": [n for n in stale if n != chapter],
                "generation": generation.name, "trace": result.get("trace", {})}


def query_memory(story_dir: Path, before_chapter: int, query: str, limit: int = 3,
                 *, snapshot: StorySnapshot | None = None,
                 worker_session: JevWorkerSession | None = None) -> dict:
    """Recall eligible observations; caller inserts evidence only in active mode."""
    mode = "off"
    try:
        story_dir = Path(story_dir).resolve()
        config = _config(story_dir)
        mode = config["mode"]
        if mode == "off":
            return {"mode": mode, "status": "disabled", "evidence": [], "trace": {}}
        if type(before_chapter) is not int or before_chapter < 1:
            raise MemoryBridgeError("before_chapter must be a positive integer")
        if not isinstance(query, str) or not query.strip() or len(query) > 4000:
            raise MemoryBridgeError("query must contain 1–4000 characters")
        if type(limit) is not int or not 1 <= limit <= 5:
            raise MemoryBridgeError("limit must be between 1 and 5")
        store, story_id = _store(story_dir), _story_id(story_dir)
        if not (store / "current.json").exists():
            return {"mode": mode, "status": "empty", "evidence": [], "trace": {}}
        with _lock(store, exclusive=False, blocking=False):
            snapshot = snapshot or StorySnapshot(story_dir)
            if snapshot.story_dir != story_dir or not snapshot.is_current():
                raise MemoryBridgeError("Story snapshot changed; retry recall")
            current, manifest = _current(store, story_id)
            backend = _backend(config)
            if manifest["backend"] != backend:
                raise MemoryBridgeError("Memory backend changed; explicitly sync a completed chapter")
            eligible = [r for r in manifest["observations"] if r["chapter"] < before_chapter]
            allowed = [r for r in eligible if _fresh(snapshot, r)]
            stale = [r["chapter"] for r in eligible if r not in allowed]
            if not allowed:
                return {"mode": mode, "status": "empty", "evidence": [],
                        "trace": {"stale_chapters_excluded": stale}}
            request = {"action": "query", "story_id": story_id,
                                 "load_dir": str(current), "before_chapter": before_chapter,
                                 "allowed": allowed, "query": query, "limit": limit}
            result = (_run_worker(config, backend, request) if worker_session is None else
                      _run_worker(config, backend, request, session=worker_session))
            after = StorySnapshot(story_dir)
            changed = [r["chapter"] for r in allowed if not _fresh(after, r)]
            if changed or not after.is_current():
                return {"mode": mode, "status": "stale", "evidence": [],
                        "trace": {**result.get("trace", {}), "sources_changed_during_query": changed}}
            result.update(mode=mode)
            result.setdefault("trace", {})["stale_chapters_excluded"] = stale
            return result
    except (MemoryBridgeError, OSError, ValueError, KeyError, TypeError) as error:
        return {"mode": mode, "status": "error", "error": str(error),
                "evidence": [], "trace": {}}


def memory_status(story_dir: Path) -> dict:
    story_dir = Path(story_dir).resolve()
    config = _config(story_dir)
    store = _store(story_dir)
    if not (store / "current.json").exists():
        return {"mode": config["mode"], "status": "empty", "observations": 0}
    with _lock(store, exclusive=False):
        current, manifest = _current(store, _story_id(story_dir))
        snapshot = StorySnapshot(story_dir)
        stale = [r["chapter"] for r in manifest["observations"] if not _fresh(snapshot, r)]
        return {"mode": config["mode"], "status": "ready", "generation": current.name,
                "observations": len(manifest["observations"]),
                "chapters": [r["chapter"] for r in manifest["observations"]],
                "mock": manifest["backend"]["mock"], "stale_chapters": stale}
