"""Retrieval contracts without Chroma, model downloads, or external calls."""

import pytest

from memory.retrieval import SemanticRetriever


class FakeCollection:
    def __init__(self, rows, respect_where=True):
        self.rows = rows
        self.calls = []
        self.respect_where = respect_where

    def count(self):
        return len(self.rows)

    def query(self, **kwargs):
        self.calls.append(kwargs)
        rows = self.rows
        if self.respect_where:
            where = kwargs.get("where", {})
            filters = where.get("$and", [where])
            for filt in filters:
                clause = filt.get("chapter_id", {})
                if "$lt" in clause:
                    rows = [r for r in rows if r[0] < clause["$lt"]]
                if "$nin" in clause:
                    rows = [r for r in rows if r[0] not in clause["$nin"]]
        rows = rows[:kwargs["n_results"]]
        return {
            "documents": [[summary for _, summary, _, _ in rows]],
            "metadatas": [[{"chapter_id": chapter, "characters": names}
                           for chapter, _, names, _ in rows]],
            "distances": [[distance for _, _, _, distance in rows]],
        }


def retriever_for(collection):
    retriever = SemanticRetriever.__new__(SemanticRetriever)
    retriever._collection = collection
    return retriever


def test_query_applies_chapter_boundary_at_backend_and_before_return():
    # Deliberately broken backend ignores filters; local validation must still hold.
    collection = FakeCollection([
        (9, "future", "阿青", 0.01), (4, "current", "阿青", 0.02),
        (3, "excluded", "阿青", 0.03), (2, "past", "阿青", 0.2),
        (1, "other past", "阿青", 0.3),
    ], respect_where=False)
    results = retriever_for(collection).query(
        "objective", n_results=2, before_chapter=4, exclude_chapters=[3],
    )
    assert [r["chapter_id"] for r in results] == [2, 1]
    assert collection.calls[0]["where"] == {"$and": [
        {"chapter_id": {"$lt": 4}}, {"chapter_id": {"$nin": [3]}},
    ]}


def test_exact_character_filter_expands_beyond_first_batch():
    collection = FakeCollection([
        (1, "not exact", "小阿青", 0.1), (2, "different person", "阿紫", 0.2),
        (3, "correct person", "阿青, 阿紫", 0.3),
    ])
    result = retriever_for(collection).query("objective", n_results=1,
                                             filter_characters=["阿青"])
    assert [r["chapter_id"] for r in result] == [3]
    assert result[0]["characters"] == ["阿青", "阿紫"]
    assert len(collection.calls) == 2
    assert all("where" not in call for call in collection.calls)


def test_filter_failure_does_not_retry_without_boundary():
    class BrokenCollection(FakeCollection):
        def query(self, **kwargs):
            self.calls.append(kwargs)
            raise RuntimeError("unsupported filter")

    collection = BrokenCollection([(4, "future", "", 0.0)])
    with pytest.raises(RuntimeError, match="unsupported filter"):
        retriever_for(collection).query("objective", before_chapter=4)
    assert len(collection.calls) == 1


def test_result_limit_distance_and_empty_results():
    collection = FakeCollection([(1, "relevant", "", 0.1), (2, "irrelevant", "", 0.9)])
    retriever = retriever_for(collection)
    assert [r["chapter_id"] for r in retriever.query("objective")] == [1]
    assert retriever.query("objective", n_results=0) == []
    assert retriever.query("objective", before_chapter=1) == []
