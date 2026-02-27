import structlog
from openai import OpenAI

from bulldogent.embedding.config import OpenAIEmbeddingConfig
from bulldogent.embedding.provider import AbstractEmbeddingProvider

_logger = structlog.get_logger()

_MAX_BATCH_SIZE = 500  # Keep well under OpenAI's 300k token-per-request limit


class OpenAIEmbeddingProvider(AbstractEmbeddingProvider):
    config: OpenAIEmbeddingConfig

    def __init__(self, config: OpenAIEmbeddingConfig) -> None:
        super().__init__(config)
        self._client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_url,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), _MAX_BATCH_SIZE):
            batch = texts[i : i + _MAX_BATCH_SIZE]
            _logger.debug("embedding_batch", batch_size=len(batch), offset=i)

            response = self._client.embeddings.create(
                model=self.config.model,
                input=batch,
            )
            all_embeddings.extend(item.embedding for item in response.data)

        return all_embeddings
