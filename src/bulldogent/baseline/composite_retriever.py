import structlog

from bulldogent.baseline.config import RetrievalConfig
from bulldogent.baseline.retriever import BaselineRetriever
from bulldogent.baseline.types import RetrievalResult

_logger = structlog.get_logger()


class CompositeRetriever:
    """Queries multiple retrievers and merges results by score."""

    def __init__(
        self,
        baseline_retriever: BaselineRetriever | None,
        learned_retriever: BaselineRetriever | None,
        retrieval_config: RetrievalConfig,
    ) -> None:
        self._retrievers: list[BaselineRetriever] = []
        if baseline_retriever:
            self._retrievers.append(baseline_retriever)
        if learned_retriever:
            self._retrievers.append(learned_retriever)
        self._retrieval_config = retrieval_config

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[RetrievalResult]:
        top_k = top_k or self._retrieval_config.top_k

        all_results: list[RetrievalResult] = []
        for retriever in self._retrievers:
            try:
                results = retriever.retrieve(query, top_k=top_k, min_score=min_score)
                all_results.extend(results)
            except Exception:
                _logger.debug("composite_retriever_source_failed", exc_info=True)

        # Sort by score ascending — lower distance = more similar in ChromaDB
        all_results.sort(key=lambda r: r.score)

        _logger.debug(
            "composite_retrieval",
            query_preview=query[:80],
            sources=len(self._retrievers),
            total_candidates=len(all_results),
            returned=min(len(all_results), top_k),
        )

        return all_results[:top_k]
