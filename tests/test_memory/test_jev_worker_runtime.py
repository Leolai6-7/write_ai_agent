"""Warm-worker contracts using in-memory substitutes, never real services."""

from copy import deepcopy
import io
import json
from types import SimpleNamespace

import pytest

from scripts import jev_memory_worker as worker


def observation(chapter):
    return {"chapter": chapter, "observation_id": f"chapter-{chapter}",
            "source_path": f"outputs/chapter_{chapter:03d}.md",
            "source_hash": str(chapter) * 64, "text": f"Story chapter {chapter}", "entities": []}


def request(before=3, *, story="story-a", load_dir="generation-a"):
    return {"action": "query", "source": "/fake/upstream",
            "backend": {"source": "/fake/upstream", "source_hash": "source-v1", "mock": True,
                        "encoder_model": "local-encoder", "jev_model": "pinned-jev"},
            "load_dir": load_dir, "story_id": story, "before_chapter": before,
            "allowed": [observation(n) for n in range(1, before)], "query": "Find the story", "limit": 5}


@pytest.fixture
def upstream(monkeypatch):
    state = SimpleNamespace(loads=0, encoders=[], builders=[], clients=[], seen=[], saved=0,
                            generations={"generation-a": ("story-a", [1, 2, 3]),
                                         "generation-b": ("story-b", [1, 2, 3])},
                            fail_load=False, fail_query=False, fail_constructor=False,
                            http_status=200, http_error=None, http_calls=0, use_http=False)

    class Encoder:
        def __init__(self, **kwargs):
            self.dimension = 3
            state.encoders.append(self)

    class VectorDB:
        def __init__(self, dimension):
            self.dimension = dimension
            self.entries = {}

        def delete_vector(self, key):
            self.entries.pop(key, None)

    class Graph:
        def __init__(self):
            self.nodes, self.links = {}, []

        def delete_node(self, key):
            self.nodes.pop(key, None)
            self.links = [link for link in self.links if key not in link]

    class TRG:
        def __init__(self, encoder, vector_db, **kwargs):
            self.encoder, self.vector_db, self.graph_db = encoder, vector_db, Graph()

    class HTTP:
        def request(self, *args, **kwargs):
            state.http_calls += 1
            if state.http_error:
                raise state.http_error
            return SimpleNamespace(status_code=state.http_status)

    class Client:
        def __init__(self, config):
            self.closed = 0
            self.cache = {}
            self._sdk = None
            state.clients.append(self)

        def _get_sdk(self):
            if self._sdk is None:
                self._sdk = SimpleNamespace(_http_client=HTTP())
            return self._sdk

        def close(self):
            self.closed += 1

    class Builder:
        def __init__(self, path, *, trg_memory, jev_client, **kwargs):
            if state.fail_constructor:
                raise RuntimeError("PRIVATE_CONSTRUCTOR_DETAILS")
            self.trg, self.jev, self.node_index = trg_memory, jev_client, {}
            state.builders.append(self)

        def load(self, path):
            if state.fail_load:
                raise ValueError("PRIVATE_LOAD_DETAILS")
            story, chapters = state.generations[path]
            for chapter in chapters:
                record = observation(chapter)
                key = f"node-{chapter}"
                self.trg.graph_db.nodes[key] = SimpleNamespace(
                    node_id=key, node_type="event", content_narrative=record["text"],
                    attributes={**record, "story_id": story},
                )
                self.trg.vector_db.entries[key] = [1, 0, 0]
            self.trg.graph_db.links = [("node-1", f"node-{n}") for n in chapters[1:]]
            self.node_index = {"all": set(self.trg.graph_db.nodes)}

        def build(self, text, timestamp, metadata):
            node = SimpleNamespace(node_id=f"node-{metadata['chapter']}", attributes=metadata,
                                   content_narrative=text, node_type="event")
            self.trg.graph_db.nodes[node.node_id] = node
            return node

        def save(self):
            state.saved += 1

    class Engine:
        def __init__(self, trg, index, *, jev_client, **kwargs):
            self.trg, self.index, self.client = trg, index, jev_client

        def query(self, question, *, top_k):
            if state.fail_query:
                raise RuntimeError("PRIVATE_QUERY_DETAILS")
            assert self.client.cache == {}  # No answers leak across requests.
            self.client.cache[question] = "synthetic answer"
            state.seen.append({"chapters": sorted(n.attributes["chapter"] for n in self.trg.graph_db.nodes.values()),
                               "nodes": set(self.trg.graph_db.nodes), "index": deepcopy(self.index),
                               "links": deepcopy(self.trg.graph_db.links),
                               "vectors": set(self.trg.vector_db.entries)})
            calls = 0
            if state.use_http:
                # A second SDK lookup must not double-wrap the same HTTP call.
                sdk = self.client._get_sdk()
                assert self.client._get_sdk() is sdk
                sdk._http_client.request("POST", "PRIVATE_URL", headers={"Bearer": "PRIVATE_KEY"},
                                         content="PRIVATE_STATE")
                calls = 1
            return SimpleNamespace(anchor_nodes=list(self.trg.graph_db.nodes.values())[:top_k],
                                   metadata={"controller": "jev-mem", "llm_calls": 0,
                                             "jev_calls": calls, "latency_seconds": 0.0}), ""

    namespace = SimpleNamespace(NodeType=SimpleNamespace(EVENT="event"), JevClient=Client,
                                JevMemConfig=lambda **kw: SimpleNamespace(**kw),
                                MemoryBuilder=Builder, MockEncoder=Encoder, VectorEncoder=Encoder,
                                QueryEngine=Engine, TemporalResonanceGraphMemory=TRG,
                                NumpyVectorDB=VectorDB)

    def load(source):
        state.loads += 1
        return namespace

    monkeypatch.setattr(worker, "_load_upstream", load)
    return state


