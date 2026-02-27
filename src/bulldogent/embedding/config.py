from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class EmbeddingProviderType(StrEnum):
    OPENAI = "openai"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


@dataclass
class AbstractEmbeddingConfig(ABC):
    model: str

    @classmethod
    @abstractmethod
    def from_yaml(cls, raw: dict[str, Any], model: str) -> "AbstractEmbeddingConfig": ...


@dataclass
class OpenAIEmbeddingConfig(AbstractEmbeddingConfig):
    api_key: str
    api_url: str | None = None

    @classmethod
    def from_yaml(cls, raw: dict[str, Any], model: str) -> "OpenAIEmbeddingConfig":
        api_key = raw.get("api_key", "")
        if not api_key:
            raise ValueError("Missing embedding openai.api_key")

        api_url = raw.get("api_url") or None

        return cls(model=model, api_key=api_key, api_url=api_url)


@dataclass
class BedrockEmbeddingConfig(AbstractEmbeddingConfig):
    region: str

    @classmethod
    def from_yaml(cls, raw: dict[str, Any], model: str) -> "BedrockEmbeddingConfig":
        region = raw.get("region", "")
        if not region:
            raise ValueError("Missing embedding bedrock.region")

        return cls(model=model, region=region)


@dataclass
class VertexEmbeddingConfig(AbstractEmbeddingConfig):
    project_id: str
    location: str

    @classmethod
    def from_yaml(cls, raw: dict[str, Any], model: str) -> "VertexEmbeddingConfig":
        project_id = raw.get("project_id", "")
        if not project_id:
            raise ValueError("Missing embedding vertex.project_id")

        location = raw.get("location", "")
        if not location:
            raise ValueError("Missing embedding vertex.location")

        return cls(model=model, project_id=project_id, location=location)
