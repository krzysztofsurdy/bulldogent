import os
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
    def from_envs(cls, raw: dict[str, Any], model: str) -> "AbstractEmbeddingConfig": ...


@dataclass
class OpenAIEmbeddingConfig(AbstractEmbeddingConfig):
    api_key: str
    api_url: str | None = None

    @classmethod
    def from_envs(cls, raw: dict[str, Any], model: str) -> "OpenAIEmbeddingConfig":
        api_key = os.getenv(raw.get("api_key_env", ""), "")
        if not api_key:
            raise ValueError(f"Missing env var: {raw.get('api_key_env', '')}")

        api_url = os.getenv(raw.get("api_url_env", ""), "") or None

        return cls(model=model, api_key=api_key, api_url=api_url)


@dataclass
class BedrockEmbeddingConfig(AbstractEmbeddingConfig):
    region: str

    @classmethod
    def from_envs(cls, raw: dict[str, Any], model: str) -> "BedrockEmbeddingConfig":
        region = os.getenv(raw.get("region_env", ""), "")
        if not region:
            raise ValueError(f"Missing env var: {raw.get('region_env', '')}")

        return cls(model=model, region=region)


@dataclass
class VertexEmbeddingConfig(AbstractEmbeddingConfig):
    project_id: str
    location: str

    @classmethod
    def from_envs(cls, raw: dict[str, Any], model: str) -> "VertexEmbeddingConfig":
        project_id = os.getenv(raw.get("project_id_env", ""), "")
        if not project_id:
            raise ValueError(f"Missing env var: {raw.get('project_id_env', '')}")

        location = os.getenv(raw.get("location_env", ""), "")
        if not location:
            raise ValueError(f"Missing env var: {raw.get('location_env', '')}")

        return cls(model=model, project_id=project_id, location=location)
