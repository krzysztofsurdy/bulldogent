import structlog
from sqlalchemy import text

from bulldogent.baseline.config import RetrievalConfig
from bulldogent.baseline.types import RetrievalResult
from bulldogent.embedding.provider import AbstractEmbeddingProvider
from bulldogent.util.db import get_session

_logger = structlog.get_logger()


class BaselineRetriever:
    def __init__(
        self,
        embedding_provider: AbstractEmbeddingProvider,
        retrieval_config: RetrievalConfig,
    ) -> None:
        self._retrieval_config = retrieval_config
        self._embedding_provider = embedding_provider

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[RetrievalResult]:
        """Query the knowledge base and return relevant chunks.

        Uses cosine similarity via pgvector: similarity = 1 - distance.
        Only results with similarity >= min_score are returned.
        """
        top_k = top_k or self._retrieval_config.top_k
        min_score = min_score if min_score is not None else self._retrieval_config.min_score

        query_embedding = self._embedding_provider.embed_query(query)

        sql = text("""
            SELECT
                source,
                title,
                content,
                url,
                1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM knowledge
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)

        with get_session() as session:
            rows = session.execute(
                sql,
                {"embedding": query_embedding, "top_k": top_k},
            ).fetchall()

        results: list[RetrievalResult] = []
        for row in rows:
            similarity: float = float(row.similarity)
            if similarity < min_score:
                continue
            results.append(
                RetrievalResult(
                    content=row.content,
                    source=row.source,
                    title=row.title,
                    url=row.url,
                    score=similarity,
                )
            )

        _logger.debug(
            "baseline_retrieval",
            query_preview=query[:80],
            candidates=len(rows),
            matched=len(results),
        )

        return results
