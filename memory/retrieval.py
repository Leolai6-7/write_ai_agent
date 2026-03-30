"""Semantic retrieval using ChromaDB for relevant memory search."""

from __future__ import annotations

from pathlib import Path

from infrastructure.logger import get_logger

logger = get_logger("retrieval")


class SemanticRetriever:
    """ChromaDB-based semantic retrieval for chapter memories.

    Stores one-line summaries as documents with structured metadata,
    and retrieves the most relevant ones based on query + filters.
    """

    def __init__(self, chroma_dir: Path, collection_name: str = "chapter_summaries"):
        import chromadb

        self._client = chromadb.PersistentClient(path=str(chroma_dir))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB initialized at %s (collection: %s)", chroma_dir, collection_name)

    def add_chapter(
        self,
        chapter_id: int,
        summary: str,
        arc_name: str = "",
        characters: list[str] | None = None,
        scene_type: str = "",
    ) -> None:
        """Add a chapter summary with structured metadata."""
        metadata = {
            "chapter_id": chapter_id,
            "arc": arc_name,
            "characters": ",".join(characters) if characters else "",
            "scene_type": scene_type,
        }
        self._collection.upsert(
            documents=[summary],
            metadatas=[metadata],
            ids=[f"ch_{chapter_id}"],
        )
        logger.debug("Added chapter %d to vector store", chapter_id)

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        max_distance: float = 0.5,
        filter_characters: list[str] | None = None,
        exclude_chapters: list[int] | None = None,
    ) -> list[dict]:
        """Find relevant chapter summaries with distance filtering and metadata filters.

        Args:
            query_text: The query (typically a chapter objective).
            n_results: Max number of results to return.
            max_distance: Only return results with distance < this threshold (0=identical, 1=unrelated).
            filter_characters: Only return chapters involving these characters.
            exclude_chapters: Chapter IDs to exclude (e.g., current chapter).

        Returns:
            List of dicts with chapter_id, summary, distance, arc, characters.
        """
        count = self._collection.count()
        if count == 0:
            return []

        n = min(n_results * 2, count)  # Fetch extra to account for filtering

        # Build metadata filter
        where_filter = None
        if filter_characters:
            # Match chapters containing any of the specified characters
            if len(filter_characters) == 1:
                where_filter = {"characters": {"$contains": filter_characters[0]}}
            else:
                where_filter = {
                    "$or": [{"characters": {"$contains": c}} for c in filter_characters]
                }

        query_kwargs = {
            "query_texts": [query_text],
            "n_results": n,
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        try:
            results = self._collection.query(**query_kwargs)
        except Exception as e:
            logger.warning("ChromaDB query failed (falling back to unfiltered): %s", e)
            results = self._collection.query(
                query_texts=[query_text],
                n_results=min(n_results, count),
            )

        output = []
        if results["documents"] and results["documents"][0]:
            exclude_set = set(exclude_chapters or [])
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results["distances"] else 0.0

                ch_id = meta.get("chapter_id", 0)

                # Apply filters
                if dist > max_distance:
                    continue
                if ch_id in exclude_set:
                    continue

                output.append({
                    "chapter_id": ch_id,
                    "summary": doc,
                    "distance": dist,
                    "arc": meta.get("arc", ""),
                    "characters": meta.get("characters", "").split(",") if meta.get("characters") else [],
                })

                if len(output) >= n_results:
                    break

        logger.debug(
            "Query '%s...' returned %d results (filtered from %d, threshold=%.2f)",
            query_text[:30], len(output),
            len(results["documents"][0]) if results["documents"] else 0,
            max_distance,
        )
        return output

    def get_count(self) -> int:
        """Get total number of stored summaries."""
        return self._collection.count()
