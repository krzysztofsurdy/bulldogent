from collections.abc import Mapping
from pathlib import Path
from typing import Any

import structlog

from bulldogent.baseline.config import RetrievalConfig
from bulldogent.baseline.types import RetrievalResult
from bulldogent.embedding.provider import AbstractEmbeddingProvider

_logger = structlog.get_logger()


class BaselineRetriever:
    def __init__(
        self,
        storage_path: Path,
        embedding_provider: AbstractEmbeddingProvider,
        retrieval_config: RetrievalConfig,
        collection_name: str = "baseline",
    ) -> None:
        import chromadb

        self._retrieval_config = retrieval_config
        self._embedding_provider = embedding_provider
        self._client = chromadb.PersistentClient(path=str(storage_path))
        self._collection = self._client.get_collection(collection_name)

    @classmethod
    def from_http(
        cls,
        host: str,
        port: int,
        embedding_provider: AbstractEmbeddingProvider,
        retrieval_config: RetrievalConfig,
        collection_name: str = "learned",
        ssl: bool = False,
    ) -> "BaselineRetriever":
        import chromadb

        instance = cls.__new__(cls)
        instance._retrieval_config = retrieval_config
        instance._embedding_provider = embedding_provider
        instance._client = chromadb.HttpClient(host=host, port=port, ssl=ssl)
        instance._collection = instance._client.get_collection(collection_name)
        return instance

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[RetrievalResult]:
        """Query the baseline knowledge base and return relevant chunks.

        ChromaDB returns cosine distances: lower = more similar.
        Only results with distance <= min_score are returned.
        """
        top_k = top_k or self._retrieval_config.top_k
        min_score = min_score if min_score is not None else self._retrieval_config.min_score

        query_embedding = self._embedding_provider.embed_query(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],  # type: ignore[arg-type]
            n_results=top_k,
        )

        documents = results.get("documents") or [[]]
        distances = results.get("distances") or [[]]
        metadatas = results.get("metadatas") or [[]]

        docs: list[str] = documents[0] if documents else []
        dists: list[float] = distances[0] if distances else []
        metas: list[Mapping[str, Any]] = metadatas[0] if metadatas else []

        if not docs:
            return []

        retrieval_results: list[RetrievalResult] = []

        for i, doc in enumerate(docs):
            distance = dists[i] if i < len(dists) else 1.0
            metadata = metas[i] if i < len(metas) else {}

            # Filter by distance threshold — lower distance = more relevant
            if distance > min_score:
                continue

            retrieval_results.append(
                RetrievalResult(
                    content=doc,
                    source=str(metadata.get("source", "unknown")),
                    title=str(metadata.get("title", "")),
                    url=str(metadata.get("url", "")),
                    score=float(distance),
                )
            )

        _logger.debug(
            "baseline_retrieval",
            query_preview=query[:80],
            candidates=len(docs),
            matched=len(retrieval_results),
        )

        return retrieval_results
