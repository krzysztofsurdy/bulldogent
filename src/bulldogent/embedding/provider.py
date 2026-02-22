from abc import ABC, abstractmethod

from bulldogent.embedding.config import AbstractEmbeddingConfig


class AbstractEmbeddingProvider(ABC):
    def __init__(self, config: AbstractEmbeddingConfig) -> None:
        self.config = config

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]
