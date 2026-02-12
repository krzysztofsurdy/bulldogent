import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import structlog

from bulldogent.messaging.platform.types import PlatformType
from bulldogent.util import PROJECT_ROOT, load_yaml_config

_logger = structlog.get_logger()
_DEFAULT_CONFIG = PROJECT_ROOT / "config" / "messaging_platform.yaml"


class _ConfigDict(TypedDict):
    llm_provider: str
    reaction_acknowledged: str
    reaction_handled: str
    reaction_error: str


@dataclass
class AbstractPlatformConfig(ABC):
    llm_provider: str
    reaction_acknowledged: str
    reaction_handled: str
    reaction_error: str

    @classmethod
    def _read_common_config(cls, yaml_config: dict[str, Any]) -> _ConfigDict:
        """
        Helper: Read common fields from environment variables.

        Returns dict that can be unpacked with ** into subclass constructors.
        """
        return _ConfigDict(
            llm_provider=os.getenv(yaml_config["llm_provider_env"], ""),
            reaction_acknowledged=yaml_config.get("reaction_acknowledged", ""),
            reaction_handled=yaml_config.get("reaction_handled", ""),
            reaction_error=yaml_config.get("reaction_error", ""),
        )

    @classmethod
    @abstractmethod
    def from_envs(cls, envs: dict[str, Any]) -> "AbstractPlatformConfig":
        """Factory method: Create config from YAML + environment variables"""
        ...


@dataclass
class SlackConfig(AbstractPlatformConfig):
    bot_token: str
    app_token: str

    @classmethod
    def from_envs(cls, envs: dict[str, Any]) -> "SlackConfig":
        common = cls._read_common_config(envs)

        bot_token = os.getenv(envs["bot_token_env"])
        if not bot_token:
            raise ValueError(f"Missing env var: {envs['bot_token_env']}")

        app_token = os.getenv(envs["app_token_env"])
        if not app_token:
            raise ValueError(f"Missing env var: {envs['app_token_env']}")

        return cls(
            bot_token=bot_token,
            app_token=app_token,
            **common,
        )


@dataclass
class TeamsConfig(AbstractPlatformConfig):
    app_id: str
    app_password: str

    @classmethod
    def from_envs(cls, envs: dict[str, Any]) -> "TeamsConfig":
        common = cls._read_common_config(envs)

        app_id = os.getenv(envs["app_id_env"])
        if not app_id:
            raise ValueError(f"Missing env var: {envs['app_id_env']}")

        app_password = os.getenv(envs["app_password_env"])
        if not app_password:
            raise ValueError(f"Missing env var: {envs['app_password_env']}")

        return cls(
            app_id=app_id,
            app_password=app_password,
            **common,
        )


@dataclass
class DiscordConfig(AbstractPlatformConfig):
    bot_token: str

    @classmethod
    def from_envs(cls, envs: dict[str, Any]) -> "DiscordConfig":
        common = cls._read_common_config(envs)

        bot_token = os.getenv(envs["bot_token_env"])
        if not bot_token:
            raise ValueError(f"Missing env var: {envs['bot_token_env']}")

        return cls(
            bot_token=bot_token,
            **common,
        )


@dataclass
class TelegramConfig(AbstractPlatformConfig):
    bot_token: str

    @classmethod
    def from_envs(cls, envs: dict[str, Any]) -> "TelegramConfig":
        common = cls._read_common_config(envs)

        bot_token = os.getenv(envs["bot_token_env"])
        if not bot_token:
            raise ValueError(f"Missing env var: {envs['bot_token_env']}")

        return cls(
            bot_token=bot_token,
            **common,
        )


class PlatformConfigGenerator:
    def __init__(self, config_location: Path = _DEFAULT_CONFIG) -> None:
        self.config = load_yaml_config(config_location)

    def generate(self) -> Iterator[AbstractPlatformConfig]:
        for platform_key, platform_config in self.config.items():
            try:
                match PlatformType(platform_key):
                    case PlatformType.SLACK:
                        yield SlackConfig.from_envs(platform_config)
                    case PlatformType.TEAMS:
                        yield TeamsConfig.from_envs(platform_config)
                    case PlatformType.DISCORD:
                        yield DiscordConfig.from_envs(platform_config)
                    case PlatformType.TELEGRAM:
                        yield TelegramConfig.from_envs(platform_config)
            except (ValueError, KeyError):
                _logger.debug("platform_skipped", platform=platform_key)
