"""Semantic retrieval using ChromaDB for relevant memory search."""

from __future__ import annotations

from pathlib import Path

from infrastructure.logger import get_logger

logger = get_logger("retrieval")


class SemanticRetriever:
    """ChromaDB-based semantic retrieval for chapter memories.

    Stores one-line summaries as documents and retrieves the most relevant
    ones based on the current chapter objective.
    """

    def __init__(self, chroma_dir: Path, collection_name: str = "chapter_summaries"):
        import chromadb

        self._client = chromadb.PersistentClient(path=str(chroma_dir))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB initialized at %s (collection: %s)", chroma_dir, collection_name)

    def add_chapter(self, chapter_id: int, summary: str, arc_name: str = "") -> None:
        """Add a chapter summary to the vector store."""
        self._collection.upsert(
            documents=[summary],
            metadatas=[{"chapter_id": chapter_id, "arc": arc_name}],
            ids=[f"ch_{chapter_id}"],
        )
        logger.debug("Added chapter %d to vector store", chapter_id)

    def query(self, query_text: str, n_results: int = 5) -> list[dict]:
        """Find the most relevant chapter summaries for a query.

        Args:
            query_text: The query (typically a chapter objective).
            n_results: Number of results to return.

        Returns:
            List of dicts with chapter_id, summary, distance, and arc.
        """
        count = self._collection.count()
        if count == 0:
            return []

        # Don't request more results than available
        n = min(n_results, count)

        results = self._collection.query(
            query_texts=[query_text],
            n_results=n,
        )

        output = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results["distances"] else 0.0
                output.append({
                    "chapter_id": meta.get("chapter_id", 0),
                    "summary": doc,
                    "distance": dist,
                    "arc": meta.get("arc", ""),
                })

        logger.debug("Query '%s...' returned %d results", query_text[:30], len(output))
        return output

    def get_count(self) -> int:
        """Get total number of stored summaries."""
        return self._collection.count()
