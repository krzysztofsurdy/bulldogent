import uuid

import structlog

from bulldogent.baseline.chunker import Chunker
from bulldogent.baseline.models import Knowledge
from bulldogent.embedding.provider import AbstractEmbeddingProvider
from bulldogent.util.db import get_session

_logger = structlog.get_logger()


class Learner:
    """Stores successful Q&A pairs in the knowledge table."""

    def __init__(
        self,
        embedding_provider: AbstractEmbeddingProvider,
        chunker: Chunker | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._chunker = chunker or Chunker()

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

        chunks = self._chunker.chunk_text(
            text=text,
            source="conversation",
            title=question[:80],
            url="",
        )

        if not chunks:
            return

        texts = [c.content for c in chunks]
        embeddings = self._embedding_provider.embed(texts)

        rows = [
            Knowledge(
                id=uuid.uuid4(),
                source="conversation",
                title=question[:80],
                content=chunk.content,
                url="",
                metadata_={
                    "channel_id": channel_id,
                    "thread_id": thread_id or "",
                    "timestamp": timestamp,
                },
                embedding=embeddings[i],
            )
            for i, chunk in enumerate(chunks)
        ]

        with get_session() as session:
            session.add_all(rows)
            session.commit()

        _logger.debug(
            "learned",
            question_preview=question[:60],
            chunks=len(chunks),
        )
