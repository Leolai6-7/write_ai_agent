"""Offline contract tests: these never invoke a model or external service."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import memory_eval_backends as live


@pytest.fixture
def corpus():
    # Keep non-sorted order: adapters must not silently choose different orders.
    return [{"chapter": n, "text": f"第 {n} 章：共同文本\n  保留空白。\n",
             "source_path": f"never-open-this/chapter-{n}.md",
             "source_sha256": hashlib.sha256(f"body-{n}".encode()).hexdigest()}
            for n in (2, 1, 3)]


@pytest.fixture
def cases():
    return [{"id": "first", "question": "共同 問題？", "before_chapter": 3, "limit": 2,
             "gold": "NEVER_SEND_GOLD"},
            {"id": "earlier", "question": "第一章？", "before_chapter": 2, "limit": 1,
             "requirements": [{"private": "NEVER_SEND_REQUIREMENTS"}]}]


@pytest.fixture
def fakes(monkeypatch, tmp_path):
    state = SimpleNamespace(events=[], paths=[], added=[], queries=[], requests=[],
                            query_errors={}, worker_errors={}, malformed={}, build_error=None)
    monkeypatch.setenv("JEV_MEM_PYTHON", str(tmp_path / "python"))
    monkeypatch.setenv("JEV_MEM_SOURCE", str(tmp_path / "upstream"))
    monkeypatch.setenv("TYPESAFE_API_KEY", "NEVER_PRINT_API_KEY")

    def backend(config):
        state.config = deepcopy(config)
        return {**config, "source_hash": "fake", "schema": 1}

    monkeypatch.setattr(live.jev_bridge, "_backend", backend)

    class FakeRetriever:
        def __init__(self, path, **kwargs):
            state.events.append("chroma-init")
            state.paths.append(Path(path))
            Path(path).mkdir()
            state.constructor = kwargs
            assert os.environ["HF_HUB_OFFLINE"] == "1"
            assert os.environ["TRANSFORMERS_OFFLINE"] == "1"

        def add_chapter(self, **kwargs):
            state.events.append("chroma-add")
            state.added.append(kwargs)
            if state.build_error:
                raise state.build_error

        def get_count(self):
            return len(state.added)

        def query(self, question, **kwargs):
            state.events.append("chroma-query")
            state.queries.append({"question": question, **kwargs})
            if question in state.query_errors:
                raise state.query_errors[question]
            if "chroma" in state.malformed:
                return state.malformed["chroma"]
            return [{"chapter_id": r["chapter_id"]} for r in state.added
                    if r["chapter_id"] < kwargs["before_chapter"]][:kwargs["n_results"]]

    monkeypatch.setattr(live, "SemanticRetriever", FakeRetriever)

    def preflight(backend, scratch):
        state.events.append("jev-preflight")
        state.preflight_path = scratch
        assert state.added
        assert scratch.is_dir()

    monkeypatch.setattr(live, "_preflight_jev", preflight)

    def worker(config, backend, request):
        state.events.append("jev-" + request["action"])
        state.requests.append(deepcopy(request))
        state.backend = deepcopy(backend)
        assert os.environ["HF_HUB_OFFLINE"] == "1"
        assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
        assert "TYPESAFE_API_KEY" not in config
        if request["action"] in state.worker_errors:
            raise state.worker_errors[request["action"]]
        if request["action"] == "build":
            state.paths.append(Path(request["save_dir"]))
            assert Path(request["save_dir"]).is_dir()
            assert request["load_dir"] is None
            return {"status": "ok", "admitted": len(request["observations"]),
                    "trace": {"controller": "jev-mem", "llm_calls": 0}}
        if "jev" in state.malformed:
            return state.malformed["jev"]
        return {"status": "ok", "evidence": [{"chapter": r["chapter"]} for r in
                                                request["allowed"][:request["limit"]]],
                "trace": {"controller": "jev-mem", "llm_calls": 0}}

    monkeypatch.setattr(live.jev_bridge, "_run_worker", worker)
    return state


def run(corpus, cases):
    return live.run_live(corpus, cases, encoder_model="explicit-encoder", jev_model="explicit-jev")


def test_session_only_reuses_queries_and_closes_before_store_cleanup(corpus, cases, fakes, monkeypatch):
    calls = []

    class Session:
        def __enter__(self):
            calls.append("enter")
            return self

        def __exit__(self, *args):
            assert all(path.exists() for path in fakes.paths)
            calls.append("exit")

    monkeypatch.setattr(live.jev_bridge, "JevWorkerSession", Session)
    original = live.jev_bridge._run_worker

    def worker(config, backend, request, *, session=None):
        if request["action"] == "build":
            assert session is None
            assert not calls
        else:
            assert isinstance(session, Session)
            assert calls == ["enter"]
        return original(config, backend, request)

    monkeypatch.setattr(live.jev_bridge, "_run_worker", worker)
    result = live.run_live(corpus, cases, encoder_model="explicit-encoder",
                           jev_model="explicit-jev", jev_worker="session")
    assert calls == ["enter", "exit"]
    assert result["backends"]["jev"]["status"] == "ok"
    assert result["metadata"]["jev_worker"] == "session"
    assert result["metadata"]["jev_session_first_query_includes_startup"] is True
    assert all(not path.exists() for path in fakes.paths)


@pytest.mark.parametrize("mode,count", [("invalid", 1), ("session", 129)])
def test_invalid_worker_session_preflight_is_before_any_work(corpus, cases, fakes, mode, count):
    queries = [{**cases[0], "id": str(n)} for n in range(count)]
    with pytest.raises(live.LivePreflightError):
        live.run_live(corpus, queries, encoder_model="explicit-encoder",
                      jev_model="explicit-jev", jev_worker=mode)
    assert not fakes.events


def test_same_exact_corpus_order_models_and_questions(corpus, cases, fakes):
    before = deepcopy((corpus, cases))
    report = run(corpus, cases)
    assert (corpus, cases) == before
    assert fakes.added == [{"chapter_id": r["chapter"], "summary": r["text"]} for r in corpus]
    observations = fakes.requests[0]["observations"]
    assert [(r["chapter"], r["text"]) for r in observations] == [
        (r["chapter"], r["text"]) for r in corpus]
    assert all(r["entities"] == [] and r["observation_id"].startswith("eval:")
               for r in observations)
    assert fakes.constructor == {"embedding_model": "explicit-encoder", "allow_model_download": False}
    assert fakes.backend["encoder_model"] == "explicit-encoder"
    assert fakes.backend["jev_model"] == "explicit-jev"
    assert fakes.backend["mock"] is False
    assert fakes.events.index("jev-preflight") < fakes.events.index("jev-build")
    assert fakes.events[:4] == ["chroma-init", "chroma-add", "chroma-add", "chroma-add"]
    worker_queries = fakes.requests[1:]
    for case, chroma, jev in zip(cases, fakes.queries, worker_queries):
        assert chroma["question"] == jev["query"] == case["question"]
        assert chroma["before_chapter"] == jev["before_chapter"] == case["before_chapter"]
        assert chroma["n_results"] == jev["limit"] == case["limit"]
        assert chroma["max_distance"] == 1.0
        assert all(r["chapter"] < case["before_chapter"] for r in jev["allowed"])
    digest = hashlib.sha256(json.dumps(
        [{"chapter": r["chapter"], "text": r["text"]} for r in corpus], ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    for backend in report["backends"].values():
        assert backend["status"] == "ok"
        assert backend["corpus_sha256"] == digest
        assert backend["encoder_model"] == "explicit-encoder"
        assert backend["build_seconds"] >= 0
        assert backend["results"]["first"]["hits"] == [2, 1]
        assert backend["results"]["earlier"]["hits"] == [1]
    assert report["metadata"]["comparison_kind"] == "same_corpus_recall"
    assert report["metadata"]["production_workflow_benchmark"] is False
    assert report["metadata"]["chroma_max_distance"] == 1.0
    assert report["metadata"]["jev_model"] == "explicit-jev"
    assert report["metadata"]["encoder_model"] == "explicit-encoder"


def test_gold_fields_are_never_read_or_forwarded(corpus, cases, fakes):
    class GuardedCase(dict):
        def get(self, key, default=None):
            assert key in {"id", "question", "before_chapter", "limit"}
            return super().get(key, default)

        def __iter__(self):
            pytest.fail("The whole case must not be copied or iterated")

        def keys(self):
            pytest.fail("The whole case must not be copied")

    report = run(corpus, [GuardedCase(case) for case in cases])
    sent = json.dumps([fakes.config, fakes.added, fakes.queries, fakes.requests, report])
    for secret in ("NEVER_SEND_GOLD", "NEVER_SEND_REQUIREMENTS", "NEVER_PRINT_API_KEY"):
        assert secret not in sent
    assert all(set(request) == {"action", "story_id", "load_dir", "allowed", "query",
                                "before_chapter", "limit"} for request in fakes.requests[1:])


def test_only_temporary_stores_no_source_reads_and_settings_restored(corpus, cases, fakes,
                                                                    monkeypatch, tmp_path):
    sentinel = tmp_path / "existing-story-data"
    sentinel.write_text("must survive", encoding="utf-8")
    corpus[0]["source_path"] = str(sentinel)
    monkeypatch.setattr(Path, "read_bytes", lambda *a: pytest.fail("source bytes opened"))
    monkeypatch.setattr(Path, "read_text", lambda *a, **kw: pytest.fail("source text opened"))
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    report = run(corpus, cases)
    assert len(fakes.paths) == 2
    assert fakes.paths[0].parent == fakes.paths[1].parent
    assert fakes.paths[0].parent.name.startswith("novel-memory-eval-")
    assert not fakes.paths[0].parent.exists()
    assert sentinel.exists()
    with sentinel.open(encoding="utf-8") as stream:
        assert stream.read() == "must survive"
    assert os.environ["HF_HUB_OFFLINE"] == "0"
    assert "TRANSFORMERS_OFFLINE" not in os.environ
    assert report["metadata"]["temporary_stores"] is True


@pytest.mark.parametrize("name", ["JEV_MEM_PYTHON", "JEV_MEM_SOURCE", "TYPESAFE_API_KEY"])
def test_missing_prerequisite_fails_before_any_backend(corpus, cases, fakes, monkeypatch, name):
    monkeypatch.delenv(name)
    with pytest.raises(live.LivePreflightError, match=name):
        run(corpus, cases)
    assert not fakes.events
    assert not fakes.requests


@pytest.mark.parametrize("name,value", [("encoder_model", ""), ("encoder_model", "  "),
                                        ("jev_model", None), ("jev_model", "")])
def test_explicit_model_names_required(corpus, cases, fakes, name, value):
    arguments = {"encoder_model": "encoder", "jev_model": "jev", name: value}
    with pytest.raises(live.LivePreflightError, match=name):
        live.run_live(corpus, cases, **arguments)
    assert not fakes.events


def test_chroma_build_failure_precedes_any_jev_call_and_cleans(corpus, cases, fakes):
    fakes.build_error = RuntimeError("NEVER_PRINT_API_KEY")
    with pytest.raises(live.LivePreflightError, match="Chroma local build") as error:
        run(corpus, cases)
    assert "NEVER_PRINT_API_KEY" not in str(error.value)
    assert not fakes.requests
    assert "jev-preflight" not in fakes.events
    assert not fakes.paths[0].parent.exists()


def test_jev_preflight_failure_never_builds_or_queries(corpus, cases, fakes, monkeypatch):
    def fail(*args):
        raise live.LivePreflightError("local encoder absent")
    monkeypatch.setattr(live, "_preflight_jev", fail)
    with pytest.raises(live.LivePreflightError, match="local encoder"):
        run(corpus, cases)
    assert not fakes.requests
    assert not fakes.paths[0].parent.exists()


def test_invalid_upstream_config_fails_before_backend_initialization(corpus, cases, fakes, monkeypatch):
    def fail(*args):
        raise ValueError("NEVER_PRINT_API_KEY")
    monkeypatch.setattr(live.jev_bridge, "_backend", fail)
    with pytest.raises(live.LivePreflightError, match="upstream checkout") as error:
        run(corpus, cases)
    assert "NEVER_PRINT_API_KEY" not in str(error.value)
    assert not fakes.events


@pytest.mark.parametrize("name", ["chroma", "jev"])
def test_query_errors_are_not_successful_empty_hits(corpus, cases, fakes, name):
    if name == "chroma":
        fakes.query_errors[cases[0]["question"]] = RuntimeError("NEVER_PRINT_API_KEY")
    else:
        fakes.worker_errors["query"] = RuntimeError("NEVER_PRINT_API_KEY")
    result = run(corpus, cases)
    backend = result["backends"][name]
    assert backend["status"] == "error"
    assert backend["results"]["first"]["status"] == "error"
    assert backend["results"]["first"]["hits"] == []
    assert "NEVER_PRINT_API_KEY" not in json.dumps(result)


def test_jev_build_error_has_explicit_case_errors(corpus, cases, fakes):
    fakes.worker_errors["build"] = RuntimeError("NEVER_PRINT_API_KEY")
    result = run(corpus, cases)
    assert result["backends"]["chroma"]["status"] == "ok"
    assert result["backends"]["jev"]["status"] == "error"
    assert all(case["status"] == "error" for case in result["backends"]["jev"]["results"].values())
    assert len(fakes.requests) == 1
    assert "NEVER_PRINT_API_KEY" not in json.dumps(result)
    assert not fakes.paths[0].parent.exists()


def test_explicit_worker_error_response_is_not_a_miss(corpus, cases, fakes):
    fakes.malformed["jev"] = {"status": "error", "evidence": [], "error": "NEVER_PRINT_API_KEY"}
    result = run(corpus, cases)
    assert result["backends"]["jev"]["results"]["first"]["status"] == "error"
    assert "NEVER_PRINT_API_KEY" not in json.dumps(result)


@pytest.mark.parametrize("hits", [[3], [99], [True], [1, 1], [1, 2, 1]])
@pytest.mark.parametrize("backend,field", [("chroma", "chapter_id"), ("jev", "chapter")])
def test_malformed_future_unknown_duplicate_hits_fail_closed(corpus, cases, fakes,
                                                           hits, backend, field):
    rows = [{field: chapter} for chapter in hits]
    fakes.malformed[backend] = rows if backend == "chroma" else {
        "status": "ok", "evidence": rows, "trace": {}}
    result = run(corpus, cases)["backends"][backend]["results"]["first"]
    assert result["status"] == "error" and result["hits"] == []


def test_empty_eligible_corpus_is_success_not_backend_error(corpus, fakes):
    cases = [{"id": "before-start", "question": "query", "before_chapter": 1, "limit": 1}]
    report = run(corpus, cases)
    assert not fakes.queries
    assert len(fakes.requests) == 1  # Build only, no query API.
    for backend in report["backends"].values():
        result = backend["results"]["before-start"]
        assert result["status"] == "ok" and result["hits"] == []
        assert result["trace"]["eligible_chapters"] == []


def test_preflight_is_isolated_offline_and_discards_provider_output(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    def process(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=1, stdout="NEVER_PRINT_API_KEY", stderr="secret")
    monkeypatch.setattr(live.subprocess, "run", process)
    with pytest.raises(live.LivePreflightError) as error:
        live._preflight_jev({"python": "/fake/python", "source": "/fake/upstream",
                            "encoder_model": "explicit-encoder"}, tmp_path)
    assert "NEVER_PRINT_API_KEY" not in str(error.value)
    command, kwargs = calls[0]
    assert command[:4] == ["/fake/python", "-I", "-B", "-c"]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
    assert kwargs["env"]["TRANSFORMERS_OFFLINE"] == "1"
    assert "socket.socket.connect = no_network" in command[4]
    assert json.loads(kwargs["input"]) == {"source": "/fake/upstream",
                                           "encoder_model": "explicit-encoder"}


@pytest.mark.parametrize("field,value", [("chapter", True), ("chapter", 0),
                                         ("text", ""), ("text", "x" * 4001),
                                         ("source_path", ""), ("source_sha256", "bad")])
def test_invalid_corpus_rejected_before_backend_calls(corpus, cases, fakes, field, value):
    corpus[0][field] = value
    with pytest.raises(live.LivePreflightError):
        run(corpus, cases)
    assert not fakes.events


@pytest.mark.parametrize("field,value", [("id", ""), ("question", ""), ("before_chapter", True),
                                         ("before_chapter", 0), ("limit", 0), ("limit", 6)])
def test_invalid_case_rejected_before_backend_calls(corpus, cases, fakes, field, value):
    cases[0][field] = value
    with pytest.raises(live.LivePreflightError):
        run(corpus, cases)
    assert not fakes.events


def test_duplicate_chapters_or_cases_rejected(corpus, cases, fakes):
    with pytest.raises(live.LivePreflightError, match="unique positive"):
        run(corpus + [corpus[0]], cases)
    with pytest.raises(live.LivePreflightError, match="unique non-empty"):
        run(corpus, cases + [cases[0]])
    assert not fakes.events
