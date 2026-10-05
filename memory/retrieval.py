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

    def __init__(
        self,
        chroma_dir: Path,
        collection_name: str = "chapter_summaries",
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
        allow_model_download: bool = False,
    ):
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        ef = SentenceTransformerEmbeddingFunction(
            model_name=embedding_model, local_files_only=not allow_model_download,
        )
        self._client = chromadb.PersistentClient(path=str(chroma_dir))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=ef,
        )
        logger.info(
            "ChromaDB initialized at %s (collection: %s, model: %s)",
            chroma_dir, collection_name, embedding_model,
        )

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
        before_chapter: int | None = None,
    ) -> list[dict]:
        """Find relevant chapter summaries with distance filtering and metadata filters.

        Args:
            query_text: The query (typically a chapter objective).
            n_results: Max number of results to return.
            max_distance: Only return results with distance < this threshold (0=identical, 1=unrelated).
            filter_characters: Only return chapters involving these characters.
            exclude_chapters: Chapter IDs to exclude (e.g., current chapter).
            before_chapter: Only retrieve chapter IDs strictly below this boundary.

        Returns:
            List of dicts with chapter_id, summary, distance, arc, characters.
        """
        count = self._collection.count()
        if count == 0 or n_results <= 0:
            return []

        # Chroma metadata does not support substring $contains. Characters are
        # stored as a comma-separated field, so enforce exact names locally.
        # Chapter bounds are applied both in Chroma and after retrieval: a
        # backend error must never silently widen a chronological query.
        filters = []
        if before_chapter is not None:
            filters.append({"chapter_id": {"$lt": before_chapter}})
        exclude_set = set(exclude_chapters or [])
        if exclude_set:
            filters.append({"chapter_id": {"$nin": sorted(exclude_set)}})
        where = filters[0] if len(filters) == 1 else {"$and": filters} if filters else None
        wanted_characters = set(filter_characters or [])
        n = min(max(n_results * 2, 1), count)
        while True:
            kwargs = {"query_texts": [query_text], "n_results": n}
            if where:
                kwargs["where"] = where
            results = self._collection.query(**kwargs)
            docs = (results.get("documents") or [[]])[0]
            metadata = (results.get("metadatas") or [[]])[0]
            distances = (results.get("distances") or [[]])[0]
            output = []
            seen = set()
            for i, doc in enumerate(docs):
                meta = (metadata[i] if i < len(metadata) else None) or {}
                dist = distances[i] if i < len(distances) else None
                ch_id = meta.get("chapter_id")
                if (not isinstance(ch_id, int) or isinstance(ch_id, bool) or ch_id < 1
                        or dist is None or dist > max_distance):
                    continue
                if ch_id in exclude_set or ch_id in seen:
                    continue
                if before_chapter is not None and ch_id >= before_chapter:
                    continue
                characters = [c.strip() for c in meta.get("characters", "").split(",") if c.strip()]
                if wanted_characters and not wanted_characters.intersection(characters):
                    continue
                output.append({
                    "chapter_id": ch_id, "summary": doc, "distance": dist,
                    "arc": meta.get("arc", ""), "characters": characters,
                })
                seen.add(ch_id)
                if len(output) >= n_results:
                    break
            if len(output) >= n_results or n >= count or len(docs) < n:
                break
            # A relevant character can rank beyond the first batch.
            n = min(n * 2, count)

        logger.debug(
            "Query '%s...' returned %d results (filtered from %d, threshold=%.2f)",
            query_text[:30], len(output),
            len(docs),
            max_distance,
        )
        return output

    def get_count(self) -> int:
        """Get total number of stored summaries."""
        return self._collection.count()