def test_warm_encoder_and_imports_only_fresh_graph_pruning_and_client(upstream):
    runtime = worker.WorkerRuntime(session=True)
    narrow = runtime.execute(request(2))
    wide = runtime.execute(request(4))
    narrow_again = runtime.execute(request(2))
    assert upstream.loads == 1 and len(upstream.encoders) == 1
    assert len(upstream.builders) == len(upstream.clients) == 3
    assert all(client.closed == 1 for client in upstream.clients)
    assert upstream.saved == 0
    assert [[hit["chapter"] for hit in r["evidence"]] for r in (narrow, wide, narrow_again)] == [[1], [1, 2, 3], [1]]
    assert [r["trace"]["timings"]["encoder_reused"] for r in (narrow, wide, narrow_again)] == [False, True, True]
    assert wide["trace"]["timings"]["encoder_seconds"] == 0.0
    for query in upstream.seen:
        assert query["nodes"] == query["vectors"] == query["index"]["all"]
        assert all(set(edge) <= query["nodes"] for edge in query["links"])
    assert len(upstream.builders[0].trg.graph_db.nodes) == 1
    assert len(upstream.builders[1].trg.graph_db.nodes) == 3


def test_fresh_generation_and_story_do_not_reuse_prior_memory(upstream):
    runtime = worker.WorkerRuntime(session=True)
    runtime.execute(request(4))
    second = runtime.execute(request(3, story="story-b", load_dir="generation-b"))
    assert [r["chapter"] for r in second["evidence"]] == [1, 2]
    assert all(node.attributes["story_id"] == "story-b"
               for node in upstream.builders[-1].trg.graph_db.nodes.values())
    # A mismatched story leaves no eligible evidence, not another story's nodes.
    mismatch = runtime.execute(request(3, story="story-b", load_dir="generation-a"))
    assert mismatch["evidence"] == []


@pytest.mark.parametrize("field,value", [("jev_model", "other"), ("encoder_model", "other"),
                                        ("source_hash", "changed"), ("mock", False)])
def test_backend_changes_rejected_before_new_client(upstream, field, value):
    runtime = worker.WorkerRuntime(session=True)
    runtime.execute(request())
    changed = request()
    changed["backend"][field] = value
    with pytest.raises(ValueError, match="cannot change"):
        runtime.execute(changed)
    assert len(upstream.clients) == 1


def test_source_change_and_session_build_rejected(upstream):
    runtime = worker.WorkerRuntime(session=True)
    runtime.execute(request())
    changed = request()
    changed["source"] = "/other/upstream"
    with pytest.raises(ValueError, match="cannot change"):
        runtime.execute(changed)
    with pytest.raises(ValueError, match="query requests"):
        runtime.execute({**request(), "action": "build"})
    assert len(upstream.clients) == 1


@pytest.mark.parametrize("failure", ["fail_constructor", "fail_load", "fail_query"])
def test_client_closed_on_failure(upstream, failure):
    setattr(upstream, failure, True)
    with pytest.raises((RuntimeError, ValueError)):
        worker.execute(request())
    assert upstream.clients[0].closed == 1


def test_http_timing_covers_actual_requests_without_sensitive_payload(upstream):
    upstream.use_http = True
    runtime = worker.WorkerRuntime(session=True)
    reports = [runtime.execute(request()), runtime.execute(request())]
    assert upstream.http_calls == 2
    for result in reports:
        trace = result["trace"]
        assert trace["api_timing_scope"] == "client_http_request_not_server_inference"
        assert len(trace["api_calls"]) == 1
        sample = trace["api_calls"][0]
        assert set(sample) == {"status", "status_code", "elapsed_seconds"}
        assert sample["status"] == "ok" and sample["status_code"] == 200
        assert sample["elapsed_seconds"] >= 0
        timings = trace["timings"]
        for phase in ("setup", "encoder", "load", "prune", "query", "build", "cleanup", "total"):
            assert timings[f"{phase}_seconds"] >= 0
        assert sum(timings[f"{phase}_seconds"] for phase in
                   ("setup", "encoder", "load", "prune", "query", "build", "cleanup")) <= timings["total_seconds"]
        assert "PRIVATE" not in json.dumps(trace)


