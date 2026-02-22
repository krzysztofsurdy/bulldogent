from bulldogent.embedding.adapters import (
    BedrockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    VertexEmbeddingProvider,
)
from bulldogent.embedding.config import (
    AbstractEmbeddingConfig,
    BedrockEmbeddingConfig,
    EmbeddingProviderType,
    OpenAIEmbeddingConfig,
    VertexEmbeddingConfig,
)
from bulldogent.embedding.provider import AbstractEmbeddingProvider


def create_embedding_provider(config: AbstractEmbeddingConfig) -> AbstractEmbeddingProvider:
    match config:
        case OpenAIEmbeddingConfig():
            return OpenAIEmbeddingProvider(config)
        case BedrockEmbeddingConfig():
            return BedrockEmbeddingProvider(config)
        case VertexEmbeddingConfig():
            return VertexEmbeddingProvider(config)
        case _:
            raise ValueError(f"Unknown embedding config: {type(config).__name__}")


__all__ = [
    "AbstractEmbeddingConfig",
    "AbstractEmbeddingProvider",
    "BedrockEmbeddingConfig",
    "BedrockEmbeddingProvider",
    "EmbeddingProviderType",
    "OpenAIEmbeddingConfig",
    "OpenAIEmbeddingProvider",
    "VertexEmbeddingConfig",
    "VertexEmbeddingProvider",
    "create_embedding_provider",
]
