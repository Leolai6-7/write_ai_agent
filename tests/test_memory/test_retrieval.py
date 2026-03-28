"""Tests for ChromaDB semantic retrieval."""

import pytest

from memory.retrieval import SemanticRetriever


@pytest.fixture
def retriever(tmp_path):
    return SemanticRetriever(tmp_path / "chroma_test")


def test_add_and_query(retriever):
    retriever.add_chapter(1, "伊澤到達圖書館並遇見守護者米娜")
    retriever.add_chapter(2, "伊澤通過守護者考驗獲得基礎區域權限")
    retriever.add_chapter(3, "伊澤發現父親留下的禁咒筆記")

    results = retriever.query("父親的線索", n_results=2)
    assert len(results) == 2
    # Chapter 3 should be most relevant (mentions 父親)
    assert any(r["chapter_id"] == 3 for r in results)


def test_empty_query(retriever):
    results = retriever.query("anything")
    assert results == []


def test_get_count(retriever):
    assert retriever.get_count() == 0
    retriever.add_chapter(1, "test summary")
    assert retriever.get_count() == 1


def test_upsert_same_chapter(retriever):
    retriever.add_chapter(1, "original summary")
    retriever.add_chapter(1, "updated summary")
    assert retriever.get_count() == 1
    results = retriever.query("updated", n_results=1)
    assert "updated" in results[0]["summary"]
