from collections.abc import Callable

from slackbot.messaging.platform.config import TeamsConfig
from slackbot.messaging.platform.platform import AbstractMessagingPlatform
from slackbot.messaging.platform.types import PlatformMessage, PlatformType


class TeamsPlatform(AbstractMessagingPlatform):
    def __init__(self, config: TeamsConfig) -> None:
        super().__init__(config)

    def identify(self) -> PlatformType:
        return PlatformType.TEAMS

    def send_message(self, channel_id: str, text: str, thread_id: str | None = None) -> str:
        raise NotImplementedError("Teams platform not yet implemented")

    def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> None:
        raise NotImplementedError("Teams platform not yet implemented")

    def on_message(self, handler: Callable[[PlatformMessage], None]) -> None:
        raise NotImplementedError("Teams platform not yet implemented")

    def start(self) -> None:
        raise NotImplementedError("Teams platform not yet implemented")
