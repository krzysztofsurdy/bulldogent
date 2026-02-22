import structlog
import vertexai
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

from bulldogent.embedding.config import VertexEmbeddingConfig
from bulldogent.embedding.provider import AbstractEmbeddingProvider

_logger = structlog.get_logger()

_MAX_BATCH_SIZE = 250  # Vertex AI embedding batch limit


class VertexEmbeddingProvider(AbstractEmbeddingProvider):
    config: VertexEmbeddingConfig

    def __init__(self, config: VertexEmbeddingConfig) -> None:
        super().__init__(config)
        vertexai.init(
            project=config.project_id,
            location=config.location,
        )
        self._model = TextEmbeddingModel.from_pretrained(config.model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), _MAX_BATCH_SIZE):
            batch = texts[i : i + _MAX_BATCH_SIZE]
            _logger.debug("embedding_batch", batch_size=len(batch), offset=i)

            inputs: list[str | TextEmbeddingInput] = [
                TextEmbeddingInput(text=t, task_type="RETRIEVAL_DOCUMENT") for t in batch
            ]
            embeddings = self._model.get_embeddings(inputs)
            all_embeddings.extend(e.values for e in embeddings)

        return all_embeddings
