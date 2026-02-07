import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

from slackbot.llm.provider import ProviderType
from slackbot.util import load_yaml_config

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "messaging_platform.yaml"


class _CommonConfig(TypedDict):
    enabled: bool
    model: str
    temperature: float
    max_tokens: int


@dataclass
class AbstractProviderConfig(ABC):
    enabled: bool
    model: str
    temperature: float
    max_tokens: int

    @classmethod
    def _read_common_config(cls, yaml_config: dict[str, Any]) -> _CommonConfig:
        """
        Helper: Read common fields from environment variables.

        Returns dict that can be unpacked with ** into subclass constructors.
        """
        return _CommonConfig(
            enabled=os.getenv(yaml_config["enabled_env"], "false").lower() == "true",
            model=os.getenv(yaml_config["model_env"], ""),
            temperature=float(os.getenv(yaml_config["temperature_env"], "0.7")),
            max_tokens=int(os.getenv(yaml_config["max_tokens_env"], "2000")),
        )

    @classmethod
    @abstractmethod
    def from_envs(cls, envs: dict[str, Any]) -> "AbstractProviderConfig":
        """Factory method: Create config from YAML + environment variables"""
        ...


@dataclass
class OpenAIConfig(AbstractProviderConfig):
    api_key: str

    @classmethod
    def from_envs(cls, envs: dict[str, Any]) -> "OpenAIConfig":
        common = cls._read_common_config(envs)

        api_key = os.getenv(envs["api_key_env"])
        if not api_key:
            raise ValueError(f"Missing env var: {envs['api_key_env']}")

        return cls(api_key=api_key, **common)


@dataclass
class BedrockConfig(AbstractProviderConfig):
    region: str
    anthropic_version: str

    @classmethod
    def from_envs(cls, envs: dict[str, Any]) -> "BedrockConfig":
        common = cls._read_common_config(envs)

        region = os.getenv(envs["region_env"])
        if not region:
            raise ValueError(f"Missing env var: {envs['region_env']}")

        anthropic_version = os.getenv(envs["anthropic_version_env"])
        if not anthropic_version:
            raise ValueError(f"Missing env var: {envs['anthropic_version_env']}")

        return cls(region=region, anthropic_version=anthropic_version, **common)


@dataclass
class VertexConfig(AbstractProviderConfig):
    project_id: str
    location: str

    @classmethod
    def from_envs(cls, envs: dict[str, Any]) -> "VertexConfig":
        common = cls._read_common_config(envs)

        project_id = os.getenv(envs["project_id_env"])
        if not project_id:
            raise ValueError(f"Missing env var: {envs['project_id_env']}")

        location = os.getenv(envs["location_env"])
        if not location:
            raise ValueError(f"Missing env var: {envs['location_env']}")

        return cls(project_id=project_id, location=location, **common)


class ProviderConfigGenerator:
    def __init__(self, config_location: Path = _DEFAULT_CONFIG) -> None:
        self.config = load_yaml_config(config_location)

    def generate(self) -> Iterator[AbstractProviderConfig]:
        for provider_key, provider_config in self.config.items():
            match ProviderType(provider_key):
                case ProviderType.OPENAI:
                    yield OpenAIConfig.from_envs(provider_config)
                case ProviderType.BEDROCK:
                    yield BedrockConfig.from_envs(provider_config)
                case ProviderType.VERTEX:
                    yield VertexConfig.from_envs(provider_config)
