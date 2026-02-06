from abc import ABC, abstractmethod
from collections.abc import Callable

from slackbot.messaging.platform.adapter import (
    DiscordPlatform,
    SlackPlatform,
    TeamsPlatform,
    TelegramPlatform,
)
from slackbot.messaging.platform.config import (
    AbstractPlatformConfig,
    DiscordConfig,
    SlackConfig,
    TeamsConfig,
    TelegramConfig,
)
from slackbot.messaging.platform.types import PlatformMessage, PlatformType


class AbstractMessagingPlatform(ABC):
    def __init__(self, config: AbstractPlatformConfig) -> None:
        self.config = config

    @abstractmethod
    def identify(self) -> PlatformType: ...

    @abstractmethod
    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> str:
        """
        Send a message to a channel (optionally in a thread).

        Returns:
            message_id of the sent message
        """
        ...

    @abstractmethod
    def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        """Add an emoji reaction to a message"""
        ...

    @abstractmethod
    def on_message(self, handler: Callable[[PlatformMessage], None]) -> None:
        """
        Register a handler function to be called for each incoming message.

        Args:
            handler: Function that takes a PlatformMessage
        """
        ...

    @abstractmethod
    def start(self) -> None:
        """Start listening for events and calling registered handlers"""
        ...


class PlatformFactory:
    def from_config(self, config: AbstractPlatformConfig) -> AbstractMessagingPlatform:
        match config:
            case SlackConfig():
                return SlackPlatform(config)
            case TeamsConfig():
                return TeamsPlatform(config)
            case DiscordConfig():
                return DiscordPlatform(config)
            case TelegramConfig():
                return TelegramPlatform(config)
            case _:
                raise ValueError(f"Unknown platform config class: {config}")
