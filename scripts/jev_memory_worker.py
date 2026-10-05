"""Isolated JSON worker for the upstream Jev-Mem checkout.

Run using its dedicated interpreter with ``-I``. The default accepts one JSON
request; ``--session`` accepts at most 128 query-only JSONL requests. A session
reuses imports and its encoder, never mutable memory, clients, or answer caches.
No credential files are loaded. This file deliberately has no novel-side imports.
"""

from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from types import SimpleNamespace


MAX_SESSION_REQUESTS = 128
MAX_REQUEST_CHARS = 4 * 1024 * 1024


def _load_upstream(source: Path) -> SimpleNamespace:
    """Import upstream exactly once inside a dedicated, novel-free process."""
    novel = Path(__file__).resolve().parents[1]
    if source == novel or not (source / "jev_mem" / "system.py").is_file():
        raise ValueError("Expected a separate upstream Jev-Mem checkout")
    if "memory" in sys.modules:
        raise RuntimeError("Jev worker must start in an isolated interpreter")
    sys.path[:] = [p for p in sys.path if p and Path(p).resolve() not in (novel, novel / "scripts")]
    sys.path.insert(0, str(source))
    from memory.graph_db import NodeType
    from memory.jev_client import JevClient
    from memory.jev_mem_config import JevMemConfig
    from memory.memory_builder import MemoryBuilder
    from memory.mock_encoder import MockEncoder
    from memory.query_engine import QueryEngine
    from memory.trg_memory import TemporalResonanceGraphMemory
    from memory.vector_db import NumpyVectorDB, VectorEncoder
    return SimpleNamespace(NodeType=NodeType, JevClient=JevClient, JevMemConfig=JevMemConfig,
                           MemoryBuilder=MemoryBuilder, MockEncoder=MockEncoder,
                           QueryEngine=QueryEngine, TemporalResonanceGraphMemory=TemporalResonanceGraphMemory,
                           NumpyVectorDB=NumpyVectorDB, VectorEncoder=VectorEncoder)


def _time_http_requests(client, records: list[dict]) -> None:
    """Measure actual HTTP sends, excluding local cache hits and mock decisions.

    Upstream currently exposes its SDK lazily through _get_sdk. Instrument only
    that request's HTTP-client instance. Never retain arguments, headers, bodies,
    response contents, URLs, exception text, or authentication values.
    """
    get_sdk = client._get_sdk
    wrapped = set()

    def get_timed_sdk():
        sdk = get_sdk()
        http = sdk._http_client
        if id(http) not in wrapped:
            original = http.request

            def request(*args, **kwargs):
                started = perf_counter()
                sample = {"status": "error"}
                try:
                    response = original(*args, **kwargs)
                    status = response.status_code
                    if type(status) is int:
                        sample["status_code"] = status
                        sample["status"] = "ok" if 200 <= status < 400 else "http_error"
                    return response
                finally:
                    sample["elapsed_seconds"] = perf_counter() - started
                    records.append(sample)

            http.request = request
            wrapped.add(id(http))
        return sdk

    client._get_sdk = get_timed_sdk


