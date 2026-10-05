"""Offline checks of evaluation logic, not measurements of retrieval quality."""

from copy import deepcopy
import json

import pytest

from scripts import benchmark_memory as benchmark


def small_fixture():
    return {
        "schema": 1,
        "chapters": [
            {"chapter": 1, "title": "交接", "body": "阿晴收到藍杯。她答應週二歸還。",
             "summary": "阿晴收到藍杯。", "record": "阿晴收到藍杯。她答應週二歸還。"},
            {"chapter": 2, "title": "暗記", "body": "阿晴記下紅門暗記。杯底刻著三角。",
             "summary": "阿晴記下暗記。", "record": "阿晴記下暗記。暗記在紅門。"},
            {"chapter": 3, "title": "改約", "body": "她改約週四歸還。",
             "summary": "她改約週四歸還。", "record": "她改約週四歸還。"},
        ],
        "cases": [
            {"id": "promise", "question": "原本答應何時還杯？", "before_chapter": 3, "limit": 1,
             "requirements": [{"id": "promise_time", "chapter": 1,
                               "quote": "她答應週二歸還。", "probes": ["週二歸還"]}]},
            {"id": "clue", "question": "杯底刻了什麼？", "before_chapter": 3, "limit": 1,
             "requirements": [{"id": "bottom_mark", "chapter": 2,
                               "quote": "杯底刻著三角。", "probes": ["杯底", "三角"]}]},
        ],
    }


def backend_result(data, *, view="record", hits=None):
    corpus = benchmark.build_corpus(data, view)
    run = {
        "status": "ok", "corpus_sha256": benchmark.corpus_fingerprint(corpus),
        "encoder_model": "cached-test-model", "build_seconds": 0.1,
        "results": {case["id"]: {"status": "ok", "hits": (hits or {}).get(case["id"], [1]),
                                  "elapsed_seconds": 0.2}
                    for case in data["cases"]},
    }
    return {"backends": {"chroma": deepcopy(run), "jev": deepcopy(run)}}


def test_separates_summary_loss_from_loss_in_full_record():
    data = small_fixture()
    report = benchmark.make_report(data)
    assert report["coverage_totals"]["summary"] == {
        "requirements": 2, "captured": 0, "capture_gaps": 2}
    assert report["coverage_totals"]["record"] == {
        "requirements": 2, "captured": 1, "capture_gaps": 1}
    assert report["mode"] == "audit_only"
    assert not report["backends"] and not report["comparison_ready"]


def test_same_document_does_not_make_an_omitted_detail_retrieved():
    data = small_fixture()
    result = backend_result(data, hits={"promise": [1], "clue": [2]})
    report = benchmark.make_report(data, live_result=result, encoder_model="cached-test-model")
    assert report["comparison_ready"]
    promise, clue = report["backends"]["jev"]["cases"]
    assert promise["all_evidence_retrieved"] is True
    assert clue["requirements"][0]["diagnosis"] == "capture_gap"
    assert clue["recall_on_captured"] is None
    assert clue["all_evidence_retrieved"] is False


def test_empty_success_is_a_miss_but_backend_error_is_not():
    data = small_fixture()
    capture = benchmark.coverage(data, "record")
    case = data["cases"][0]
    missed = benchmark.score_case(case, capture, {"status": "ok", "hits": []})
    failed = benchmark.score_case(case, capture, {"status": "error", "hits": []})
    assert missed["requirements"][0]["diagnosis"] == "retrieval_miss"
    assert missed["recall_on_captured"] == 0
    assert failed["requirements"][0]["diagnosis"] == "not_evaluated"
    assert failed["recall_on_captured"] is None
    assert failed["all_evidence_retrieved"] is None


@pytest.mark.parametrize("hits", [[3], [1, 1], [1, 2], [True], ["1"]])
def test_invalid_returns_never_count_as_success(hits):
    data = small_fixture()
    result = benchmark.score_case(data["cases"][0], benchmark.coverage(data, "record"),
                                  {"status": "ok", "hits": hits})
    assert result["status"] == "invalid_output"
    assert result["recall_on_captured"] is None


@pytest.mark.parametrize("field,value", [
    ("corpus_sha256", "different"), ("encoder_model", "different"),
])
def test_unfair_or_failed_run_is_not_comparable(field, value):
    data = small_fixture()
    result = backend_result(data)
    result["backends"]["jev"][field] = value
    report = benchmark.make_report(data, live_result=result, encoder_model="cached-test-model")
    assert report["comparison_ready"] is False
    assert report["backends"]["jev"]["cases"][0]["recall_on_captured"] is None


def test_missing_backend_or_case_cannot_pass_comparison():
    data = small_fixture()
    result = backend_result(data)
    del result["backends"]["jev"]["results"]["promise"]
    assert not benchmark.make_report(data, live_result=result,
                                     encoder_model="cached-test-model")["comparison_ready"]
    del result["backends"]["jev"]
    assert not benchmark.make_report(data, live_result=result,
                                     encoder_model="cached-test-model")["comparison_ready"]


