"""Offline JSONL transport contracts; only a temporary stdlib worker is launched."""

from copy import deepcopy
import json
import sys
import time
from types import SimpleNamespace

import pytest

from memory import jev_bridge as bridge
from memory import jev_session as transport
from tests.test_memory.test_jev_bridge import add_chapter, make_story


FAKE_WORKER = r'''
import json
import os
from pathlib import Path
import sys
import time

assert sys.argv[1:] == ["--session"]
events = Path(__file__).with_name("requests.jsonl")
for line in sys.stdin:
    request = json.loads(line)
    with events.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"id": request["request_id"], "pid": os.getpid(),
                                 "query": request.get("query")}) + "\n")
    mode = request.get("test_mode", request.get("query", "ok"))
    if mode == "hang":
        time.sleep(60)
    if mode == "eof":
        break
    if mode == "invalid_json":
        print("not-json", flush=True)
        continue
    if mode == "no_newline":
        sys.stdout.write("{}")
        sys.stdout.flush()
        break
    if mode == "overlimit":
        sys.stdout.write("x" * (4 * 1024 * 1024 + 1) + "\n")
        sys.stdout.flush()
        continue
    evidence = [
        {"chapter": row["chapter"], "source_path": row["source_path"],
         "source_hash": row["source_hash"], "text": row["text"][:1400],
         "memory_id": "fake-memory-" + str(row["chapter"])}
        for row in request.get("allowed", [])[:request.get("limit", 1)]
    ]
    result = {"status": "ok", "request_id": request["request_id"],
              "pid": os.getpid(), "evidence": evidence,
              "trace": {"controller": "jev-mem", "llm_calls": 0}}
    if mode == "wrong_id":
        result["request_id"] += 1
    elif mode == "bool_id":
        result["request_id"] = True
    elif mode == "missing_id":
        del result["request_id"]
    elif mode == "missing_status":
        del result["status"]
    elif mode == "error":
        result.update(status="error", error="PRIVATE_PROVIDER_OUTPUT")
    elif mode == "list":
        result = []
    elif mode == "malicious_source_path":
        evidence[0]["source_path"] = "../../private.md"
    elif mode == "malicious_source_hash":
        evidence[0]["source_hash"] = "not-the-allowed-hash"
    elif mode == "malicious_text":
        evidence[0]["text"] = "Invented evidence."
    elif mode == "malicious_chapter":
        evidence[0]["chapter"] = 99
    elif mode == "too_many_evidence":
        evidence.append(dict(evidence[0]))
    elif mode == "bad_trace":
        result["trace"]["llm_calls"] = 1
    print(json.dumps(result), flush=True)
'''


