from collections.abc import Callable
from typing import Any

import structlog
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from slackbot.messaging.platform.config import SlackConfig
from slackbot.messaging.platform.platform import AbstractMessagingPlatform
from slackbot.messaging.platform.types import PlatformMessage, PlatformType, PlatformUser

_logger = structlog.get_logger()


class SlackPlatform(AbstractMessagingPlatform):
    config: SlackConfig

    def __init__(self, config: SlackConfig) -> None:
        super().__init__(config)
        self.app = App(token=config.bot_token)
        self._message_handler: Callable[[PlatformMessage], None] | None = None

    def identify(self) -> PlatformType:
        return PlatformType.SLACK

    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> str:
        response = self.app.client.chat_postMessage(
            channel=channel_id,
            text=text,
            thread_ts=thread_id,
        )
        return str(response["ts"])

    def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        self.app.client.reactions_add(
            channel=channel_id,
            timestamp=message_id,
            name=emoji,
        )

    def on_message(self, handler: Callable[[PlatformMessage], None]) -> None:
        self._message_handler = handler

        @self.app.event("app_mention")
        def handle_mention(event: dict[str, Any], say: Any, client: Any) -> None:
            if self._message_handler:
                platform_message = self._event_to_platform_message(event)
                self._message_handler(platform_message)

    def start(self) -> None:
        _logger.info("slack_platform_starting")
        handler = SocketModeHandler(self.app, self.config.app_token)
        handler.connect()  # type: ignore[no-untyped-call]
        _logger.info("slack_platform_started")

    def _event_to_platform_message(self, event: dict[str, Any]) -> PlatformMessage:
        return PlatformMessage(
            id=event["ts"],
            channel_id=event["channel"],
            text=event.get("text", ""),
            user=PlatformUser(
                user_id=event.get("user", ""),
                name="",
                raw=event,
            ),
            timestamp=float(event["ts"]),
            thread_id=event.get("thread_ts"),
            raw=event,
        )