def test_http_error_and_transport_exception_are_timed_without_messages(upstream):
    client = upstream.clients  # HTTP timing is independently testable without a builder.
    assert client == []
    http = SimpleNamespace(request=lambda *a, **kw: SimpleNamespace(status_code=429))
    sdk = SimpleNamespace(_http_client=http)
    fake = SimpleNamespace(_get_sdk=lambda: sdk)
    samples = []
    worker._time_http_requests(fake, samples)
    fake._get_sdk()._http_client.request("PRIVATE_STATE")
    assert samples[0]["status"] == "http_error" and samples[0]["status_code"] == 429

    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_KEY")
    fake = SimpleNamespace(_get_sdk=lambda: SimpleNamespace(_http_client=SimpleNamespace(request=fail)))
    samples = []
    worker._time_http_requests(fake, samples)
    with pytest.raises(RuntimeError):
        fake._get_sdk()._http_client.request("PRIVATE_STATE")
    assert samples[0]["status"] == "error" and samples[0]["elapsed_seconds"] >= 0
    assert "PRIVATE" not in json.dumps(samples)


def test_mock_calls_have_no_http_sample(upstream):
    result = worker.execute(request())
    assert result["trace"]["api_calls"] == []
    assert upstream.clients[0]._sdk is None


def test_oneshot_build_compatibility(upstream):
    payload = {**request(), "action": "build", "load_dir": None, "save_dir": "new-generation",
               "observations": [observation(1), observation(2)]}
    result = worker.execute(payload)
    assert result["admitted"] == 2 and result["status"] == "ok"
    assert result["trace"]["nodes"] == 2 and result["trace"]["timings"]["worker_mode"] == "oneshot"
    assert upstream.saved == 1
    assert upstream.clients[0].closed == 1


def test_runtime_request_count_is_bounded(upstream, monkeypatch):
    monkeypatch.setattr(worker, "MAX_SESSION_REQUESTS", 2)
    runtime = worker.WorkerRuntime(session=True)
    runtime.execute(request())
    runtime.execute(request())
    with pytest.raises(ValueError, match="at most"):
        runtime.execute(request())
    assert len(upstream.clients) == 2


def run_session(monkeypatch, requests):
    stdin, stdout = io.StringIO(requests), io.StringIO()
    monkeypatch.setattr(worker.sys, "stdin", stdin)
    monkeypatch.setattr(worker.sys, "stdout", stdout)
    code = worker.session_main()
    return code, [json.loads(line) for line in stdout.getvalue().splitlines()], stdin


def test_jsonl_session_echoes_ids_and_uses_one_encoder(upstream, monkeypatch):
    text = "\n".join(json.dumps({**request(n), "request_id": i}) for i, n in ((1, 2), (2, 4))) + "\n"
    code, results, _ = run_session(monkeypatch, text)
    assert code == 0 and [r["request_id"] for r in results] == [1, 2]
    assert [r["trace"]["timings"]["encoder_reused"] for r in results] == [False, True]
    assert len(upstream.encoders) == 1


@pytest.mark.parametrize("bad_line", ['{"request_id": 2, "PRIVATE_KEY":', '[]',
                                     '{"request_id":true}', '{"request_id":1}'])
def test_session_error_is_sanitized_and_stops_without_processing_next(upstream, monkeypatch, bad_line):
    good = json.dumps({**request(), "request_id": 1})
    later = json.dumps({**request(), "request_id": 3})
    code, results, remaining = run_session(monkeypatch, good + "\n" + bad_line + "\n" + later + "\n")
    assert code == 1 and len(results) == 2 and results[-1]["status"] == "error"
    assert "PRIVATE" not in json.dumps(results[-1])
    assert remaining.read() == later + "\n"
    assert len(upstream.clients) == 1


def test_session_exits_after_bounded_requests(upstream, monkeypatch):
    monkeypatch.setattr(worker, "MAX_SESSION_REQUESTS", 2)
    lines = [json.dumps({**request(), "request_id": n}) for n in range(1, 4)]
    code, results, remaining = run_session(monkeypatch, "\n".join(lines) + "\n")
    assert code == 0 and len(results) == 2
    assert remaining.read() == lines[2] + "\n"


def test_session_failure_closes_client_and_never_prints_upstream_error(upstream, monkeypatch):
    upstream.fail_query = True
    code, results, _ = run_session(monkeypatch, json.dumps({**request(), "request_id": 4}) + "\n")
    assert code == 1 and results == [{"status": "error", "error_type": "RuntimeError",
                                     "error": "Worker request failed", "request_id": 4}]
    assert upstream.clients[0].closed == 1
