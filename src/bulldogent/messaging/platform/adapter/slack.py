from collections.abc import Callable
from typing import Any

import structlog
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError

from bulldogent.messaging.platform.config import SlackConfig
from bulldogent.messaging.platform.platform import AbstractPlatform
from bulldogent.messaging.platform.types import (
    PlatformMessage,
    PlatformReaction,
    PlatformType,
    PlatformUser,
)

_logger = structlog.get_logger()


class SlackPlatform(AbstractPlatform):
    config: SlackConfig

    def __init__(self, config: SlackConfig) -> None:
        super().__init__(config)
        self.app = App(token=config.bot_token)
        self._message_handler: Callable[[PlatformMessage], None] | None = None
        self._reaction_handler: Callable[[PlatformReaction], None] | None = None
        self._bot_user_id: str = ""

    def identify(self) -> PlatformType:
        return PlatformType.SLACK

    def get_bot_user_id(self) -> str:
        return self._bot_user_id

    def get_thread_messages(
        self,
        channel_id: str,
        thread_id: str,
    ) -> list[PlatformMessage]:
        try:
            response = self.app.client.conversations_replies(
                channel=channel_id,
                ts=thread_id,
            )
            messages: list[dict[str, Any]] = response.get("messages", [])
            return [self._event_to_platform_message(msg, channel_id=channel_id) for msg in messages]
        except Exception:
            _logger.exception(
                "slack_get_thread_messages_failed",
                channel_id=channel_id,
                thread_id=thread_id,
            )
            return []

    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> str:
        _logger.debug("slack_sending_message", channel_id=channel_id, thread_id=thread_id)
        try:
            response = self.app.client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_id,
            )
            return str(response["ts"])
        except Exception:
            _logger.exception("slack_send_message_failed", channel_id=channel_id)
            return ""

    def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        try:
            self.app.client.reactions_add(
                channel=channel_id,
                timestamp=message_id,
                name=emoji,
            )
        except SlackApiError as e:
            if e.response.get("error") == "already_reacted":
                _logger.debug("slack_reaction_already_exists", channel_id=channel_id, emoji=emoji)
            else:
                _logger.exception("slack_add_reaction_failed", channel_id=channel_id, emoji=emoji)
        except Exception:
            _logger.exception("slack_add_reaction_failed", channel_id=channel_id, emoji=emoji)

    def on_message(self, handler: Callable[[PlatformMessage], None]) -> None:
        self._message_handler = handler

        @self.app.event("app_mention")
        def handle_mention(event: dict[str, Any], say: Any, client: Any) -> None:
            if self._message_handler:
                try:
                    platform_message = self._event_to_platform_message(event)
                    self._message_handler(platform_message)
                except Exception:
                    _logger.exception("slack_handle_mention_failed")

    def on_reaction(self, handler: Callable[[PlatformReaction], None]) -> None:
        self._reaction_handler = handler

        @self.app.event("reaction_added")
        def handle_reaction(event: dict[str, Any]) -> None:
            if self._reaction_handler:
                try:
                    item = event.get("item", {})
                    reaction = PlatformReaction(
                        channel_id=item.get("channel", ""),
                        message_id=item.get("ts", ""),
                        user_id=event.get("user", ""),
                        emoji=event.get("reaction", ""),
                    )
                    self._reaction_handler(reaction)
                except Exception:
                    _logger.exception("slack_handle_reaction_failed")

    def start(self) -> None:
        _logger.info("slack_platform_starting")
        auth_response = self.app.client.auth_test()
        self._bot_user_id = auth_response.get("user_id", "")
        _logger.info("slack_bot_identified", bot_user_id=self._bot_user_id)
        handler = SocketModeHandler(self.app, self.config.app_token)
        handler.connect()  # type: ignore[no-untyped-call]
        _logger.info("slack_platform_started")

    def _event_to_platform_message(
        self,
        event: dict[str, Any],
        channel_id: str | None = None,
    ) -> PlatformMessage:
        user_id = event.get("user", "")

        return PlatformMessage(
            id=event["ts"],
            channel_id=channel_id or event["channel"],
            text=event.get("text", ""),
            user=PlatformUser(
                user_id=user_id,
                name=user_id,
                raw=event,
            ),
            timestamp=float(event["ts"]),
            thread_id=event.get("thread_ts"),
            raw=event,
        )
