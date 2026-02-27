from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

import structlog

from bulldogent.llm.provider.types import ProviderType
from bulldogent.util import PROJECT_ROOT, load_yaml_config

_logger = structlog.get_logger()
_DEFAULT_CONFIG = PROJECT_ROOT / "config" / "providers.yaml"


class _CommonConfig(TypedDict):
    model: str
    temperature: float | None
    max_tokens: int
    api_url: str | None


@dataclass
class AbstractProviderConfig(ABC):
    model: str
    temperature: float | None
    max_tokens: int
    api_url: str | None = field(default=None, kw_only=True)

    @classmethod
    def _read_common_config(cls, yaml_config: dict[str, Any]) -> _CommonConfig:
        """
        Helper: Read common fields from the resolved YAML config.

        Returns dict that can be unpacked with ** into subclass constructors.
        """
        temp = yaml_config.get("temperature")
        return _CommonConfig(
            model=yaml_config.get("model", ""),
            temperature=float(temp) if temp is not None else None,
            max_tokens=int(yaml_config.get("max_tokens", 2000)),
            api_url=yaml_config.get("api_url") or None,
        )

    @classmethod
    @abstractmethod
    def from_yaml(cls, config: dict[str, Any]) -> "AbstractProviderConfig":
        """Factory method: Create config from resolved YAML dict"""
        ...


@dataclass
class OpenAIConfig(AbstractProviderConfig):
    api_key: str

    @classmethod
    def from_yaml(cls, config: dict[str, Any]) -> "OpenAIConfig":
        common = cls._read_common_config(config)

        api_key = config.get("api_key", "")
        if not api_key:
            raise ValueError("Missing openai.api_key")

        return cls(api_key=api_key, **common)


@dataclass
class BedrockConfig(AbstractProviderConfig):
    region: str
    anthropic_version: str

    @classmethod
    def from_yaml(cls, config: dict[str, Any]) -> "BedrockConfig":
        common = cls._read_common_config(config)

        region = config.get("region", "")
        if not region:
            raise ValueError("Missing bedrock.region")

        anthropic_version = config.get("anthropic_version", "")
        if not anthropic_version:
            raise ValueError("Missing bedrock.anthropic_version")

        return cls(region=region, anthropic_version=anthropic_version, **common)


@dataclass
class VertexConfig(AbstractProviderConfig):
    project_id: str
    location: str

    @classmethod
    def from_yaml(cls, config: dict[str, Any]) -> "VertexConfig":
        common = cls._read_common_config(config)

        project_id = config.get("project_id", "")
        if not project_id:
            raise ValueError("Missing vertex.project_id")

        location = config.get("location", "")
        if not location:
            raise ValueError("Missing vertex.location")

        return cls(project_id=project_id, location=location, **common)


class ProviderConfigGenerator:
    def __init__(self, config_location: Path = _DEFAULT_CONFIG) -> None:
        self.config = load_yaml_config(config_location)

    def generate(self) -> Iterator[AbstractProviderConfig]:
        for provider_key, provider_config in self.config.items():
            try:
                match ProviderType(provider_key):
                    case ProviderType.OPENAI:
                        yield OpenAIConfig.from_yaml(provider_config)
                    case ProviderType.BEDROCK:
                        yield BedrockConfig.from_yaml(provider_config)
                    case ProviderType.VERTEX:
                        yield VertexConfig.from_yaml(provider_config)
            except (ValueError, KeyError):
                _logger.debug("provider_skipped", provider=provider_key)
