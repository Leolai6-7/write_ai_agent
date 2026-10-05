"""Tests for ChromaDB semantic retrieval."""

import os

import pytest

from memory.retrieval import SemanticRetriever

pytestmark = pytest.mark.skipif(
    os.getenv("NOVEL_TEST_SEMANTIC") != "1",
    reason="Set NOVEL_TEST_SEMANTIC=1 for real Chroma/model integration tests",
)


@pytest.fixture
def retriever(tmp_path):
    return SemanticRetriever(tmp_path / "chroma_test", embedding_model=os.getenv(
        "NOVEL_TEST_ENCODER", "BAAI/bge-small-zh-v1.5"))


def test_add_and_query(retriever):
    retriever.add_chapter(1, "伊澤到達圖書館並遇見守護者米娜")
    retriever.add_chapter(2, "伊澤通過守護者考驗獲得基礎區域權限")
    retriever.add_chapter(3, "伊澤發現父親留下的禁咒筆記")

    results = retriever.query("父親的線索", n_results=2, max_distance=1.0)
    assert len(results) >= 1
    # Chapter 3 should be most relevant (mentions 父親)
    assert results[0]["chapter_id"] == 3


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


def test_real_backend_chapter_boundary_and_exact_character_filter(retriever):
    retriever.add_chapter(1, "米娜持有銅鑰匙", characters=["米娜"])
    retriever.add_chapter(2, "米娜在碼頭等候", characters=["米娜"])
    retriever.add_chapter(3, "未來米娜摧毀銅鑰匙", characters=["米娜"])
    retriever.add_chapter(1_000, "米娜子持有銅鑰匙", characters=["米娜子"])
    results = retriever.query("銅鑰匙", n_results=5, max_distance=2.0,
                              before_chapter=3, filter_characters=["米娜"])
    assert {r["chapter_id"] for r in results} == {1, 2}
    assert retriever.query("銅鑰匙", n_results=5, max_distance=2.0,
                           before_chapter=3, filter_characters=["米娜子"]) == []
