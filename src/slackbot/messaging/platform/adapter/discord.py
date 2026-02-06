from collections.abc import Callable

from slackbot.messaging.platform.config import DiscordConfig
from slackbot.messaging.platform.platform import AbstractMessagingPlatform
from slackbot.messaging.platform.types import PlatformMessage, PlatformType


class DiscordPlatform(AbstractMessagingPlatform):
    def __init__(self, config: DiscordConfig) -> None:
        super().__init__(config)

    def identify(self) -> PlatformType:
        return PlatformType.DISCORD

    def send_message(self, channel_id: str, text: str, thread_id: str | None = None) -> str:
        raise NotImplementedError("Discord platform not yet implemented")

    def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> None:
        raise NotImplementedError("Discord platform not yet implemented")

    def on_message(self, handler: Callable[[PlatformMessage], None]) -> None:
        raise NotImplementedError("Discord platform not yet implemented")

    def start(self) -> None:
        raise NotImplementedError("Discord platform not yet implemented")
