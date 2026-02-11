from abc import ABC, abstractmethod
from collections.abc import Callable

from bulldogent.messaging.platform.config import AbstractPlatformConfig
from bulldogent.messaging.platform.types import PlatformMessage, PlatformType


class AbstractPlatform(ABC):
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
    def get_bot_user_id(self) -> str:
        """Return the bot's own user ID on this platform.

        Used to distinguish bot messages from user messages
        when building conversation history from threads.
        """
        ...

    @abstractmethod
    def get_thread_messages(
        self,
        channel_id: str,
        thread_id: str,
    ) -> list[PlatformMessage]:
        """Fetch all messages in a thread.

        Returns messages in chronological order (oldest first).
        Used for building conversation context when the bot
        is mentioned inside an existing thread.
        """
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
