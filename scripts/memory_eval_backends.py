"""Opt-in, same-corpus live recall adapters, not a production workflow benchmark.

Only caller-supplied text is indexed. No story directory, workflow receipt, or
existing memory is read. All stores live in a disposable TemporaryDirectory.
Gold labels are deliberately excluded by projecting a fixed query field set.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from memory import jev_bridge
from memory.retrieval import SemanticRetriever


class LivePreflightError(ValueError):
    """Invalid inputs or unavailable local prerequisites; no live calls started."""


def corpus_sha256(corpus: list[dict]) -> str:
    """Fingerprint exact text and order, excluding provenance and gold labels."""
    values = [{"chapter": item["chapter"], "text": item["text"]} for item in corpus]
    encoded = json.dumps(values, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _inputs(corpus: list[dict], cases: list[dict]) -> tuple[list[dict], list[dict]]:
    if not isinstance(corpus, list) or not corpus:
        raise LivePreflightError("corpus must be a non-empty list")
    records, chapters = [], set()
    for item in corpus:
        if not isinstance(item, dict):
            raise LivePreflightError("corpus records must be objects")
        chapter, text = item.get("chapter"), item.get("text")
        if type(chapter) is not int or chapter < 1 or chapter in chapters:
            raise LivePreflightError("corpus chapters must be unique positive integers")
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise LivePreflightError("corpus text must contain 1–4000 characters")
        source_path, source_sha = item.get("source_path"), item.get("source_sha256")
        if not isinstance(source_path, str) or not source_path.strip():
            raise LivePreflightError("corpus records require source_path text")
        if not isinstance(source_sha, str) or not re.fullmatch(r"[a-f0-9]{64}", source_sha):
            raise LivePreflightError("corpus records require a SHA-256 source fingerprint")
        # Provenance is carried, never opened as a filesystem path.
        records.append({"chapter": chapter, "text": text, "source_path": source_path,
                        "source_sha256": source_sha})
        chapters.add(chapter)
    if not isinstance(cases, list) or not cases:
        raise LivePreflightError("cases must be a non-empty list")
    queries, identifiers = [], set()
    for item in cases:
        if not isinstance(item, dict):
            raise LivePreflightError("cases must be objects")
        # Do not iterate item, copy item, or access any gold/scoring fields.
        query = {field: item.get(field) for field in
                 ("id", "question", "before_chapter", "limit")}
        case_id = query["id"]
        if not isinstance(case_id, str) or not case_id.strip() or case_id in identifiers:
            raise LivePreflightError("case ids must be unique non-empty strings")
        if (not isinstance(query["question"], str) or not query["question"].strip()
                or len(query["question"]) > 4000):
            raise LivePreflightError("questions must contain 1–4000 characters")
        if type(query["before_chapter"]) is not int or query["before_chapter"] < 1:
            raise LivePreflightError("before_chapter must be a positive integer")
        if type(query["limit"]) is not int or not 1 <= query["limit"] <= 5:
            raise LivePreflightError("limit must be between 1 and 5")
        queries.append(query)
        identifiers.add(case_id)
    return records, queries


@contextmanager
def _offline_models():
    # The production worker uses setdefault; force offline even when the caller
    # previously enabled downloads. Restore every setting after the run.
    settings = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "ANONYMIZED_TELEMETRY": "False"}
    previous = {key: os.environ.get(key) for key in settings}
    try:
        os.environ.update(settings)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


_JEV_PREFLIGHT = r'''
import json, socket, sys
def no_network(*args, **kwargs):
    raise RuntimeError("Network disabled during live-evaluation preflight")
socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network
socket.getaddrinfo = no_network
spec = json.load(sys.stdin)
sys.path.insert(0, spec["source"])
from memory.graph_db import NodeType
from memory.jev_mem_config import JevMemConfig
from memory.memory_builder import MemoryBuilder
from memory.mock_encoder import MockEncoder
from memory.query_engine import QueryEngine
from memory.trg_memory import TemporalResonanceGraphMemory
from memory.vector_db import NumpyVectorDB, VectorEncoder
# Load the encoder in the worker's interpreter, not just the novel interpreter.
# Never create a builder or Jev client in this prerequisite probe.
encoder = VectorEncoder(model_name=spec["encoder_model"], use_openai=False)
assert encoder.dimension > 0
'''


def _preflight_jev(backend: dict, scratch: Path) -> None:
    """Check worker imports and local encoder with network physically blocked."""
    environment = dict(os.environ)
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                       PYTHONDONTWRITEBYTECODE="1")
    # Neither output nor errors from optional third-party code may expose keys.
    try:
        process = subprocess.run(
            [backend["python"], "-I", "-B", "-c", _JEV_PREFLIGHT],
            input=json.dumps({"source": backend["source"],
                              "encoder_model": backend["encoder_model"]}),
            text=True, capture_output=True, cwd=scratch, env=environment,
            timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise LivePreflightError("Jev local preflight could not complete; no live calls started") from None
    if process.returncode:
        raise LivePreflightError(
            "Jev local imports/encoder unavailable; prepare dependencies and cached model separately"
        )


def _configuration(encoder_model: str, jev_model: str) -> tuple[dict, dict]:
    for name, value in (("encoder_model", encoder_model), ("jev_model", jev_model)):
        if not isinstance(value, str) or not value.strip():
            raise LivePreflightError(f"{name} must be explicitly supplied and non-empty")
    for name in ("JEV_MEM_PYTHON", "JEV_MEM_SOURCE", "TYPESAFE_API_KEY"):
        if not os.environ.get(name, "").strip():
            raise LivePreflightError(f"Set {name} before requesting live evaluation")
    config = {"mock": False, "python": os.environ["JEV_MEM_PYTHON"],
              "source": os.environ["JEV_MEM_SOURCE"], "encoder_model": encoder_model,
              "jev_model": jev_model, "timeout_seconds": 60}
    try:
        backend = jev_bridge._backend(config)
    except (OSError, ValueError, TypeError):
        raise LivePreflightError("Jev interpreter or separate upstream checkout is unavailable") from None
    if Path(backend["source"]).resolve() == Path(__file__).resolve().parents[1]:
        raise LivePreflightError("Jev requires a separate upstream checkout")
    return config, backend


def _observations(records: list[dict]) -> list[dict]:
    # Evaluation identities are intentionally not production chapter receipts.
    return [{"chapter": item["chapter"], "text": item["text"], "entities": [],
             "observation_id": f"eval:{item['chapter']}:{item['source_sha256']}",
             "source_hash": item["source_sha256"], "source_path": item["source_path"]}
            for item in records]


def _validated_hits(rows: list[dict], field: str, allowed: set[int], limit: int) -> list[int]:
    if not isinstance(rows, list) or len(rows) > limit:
        raise ValueError("backend returned malformed or over-limit hits")
    hits = []
    for row in rows:
        chapter = row.get(field) if isinstance(row, dict) else None
        if type(chapter) is not int or chapter not in allowed or chapter in hits:
            raise ValueError("backend returned a duplicate or ineligible chapter")
        hits.append(chapter)
    return hits


def _error_result(error: Exception, elapsed: float) -> dict:
    # Exception messages can contain headers or private provider response data.
    return {"status": "error", "hits": [], "elapsed_seconds": elapsed,
            "error_type": type(error).__name__, "error": "Backend operation failed",
            "trace": {}}


def run_live(corpus: list[dict], cases: list[dict], *, encoder_model: str,
             jev_model: str, jev_worker: str = "oneshot") -> dict:
    """Compare exact input text using local Chroma and opt-in live Jev-Mem.

    Prerequisite failures raise LivePreflightError before any Jev build/query.
    Runtime failures remain explicit error results, never successful zero hits.
    This deliberately bypasses production synchronization/receipt workflows.
    """
    if jev_worker not in ("oneshot", "session"):
        raise LivePreflightError("jev_worker must be oneshot or session")
    records, queries = _inputs(corpus, cases)
    if jev_worker == "session" and len(queries) > 128:
        raise LivePreflightError("A worker session supports at most 128 queries")
    config, backend = _configuration(encoder_model, jev_model)
    fingerprint = corpus_sha256(records)
    backends = {name: {"status": "ok", "corpus_sha256": fingerprint,
                       "encoder_model": encoder_model, "build_seconds": 0.0,
                       "results": {}} for name in ("chroma", "jev")}
    backends["jev"]["jev_model"] = jev_model
    metadata = {"comparison_kind": "same_corpus_recall", "production_workflow_benchmark": False,
                "corpus_sha256": fingerprint, "corpus_chapters": [r["chapter"] for r in records],
                "encoder_model": encoder_model, "jev_model": jev_model,
                "jev_worker": jev_worker,
                "jev_session_first_query_includes_startup": jev_worker == "session",
                "jev_source_sha256": backend.get("source_hash"),
                "case_count": len(queries), "temporary_stores": True,
                "model_downloads_allowed": False, "chroma_max_distance": 1.0,
                "jev_entities": "empty_for_all_records", "gold_sent_to_backends": False,
                "limitations": ["No production completion receipts or freshness checks",
                                "Equal text/model names do not guarantee identical embedding preprocessing",
                                "Equal-input recall comparison, not isolated algorithm benchmarking",
                                "Jev builds once on the whole corpus; queries prune future nodes",
                                "Backend build and query latency are measured separately"]}
    with TemporaryDirectory(prefix="novel-memory-eval-") as directory, _offline_models(), ExitStack() as stack:
        scratch = Path(directory)
        chroma_path, jev_path = scratch / "chroma", scratch / "jev"
        jev_path.mkdir()
        started = perf_counter()
        try:
            retriever = SemanticRetriever(chroma_path, embedding_model=encoder_model,
                                          allow_model_download=False)
            for record in records:
                retriever.add_chapter(chapter_id=record["chapter"], summary=record["text"])
            if retriever.get_count() != len(records):
                raise ValueError("Chroma did not capture the entire corpus")
        except Exception:
            raise LivePreflightError(
                "Chroma local build unavailable; prepare dependencies and cached model separately"
            ) from None
        backends["chroma"]["build_seconds"] = perf_counter() - started
        _preflight_jev(backend, scratch)
        observations = _observations(records)
        story_id = f"memory-eval:{fingerprint}"
        jev_built = False
        started = perf_counter()
        try:
            build = jev_bridge._run_worker(config, backend, {
                "action": "build", "story_id": story_id, "load_dir": None,
                "save_dir": str(jev_path), "observations": observations,
            })
            if build.get("status") != "ok" or build.get("admitted") != len(observations):
                raise ValueError("Jev build did not succeed")
            jev_built = True
            backends["jev"]["build_trace"] = build.get("trace", {})
        except Exception as error:
            backends["jev"].update(status="error", error_type=type(error).__name__,
                                   error="Backend build failed")
        backends["jev"]["build_seconds"] = perf_counter() - started
        session = (stack.enter_context(jev_bridge.JevWorkerSession())
                   if jev_worker == "session" else None)
        for case in queries:
            allowed = [r for r in observations if r["chapter"] < case["before_chapter"]]
            eligible = {r["chapter"] for r in allowed}
            for name in ("chroma", "jev"):
                started = perf_counter()
                try:
                    if name == "jev" and not jev_built:
                        raise RuntimeError("Backend build failed")
                    if not allowed:
                        hits, trace = [], {"eligible_chapters": [], "query_skipped": "empty_corpus"}
                    elif name == "chroma":
                        rows = retriever.query(case["question"], n_results=case["limit"],
                                               before_chapter=case["before_chapter"],
                                               max_distance=1.0)
                        hits = _validated_hits(rows, "chapter_id", eligible, case["limit"])
                        trace = {"eligible_chapters": sorted(eligible), "max_distance": 1.0}
                    else:
                        request = {
                            "action": "query", "story_id": story_id, "load_dir": str(jev_path),
                            "allowed": allowed, "query": case["question"],
                            "before_chapter": case["before_chapter"], "limit": case["limit"],
                        }
                        response = (jev_bridge._run_worker(config, backend, request)
                                    if session is None else
                                    jev_bridge._run_worker(config, backend, request, session=session))
                        if response.get("status") != "ok":
                            raise ValueError("Jev query did not succeed")
                        hits = _validated_hits(response["evidence"], "chapter", eligible, case["limit"])
                        trace = response.get("trace", {})
                    result = {"status": "ok", "hits": hits,
                              "elapsed_seconds": perf_counter() - started, "trace": trace}
                except Exception as error:
                    result = _error_result(error, perf_counter() - started)
                    backends[name]["status"] = "error"
                backends[name]["results"][case["id"]] = result
    return {"backends": backends, "metadata": metadata}
