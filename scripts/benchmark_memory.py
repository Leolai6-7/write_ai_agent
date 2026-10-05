"""Equal-input recall evaluation and source-to-record coverage audit.

Default execution is a read-only, dependency-free audit of curated fictional
fixtures. Live retrieval requires an explicit paid-API flag and cached models.
Marker coverage is not automatic semantic fact verification or writing quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "examples/memory-eval/cases.json"


def fingerprint(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def corpus_fingerprint(corpus: list[dict]) -> str:
    return fingerprint([{"chapter": row["chapter"], "text": row["text"]} for row in corpus])


def validate_fixture(data: dict) -> None:
    """Fail before invoking any backend if source/gold references are malformed."""
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Expected fixture schema 1")
    chapters = data.get("chapters")
    cases = data.get("cases")
    if not isinstance(chapters, list) or not chapters or not isinstance(cases, list) or not cases:
        raise ValueError("Nonempty chapters and cases are required")
    by_chapter = {}
    for row in chapters:
        if not isinstance(row, dict):
            raise ValueError("Each chapter must be an object")
        chapter = row.get("chapter")
        if type(chapter) is not int or chapter < 1 or chapter in by_chapter:
            raise ValueError("Chapter numbers must be unique positive integers")
        for field in ("title", "body", "summary", "record"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Chapter {chapter}: nonempty {field} required")
        if len(row["record"]) > 4000:
            raise ValueError("Shared record exceeds the Jev observation limit")
        if row["summary"] not in row["record"]:
            raise ValueError("The record must contain its actual summary")
        by_chapter[chapter] = row
    case_ids, requirement_ids = set(), set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each case must be an object")
        for field in ("id", "question"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f"Nonempty case {field} required")
        if case["id"] in case_ids:
            raise ValueError("Duplicate case id")
        case_ids.add(case["id"])
        before = case.get("before_chapter")
        if type(before) is not int or before < 2:
            raise ValueError("before_chapter must be an integer >= 2")
        if type(case.get("limit")) is not int or not 1 <= case["limit"] <= 3:
            raise ValueError("Shared output limit must be 1–3 chapters")
        requirements = case.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise ValueError("Every case needs source-backed requirements")
        for requirement in requirements:
            if not isinstance(requirement, dict):
                raise ValueError("Each requirement must be an object")
            rid = requirement.get("id")
            if not isinstance(rid, str) or not rid.strip() or rid in requirement_ids:
                raise ValueError("Requirement ids must be nonempty and globally unique")
            requirement_ids.add(rid)
            chapter = requirement.get("chapter")
            if type(chapter) is not int or chapter not in by_chapter or chapter >= before:
                raise ValueError(f"{rid}: source must precede the queried chapter")
            quote, probes = requirement.get("quote"), requirement.get("probes")
            if not isinstance(quote, str) or not quote.strip() or quote not in by_chapter[chapter]["body"]:
                raise ValueError(f"{rid}: quote is not in the source manuscript")
            if (not isinstance(probes, list) or not probes
                    or any(not isinstance(p, str) or not p.strip() or p not in quote for p in probes)):
                raise ValueError(f"{rid}: probes must be exact fragments of the source quote")
        if len({r["chapter"] for r in requirements}) > case["limit"]:
            raise ValueError("Output budget cannot hold all required source chapters")


def build_corpus(data: dict, view: str = "record") -> list[dict]:
    validate_fixture(data)
    if view not in ("summary", "record"):
        raise ValueError("Corpus view must be summary or record")
    return [{"chapter": row["chapter"], "text": row[view],
             "source_path": f"outputs/chapter_{row['chapter']:03d}.md",
             "source_sha256": hashlib.sha256(row["body"].encode()).hexdigest()}
            for row in sorted(data["chapters"], key=lambda row: row["chapter"])]


def coverage(data: dict, view: str) -> list[dict]:
    corpus = {row["chapter"]: row["text"] for row in build_corpus(data, view)}
    rows = []
    for case in data["cases"]:
        for req in case["requirements"]:
            missing = [probe for probe in req["probes"] if probe not in corpus[req["chapter"]]]
            rows.append({"case": case["id"], "requirement": req["id"],
                         "chapter": req["chapter"], "source_quote": req["quote"],
                         "captured": not missing, "missing_markers": missing})
    return rows


def score_case(case: dict, capture: list[dict], result: dict | None) -> dict:
    """Separate missing input, missing recall, invalid returns, and backend errors."""
    rows = [row for row in capture if row["case"] == case["id"]]
    expected = {req["id"]: req["chapter"] for req in case["requirements"]}
    capture_valid = (
        len(rows) == len(expected)
        and {row.get("requirement") for row in rows} == set(expected)
        and all(row.get("chapter") == expected.get(row.get("requirement"))
                and type(row.get("captured")) is bool for row in rows)
    )
    if result is None:
        result = {"status": "not_run"}
    elif not isinstance(result, dict):
        result = {"status": "invalid_output"}
    hits = result.get("hits", [] if result.get("status") != "ok" else None)
    if not isinstance(hits, list):
        hits = []
        result = {**result, "status": "invalid_output"}
    valid_hits = [h for h in hits if type(h) is int and 0 < h < case["before_chapter"]]
    invalid = len(valid_hits) != len(hits) or len(set(valid_hits)) != len(valid_hits)
    invalid = invalid or len(hits) > case["limit"]
    status = "invalid_output" if invalid else result.get("status", "not_run")
    if not capture_valid:
        return {"case": case["id"], "status": "invalid_capture", "hits": hits,
                "requirements": [{"id": key, "chapter": chapter, "diagnosis": "not_evaluated"}
                                 for key, chapter in expected.items()],
                "capturable_requirements": None, "recall_on_captured": None,
                "all_evidence_available": None, "all_evidence_retrieved": None,
                "elapsed_seconds": result.get("elapsed_seconds"), "trace": result.get("trace", {})}
    requirements = []
    for row in rows:
        if not row["captured"]:
            diagnosis = "capture_gap"
        elif status != "ok":
            diagnosis = "not_evaluated"
        elif row["chapter"] in valid_hits:
            diagnosis = "retrieved"
        else:
            diagnosis = "retrieval_miss"
        requirements.append({"id": row["requirement"], "chapter": row["chapter"],
                             "diagnosis": diagnosis})
    available = sum(row["captured"] for row in rows)
    retrieved = sum(row["diagnosis"] == "retrieved" for row in requirements)
    return {"case": case["id"], "status": status, "hits": hits,
            "requirements": requirements,
            "capturable_requirements": available,
            "recall_on_captured": retrieved / available if available and status == "ok" else None,
            "all_evidence_available": all(row["captured"] for row in rows),
            "all_evidence_retrieved": (
                all(row["diagnosis"] == "retrieved" for row in requirements)
                if status == "ok" else None),
            "elapsed_seconds": result.get("elapsed_seconds"), "trace": result.get("trace", {})}


def make_report(data: dict, view: str = "record", *, live_result: dict | None = None,
                encoder_model: str | None = None) -> dict:
    corpus = build_corpus(data, view)
    captures = {kind: coverage(data, kind) for kind in ("summary", "record")}
    report = {
        "mode": "live" if live_result is not None else "audit_only",
        "scope": "equal_input_source_recall_not_full_writing_pipeline",
        "coverage_method": "curated_exact_markers_not_semantic_verification",
        "dataset_sha256": fingerprint(data), "corpus_view": view,
        "corpus_sha256": corpus_fingerprint(corpus), "encoder_model": encoder_model,
        "capture_audit": captures,
        "coverage_totals": {
            kind: {"requirements": len(rows), "captured": sum(row["captured"] for row in rows),
                   "capture_gaps": sum(not row["captured"] for row in rows)}
            for kind, rows in captures.items()},
        "backends": {}, "comparison_ready": False,
    }
    if live_result is None:
        return report
    backends = live_result.get("backends", {})
    all_ready = set(backends) == {"chroma", "jev"}
    known_chapters = {row["chapter"] for row in corpus}
    for name in ("chroma", "jev"):
        run = backends.get(name, {"status": "not_run"})
        matched = (run.get("corpus_sha256") == report["corpus_sha256"]
                   and bool(encoder_model) and run.get("encoder_model") == encoder_model)
        scores = []
        for case in data["cases"]:
            result = run.get("results", {}).get(case["id"])
            if not matched:
                result = {"status": "input_mismatch"}
            elif result is None and run.get("status") != "ok":
                result = {"status": run.get("status", "not_run")}
            elif isinstance(result, dict):
                hits = result.get("hits", [])
                if isinstance(hits, list) and any(type(h) is not int or h not in known_chapters for h in hits):
                    result = {**result, "status": "invalid_output"}
            scores.append(score_case(case, captures[view], result))
        ready = matched and run.get("status") == "ok" and all(s["status"] == "ok" for s in scores)
        all_ready = all_ready and ready
        report["backends"][name] = {
            "status": run.get("status", "not_run"), "input_matched": matched,
            "build_seconds": run.get("build_seconds"), "cases": scores,
            "build_trace": run.get("build_trace", {}),
        }
    report["comparison_ready"] = all_ready
    report["metadata"] = live_result.get("metadata", {})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--corpus", choices=("record", "summary"), default="record")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--allow-paid-api", action="store_true")
    parser.add_argument("--encoder-model")
    parser.add_argument("--jev-model")
    parser.add_argument("--jev-worker", choices=("oneshot", "session"), default="oneshot",
                        help="session reuses the encoder, but reloads the graph for every query")
    args = parser.parse_args(argv)
    if args.live and (not args.allow_paid_api or not args.encoder_model or not args.jev_model):
        parser.error("Live comparison needs --allow-paid-api, --encoder-model and --jev-model")
    try:
        data = json.loads(args.fixture.read_text(encoding="utf-8"))
        corpus = build_corpus(data, args.corpus)
        result = None
        if args.live:
            try:
                from scripts.memory_eval_backends import run_live
            except ModuleNotFoundError:
                from memory_eval_backends import run_live
            # Answers, source manuscripts and coverage probes never reach the backends.
            cases = [{key: case[key] for key in ("id", "question", "before_chapter", "limit")}
                     for case in data["cases"]]
            result = run_live(corpus, cases, encoder_model=args.encoder_model, jev_model=args.jev_model,
                              jev_worker=args.jev_worker)
        report = make_report(data, args.corpus, live_result=result, encoder_model=args.encoder_model)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not args.live or report["comparison_ready"] else 2
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        # Do not print exception text from external clients; it could include credentials.
        print(json.dumps({"status": "error", "error_type": type(exc).__name__,
                          "comparison_ready": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