class WorkerRuntime:
    """Process-local immutable backend plus encoder; all query state is fresh."""

    def __init__(self, *, session: bool = False):
        self.session = session
        self._identity = None
        self._upstream = None
        self._encoder = None
        self._requests = 0

    def execute(self, request: dict) -> dict:
        started = perf_counter()
        timings = {f"{phase}_seconds": 0.0 for phase in
                   ("setup", "encoder", "load", "prune", "query", "build", "cleanup")}
        timings.update(encoder_reused=self._encoder is not None,
                       worker_mode="session" if self.session else "oneshot")
        setup = perf_counter()
        if not isinstance(request, dict) or request.get("action") not in ("query", "build"):
            raise ValueError("Unknown worker action")
        if self.session and (request["action"] != "query" or self._requests >= MAX_SESSION_REQUESTS):
            raise ValueError("Session accepts at most 128 query requests")
        source = Path(request["source"]).resolve()
        spec = request["backend"]
        if not isinstance(spec, dict):
            raise ValueError("Invalid backend")
        identity = json.dumps({"source": str(source), "backend": spec}, sort_keys=True,
                              ensure_ascii=False, allow_nan=False)
        if self._identity is not None and identity != self._identity:
            raise ValueError("A worker session cannot change its source or backend")
        # Every session request forces offline encoder use. Keep the original
        # single-request compatibility with explicitly prepared environments.
        for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
            if self.session:
                os.environ[name] = "1"
            else:
                os.environ.setdefault(name, "1")
        if self._upstream is None:
            self._upstream = _load_upstream(source)
            self._identity = identity
        upstream = self._upstream
        config = upstream.JevMemConfig(
            write_enabled=True, read_enabled=True, jev_mock=spec["mock"],
            jev_model=spec["jev_model"], fallback_to_magma=False,
            consolidation_interval=0, candidate_top_k=5, anchor_count=3,
            maximum_nodes=12, maximum_edges=30, maximum_depth=2,
            maximum_jev_calls=4, max_latency_seconds=10.0, max_retries=0,
        )
        timings["setup_seconds"] = perf_counter() - setup
        if self._encoder is None:
            encoder_started = perf_counter()
            self._encoder = (upstream.MockEncoder() if spec["mock"] else
                             upstream.VectorEncoder(model_name=spec["encoder_model"], use_openai=False))
            timings["encoder_seconds"] = perf_counter() - encoder_started
        encoder = self._encoder
        setup = perf_counter()
        client = upstream.JevClient(config)
        api_calls = []
        self._requests += 1
        try:
            _time_http_requests(client, api_calls)
            trg = upstream.TemporalResonanceGraphMemory(
                encoder=encoder, vector_db=upstream.NumpyVectorDB(encoder.dimension),
                llm_backend=None, enable_async=False,
            )
            cache_dir = request.get("save_dir") or request["load_dir"]
            builder = upstream.MemoryBuilder(cache_dir, trg_memory=trg, llm_enabled=False,
                                             jev_config=config, jev_client=client)
            timings["setup_seconds"] += perf_counter() - setup
            phase = perf_counter()
            if request.get("load_dir"):
                builder.load(request["load_dir"])
                if builder.trg.vector_db.dimension != encoder.dimension:
                    raise ValueError("Persisted embedding dimension does not match encoder")
                if set(builder.trg.vector_db.entries) != set(builder.trg.graph_db.nodes):
                    raise ValueError("Persisted graph and vectors are inconsistent; explicitly sync to rebuild")
            timings["load_seconds"] = perf_counter() - phase
            if request["action"] == "build":
                phase = perf_counter()
                admitted = 0
                for record in request["observations"]:
                    metadata = {**{key: record[key] for key in
                                    ("chapter", "observation_id", "source_path", "source_hash", "entities")},
                                "story_id": request["story_id"], "source": "novel_chapter_log"}
                    node = builder.build(record["text"], timestamp=None, metadata=metadata)
                    if node is None:
                        raise RuntimeError("Jev-Mem rejected a chapter observation")
                    admitted += 1
                builder.save()
                timings["build_seconds"] = perf_counter() - phase
                result = {"status": "ok", "admitted": admitted,
                          "trace": {"controller": "jev-mem", "mock": spec["mock"],
                                    "llm_calls": 0, "nodes": len(builder.trg.graph_db.nodes)}}
            else:
                result = self._query(request, builder, config, timings)
        finally:
            cleanup = perf_counter()
            client.close()
            timings["cleanup_seconds"] = perf_counter() - cleanup
        timings["total_seconds"] = perf_counter() - started
        result["trace"].update(timings=timings, api_calls=api_calls,
                               api_timing_scope="client_http_request_not_server_inference")
        return result

    def _query(self, request: dict, builder, config, timings: dict) -> dict:
        phase = perf_counter()
        allowed = {r["observation_id"]: r for r in request["allowed"]}
        removed = 0
        for node_id, node in list(builder.trg.graph_db.nodes.items()):
            attrs = node.attributes
            record = allowed.get(attrs.get("observation_id"))
            valid = (node.node_type == self._upstream.NodeType.EVENT and record is not None
                     and attrs.get("story_id") == request["story_id"]
                     and attrs.get("source_hash") == record["source_hash"]
                     and attrs.get("chapter") == record["chapter"]
                     and node.content_narrative == record["text"]
                     and record["chapter"] < request["before_chapter"])
            if not valid:
                builder.trg.graph_db.delete_node(node_id)
                builder.trg.vector_db.delete_vector(node_id)
                removed += 1
        retained = set(builder.trg.graph_db.nodes)
        builder.node_index = {term: set(ids) & retained for term, ids in builder.node_index.items()
                              if set(ids) & retained}
        timings["prune_seconds"] = perf_counter() - phase
        # A fresh builder and engine for every request prevent narrowing one
        # query from permanently removing nodes needed by a later query.
        phase = perf_counter()
        engine = self._upstream.QueryEngine(builder.trg, builder.node_index,
                                            jev_config=config, jev_client=builder.jev)
        context, _ = engine.query(request["query"], top_k=request["limit"])
        timings["query_seconds"] = perf_counter() - phase
        evidence = [{"chapter": node.attributes["chapter"],
                     "text": node.content_narrative[:1400], "memory_id": node.node_id,
                     "source_path": node.attributes["source_path"],
                     "source_hash": node.attributes["source_hash"]}
                    for node in context.anchor_nodes]
        trace = {key: context.metadata.get(key) for key in
                 ("controller", "stopping_decision", "jev_calls", "llm_calls", "fallback_events",
                  "nodes_visited", "edges_examined", "latency_seconds")}
        trace.update(mock=request["backend"]["mock"], excluded_nodes=removed,
                     eligible_chapters=sorted({r["chapter"] for r in allowed.values()}))
        return {"status": "ok", "evidence": evidence, "trace": trace}


def execute(request: dict) -> dict:
    """Backwards-compatible one-shot API."""
    return WorkerRuntime().execute(request)


def _error(error: Exception) -> dict:
    return {"status": "error", "error_type": type(error).__name__, "error": "Worker request failed"}


def session_main() -> int:
    runtime = WorkerRuntime(session=True)
    previous_id = -1
    for _ in range(MAX_SESSION_REQUESTS):
        request_id = None
        try:
            line = sys.stdin.readline(MAX_REQUEST_CHARS + 1)
            if not line:
                return 0
            if len(line) > MAX_REQUEST_CHARS:
                raise ValueError("Request exceeds the session input limit")
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Session requests must be objects")
            candidate = request.get("request_id")
            if type(candidate) is int:
                request_id = candidate
            if request_id is None or request_id <= previous_id:
                raise ValueError("Session request_id must increase monotonically")
            previous_id = request_id
            with redirect_stdout(sys.stderr):
                result = runtime.execute(request)
            result["request_id"] = request_id
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as error:
            print(json.dumps({**_error(error), "request_id": request_id}, ensure_ascii=False), flush=True)
            return 1  # Fail closed; never retry an uncertain paid request.
    return 0


def main() -> int:
    if sys.argv[1:] == ["--session"]:
        return session_main()
    try:
        request = json.load(sys.stdin)
        with redirect_stdout(sys.stderr):
            result = execute(request)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps(_error(error), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