def test_partial_backend_error_preserves_valid_per_case_results():
    data = small_fixture()
    result = backend_result(data)
    result["backends"]["jev"]["status"] = "error"
    result["backends"]["jev"]["results"]["clue"] = {"status": "error", "hits": []}
    report = benchmark.make_report(data, live_result=result, encoder_model="cached-test-model")
    assert not report["comparison_ready"]
    assert report["backends"]["jev"]["cases"][0]["recall_on_captured"] == 1
    assert report["backends"]["jev"]["cases"][1]["all_evidence_retrieved"] is None


def test_success_without_hits_is_not_a_successful_empty_search():
    data = small_fixture()
    result = backend_result(data)
    for backend in result["backends"].values():
        for case in backend["results"]:
            backend["results"][case] = {"status": "ok"}
    report = benchmark.make_report(data, live_result=result, encoder_model="cached-test-model")
    assert not report["comparison_ready"]
    assert report["backends"]["chroma"]["cases"][0]["status"] == "invalid_output"


def test_unknown_chapter_is_preserved_as_invalid_not_counted():
    data = small_fixture()
    data["cases"][0]["before_chapter"] = 10
    result = backend_result(data, hits={"promise": [8]})
    report = benchmark.make_report(data, live_result=result, encoder_model="cached-test-model")
    score = report["backends"]["chroma"]["cases"][0]
    assert score["hits"] == [8] and score["status"] == "invalid_output"
    assert score["recall_on_captured"] is None


@pytest.mark.parametrize("change", ["missing", "duplicate", "wrong_chapter", "non_bool"])
def test_capture_rows_must_match_requirements_before_scoring(change):
    data = small_fixture()
    capture = benchmark.coverage(data, "record")
    if change == "missing":
        capture = []
    elif change == "duplicate":
        capture.append(deepcopy(capture[0]))
    elif change == "wrong_chapter":
        capture[0]["chapter"] = 2
    else:
        capture[0]["captured"] = 1
    score = benchmark.score_case(data["cases"][0], capture, {"status": "ok", "hits": [1]})
    assert score["status"] == "invalid_capture"
    assert score["all_evidence_available"] is None and score["all_evidence_retrieved"] is None
    assert score["recall_on_captured"] is None


@pytest.mark.parametrize("mutation", [
    lambda d: d["cases"][0]["requirements"][0].update(quote="不是正文的話"),
    lambda d: d["cases"][0]["requirements"][0].update(probes=["編造的依據"]),
    lambda d: d["cases"][0]["requirements"][0].update(chapter=3),
    lambda d: d["chapters"][1].update(chapter=1),
    lambda d: d["chapters"][0].update(record="另一份記錄"),
    lambda d: d["cases"][0].update(limit=True),
])
def test_bad_fixture_rejected_before_retrieval(mutation):
    data = small_fixture()
    mutation(data)
    with pytest.raises(ValueError):
        benchmark.build_corpus(data)


def test_corpus_is_sorted_and_contains_no_answers_or_body():
    data = small_fixture()
    data["chapters"].reverse()
    corpus = benchmark.build_corpus(data)
    assert [row["chapter"] for row in corpus] == [1, 2, 3]
    assert all(set(row) == {"chapter", "text", "source_path", "source_sha256"} for row in corpus)
    assert "三角" not in json.dumps(corpus, ensure_ascii=False)
    changed = deepcopy(corpus)
    changed[0]["text"] += " extra"
    assert benchmark.corpus_fingerprint(corpus) != benchmark.corpus_fingerprint(changed)


def test_offline_cli_never_starts_worker(tmp_path, monkeypatch, capsys):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(small_fixture(), ensure_ascii=False))
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: pytest.fail("offline spawned worker"))
    assert benchmark.main(["--fixture", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "audit_only" and not report["comparison_ready"]


def test_live_needs_explicit_consent_and_models():
    with pytest.raises(SystemExit) as exc:
        benchmark.main(["--live"])
    assert exc.value.code == 2


def test_curated_fixture_has_distinct_prose_and_both_capture_gap_types():
    data = json.loads(benchmark.DEFAULT_FIXTURE.read_text())
    benchmark.validate_fixture(data)
    assert all(row["body"] != row["summary"] and len(row["summary"]) <= 80
               for row in data["chapters"])
    summary = {r["requirement"]: r["captured"] for r in benchmark.coverage(data, "summary")}
    record = {r["requirement"]: r["captured"] for r in benchmark.coverage(data, "record")}
    assert any(summary[key] and record[key] for key in summary)
    assert any(not summary[key] and record[key] for key in summary)
    assert any(not record[key] for key in record)