@pytest.fixture
def fake_worker(tmp_path, monkeypatch):
    worker = tmp_path / "fake_session_worker.py"
    worker.write_text(FAKE_WORKER, encoding="utf-8")
    backend = {"python": sys.executable, "source": str(tmp_path), "mock": True,
               "source_hash": "offline-source", "encoder_model": "offline-only"}
    processes = []
    popen = transport.subprocess.Popen

    def checked_popen(args, **kwargs):
        assert args == [sys.executable, "-I", "-u", str(worker), "--session"]
        assert kwargs["cwd"] == str(tmp_path)
        process = popen(args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(transport.subprocess, "Popen", checked_popen)
    monkeypatch.setattr(bridge, "WORKER", worker)
    harness = SimpleNamespace(worker=worker, backend=backend, processes=processes,
                              config={"timeout_seconds": 2},
                              events_path=tmp_path / "requests.jsonl")
    yield harness
    # A failed assertion must not leave even the synthetic subprocess running.
    for process in processes:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        for stream in (process.stdin, process.stdout):
            if stream is not None and not stream.closed:
                stream.close()


def request(session, fake, mode="ok", **extra):
    return session.request(fake.config, fake.backend,
                           {"action": "query", "query": mode, **extra}, fake.worker)


def events(fake):
    return [json.loads(line) for line in fake.events_path.read_text().splitlines()]


def assert_stopped(fake):
    assert fake.processes
    assert all(process.poll() is not None for process in fake.processes)
    assert all(process.stdin.closed and process.stdout.closed for process in fake.processes)


def test_context_is_lazy_and_closed_context_cannot_restart(fake_worker):
    with transport.JevWorkerSession() as session:
        assert not fake_worker.processes
    assert not fake_worker.processes
    with pytest.raises(transport.WorkerSessionError, match="open context"):
        request(session, fake_worker)
    with pytest.raises(transport.WorkerSessionError, match="new worker session"):
        session.__enter__()
    assert not fake_worker.processes


def test_request_requires_context(fake_worker):
    with pytest.raises(transport.WorkerSessionError, match="open context"):
        request(transport.JevWorkerSession(), fake_worker)
    assert not fake_worker.processes


def test_same_pid_is_reused_with_increasing_client_owned_ids(fake_worker):
    with transport.JevWorkerSession() as session:
        first = request(session, fake_worker, "first", request_id=999)
        second = request(session, fake_worker, "second", request_id=999)
        assert [first["request_id"], second["request_id"]] == [1, 2]
        assert first["pid"] == second["pid"] == fake_worker.processes[0].pid
        assert len(fake_worker.processes) == 1
        assert fake_worker.processes[0].poll() is None
    assert [row["id"] for row in events(fake_worker)] == [1, 2]
    assert [row["query"] for row in events(fake_worker)] == ["first", "second"]
    assert_stopped(fake_worker)
    session.close()  # Cleanup is idempotent.


def test_context_exception_also_reaps_worker(fake_worker):
    with pytest.raises(RuntimeError, match="caller failed"):
        with transport.JevWorkerSession() as session:
            request(session, fake_worker)
            raise RuntimeError("caller failed")
    assert_stopped(fake_worker)


def test_timeout_stops_worker_without_retry(fake_worker):
    with transport.JevWorkerSession() as session:
        request(session, fake_worker)
        fake_worker.config["timeout_seconds"] = 0.3
        started = time.monotonic()
        with pytest.raises(transport.WorkerSessionError, match="timeout_seconds"):
            request(session, fake_worker, "hang")
        assert_stopped(fake_worker)
        with pytest.raises(transport.WorkerSessionError, match="open context"):
            request(session, fake_worker)
    assert time.monotonic() - started < 4
    assert len(fake_worker.processes) == 1
    assert len(events(fake_worker)) == 2


@pytest.mark.parametrize("mode", [
    "invalid_json", "wrong_id", "bool_id", "missing_id", "missing_status",
    "eof", "no_newline", "overlimit", "error", "list",
])
def test_protocol_failure_closes_session_and_cannot_retry(fake_worker, mode):
    with transport.JevWorkerSession() as session:
        with pytest.raises(transport.WorkerSessionError, match="invalid response") as exc:
            request(session, fake_worker, mode)
        assert "PRIVATE_PROVIDER_OUTPUT" not in str(exc.value)
        assert_stopped(fake_worker)
        with pytest.raises(transport.WorkerSessionError, match="open context"):
            request(session, fake_worker)
    assert len(fake_worker.processes) == 1
    assert len(events(fake_worker)) == 1


@pytest.mark.parametrize("change", ["encoder", "source", "worker"])
def test_backend_or_worker_mutation_is_refused(fake_worker, change):
    with transport.JevWorkerSession() as session:
        request(session, fake_worker)
        worker = fake_worker.worker
        if change == "encoder":
            # Mutate the same dictionary: the session must own a detached copy.
            fake_worker.backend["encoder_model"] = "changed-encoder"
        elif change == "source":
            fake_worker.backend["source"] = str(fake_worker.worker.parent / "other")
        else:
            worker = fake_worker.worker.with_name("other_worker.py")
        with pytest.raises(transport.WorkerSessionError, match="backend changed"):
            session.request(fake_worker.config, fake_worker.backend,
                            {"action": "query"}, worker)
        assert_stopped(fake_worker)
    assert len(fake_worker.processes) == 1
    assert len(events(fake_worker)) == 1


@pytest.mark.parametrize("value", [0, -1, 129, True, "2", 1.5])
def test_invalid_request_budgets_are_rejected(value):
    with pytest.raises(ValueError, match="max_requests"):
        transport.JevWorkerSession(max_requests=value)


def test_request_budget_stops_instead_of_restarting(fake_worker):
    with transport.JevWorkerSession(max_requests=2) as session:
        request(session, fake_worker)
        request(session, fake_worker)
        with pytest.raises(transport.WorkerSessionError, match="budget exhausted"):
            request(session, fake_worker)
        assert_stopped(fake_worker)
    assert len(fake_worker.processes) == 1
    assert [row["id"] for row in events(fake_worker)] == [1, 2]


def test_build_is_refused_without_starting_worker(fake_worker):
    with transport.JevWorkerSession() as session:
        with pytest.raises(transport.WorkerSessionError, match="queries only"):
            session.request(fake_worker.config, fake_worker.backend,
                            {"action": "build", "observations": []}, fake_worker.worker)
        with pytest.raises(transport.WorkerSessionError, match="open context"):
            request(session, fake_worker)
    assert not fake_worker.processes


def test_oversized_request_is_refused_before_launch(fake_worker):
    with transport.JevWorkerSession() as session:
        with pytest.raises(transport.WorkerSessionError, match="8 MiB"):
            request(session, fake_worker, "x" * (8 * 1024 * 1024))
    assert not fake_worker.processes


@pytest.mark.parametrize("mode", [
    "malicious_source_path", "malicious_source_hash", "malicious_text",
    "malicious_chapter", "too_many_evidence", "bad_trace",
])
def test_bridge_validates_session_evidence_and_closes_bad_worker(fake_worker, mode):
    allowed = {"chapter": 1, "source_path": "outputs/chapter_001.md",
               "source_hash": "trusted-hash", "text": "Synthetic source evidence."}
    payload = {"action": "query", "query": mode, "limit": 1, "allowed": [allowed]}
    with transport.JevWorkerSession() as session:
        with pytest.raises(bridge.MemoryBridgeError, match="invalid|allowed sources"):
            bridge._run_worker(fake_worker.config, fake_worker.backend, payload, session=session)
        assert_stopped(fake_worker)
        with pytest.raises(transport.WorkerSessionError, match="open context"):
            request(session, fake_worker)
    assert len(fake_worker.processes) == 1


def prepare_story(tmp_path, monkeypatch, fake):
    story = make_story(tmp_path, name="session-synthetic", mode="active")
    add_chapter(story, 1, "Mina leaves a blue cup beside the lamp.")
    monkeypatch.setattr(bridge, "_backend", lambda config: deepcopy(fake.backend))

    def offline_build(config, backend, payload):
        assert payload["action"] == "build"
        return {"status": "ok", "admitted": len(payload["observations"]),
                "trace": {"controller": "jev-mem", "llm_calls": 0}}

    with monkeypatch.context() as patch:
        patch.setattr(bridge, "_run_worker", offline_build)
        assert bridge.sync_chapter(story, 1)["stored"]
    return story


def test_query_memory_reuses_explicit_session(tmp_path, monkeypatch, fake_worker):
    story = prepare_story(tmp_path, monkeypatch, fake_worker)
    with transport.JevWorkerSession() as session:
        first = bridge.query_memory(story, 2, "ok", limit=1, worker_session=session)
        second = bridge.query_memory(story, 2, "ok", limit=1, worker_session=session)
        assert first["status"] == second["status"] == "ok"
        assert first["pid"] == second["pid"]
        assert first["evidence"] == second["evidence"]
        assert first["evidence"][0]["chapter"] == 1
    assert len(fake_worker.processes) == 1
    assert_stopped(fake_worker)


def test_query_memory_withholds_malicious_session_evidence(tmp_path, monkeypatch, fake_worker):
    story = prepare_story(tmp_path, monkeypatch, fake_worker)
    with transport.JevWorkerSession() as session:
        result = bridge.query_memory(story, 2, "malicious_source_path", limit=1,
                                     worker_session=session)
        assert result["status"] == "error"
        assert result["evidence"] == []
        assert_stopped(fake_worker)


def test_off_does_not_invoke_or_start_session(tmp_path, monkeypatch, fake_worker):
    story = tmp_path / "never-created"
    with transport.JevWorkerSession() as session:
        monkeypatch.setattr(session, "request", lambda *a, **kw: pytest.fail("off invoked session"))
        result = bridge.query_memory(story, 2, "synthetic", worker_session=session)
        assert result["status"] == "disabled" and result["evidence"] == []
    assert not fake_worker.processes
    assert not story.exists()
