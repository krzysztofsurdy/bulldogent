import structlog

from bulldogent.baseline.chunker import chunk_text
from bulldogent.baseline.config import LearningConfig
from bulldogent.embedding.provider import AbstractEmbeddingProvider

_logger = structlog.get_logger()


class Learner:
    """Stores successful Q&A pairs in a learned ChromaDB collection."""

    def __init__(
        self,
        learning_config: LearningConfig,
        embedding_provider: AbstractEmbeddingProvider,
    ) -> None:
        import chromadb

        self._embedding_provider = embedding_provider

        if learning_config.backend == "http":
            http_cfg = learning_config.http
            self._client = chromadb.HttpClient(
                host=http_cfg.host,
                port=http_cfg.port,
                ssl=http_cfg.ssl,
            )
        else:
            path = learning_config.persistent.path
            path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(path))

        self._collection = self._client.get_or_create_collection(
            name=learning_config.collection,
            metadata={"hnsw:space": "cosine"},
        )

    def learn(
        self,
        question: str,
        answer: str,
        channel_id: str,
        thread_id: str | None,
        timestamp: str,
    ) -> None:
        """Chunk, embed, and store a Q&A pair."""
        text = f"Q: {question}\n\nA: {answer}"

        chunks = chunk_text(
            text=text,
            source="conversation",
            title=question[:80],
            url="",
        )

        if not chunks:
            return

        texts = [c.content for c in chunks]
        embeddings = self._embedding_provider.embed(texts)

        ids = [f"conversation:{timestamp}:{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source": "conversation",
                "title": question[:80],
                "channel_id": channel_id,
                "thread_id": thread_id or "",
                "timestamp": timestamp,
            }
            for _ in chunks
        ]

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,  # type: ignore[arg-type]
            documents=texts,
            metadatas=metadatas,  # type: ignore[arg-type]
        )

        _logger.debug(
            "learned",
            question_preview=question[:60],
            chunks=len(chunks),
        )
