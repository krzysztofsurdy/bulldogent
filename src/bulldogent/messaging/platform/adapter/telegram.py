import threading
from collections.abc import Callable
from typing import Any

import structlog
import telebot

from bulldogent.messaging.platform.config import TelegramConfig
from bulldogent.messaging.platform.platform import AbstractPlatform
from bulldogent.messaging.platform.types import (
    PlatformMessage,
    PlatformReaction,
    PlatformType,
    PlatformUser,
)

_logger = structlog.get_logger()


class TelegramPlatform(AbstractPlatform):
    """Telegram messaging platform adapter.

    Uses pyTelegramBotAPI which is natively synchronous (no async wrappers needed).
    """

    config: TelegramConfig

    def __init__(self, config: TelegramConfig) -> None:
        super().__init__(config)
        self._bot = telebot.TeleBot(config.bot_token)
        self._message_handler: Callable[[PlatformMessage], None] | None = None
        self._bot_username: str = ""
        self._bot_user_id: str = ""

    def identify(self) -> PlatformType:
        return PlatformType.TELEGRAM

    def get_bot_user_id(self) -> str:
        return self._bot_user_id

    def get_thread_messages(
        self,
        channel_id: str,
        thread_id: str,
    ) -> list[PlatformMessage]:
        """Fetch thread history from Telegram.

        Telegram Bot API does not provide an endpoint to fetch all replies
        to a message. Threads (reply_to_message_id) are a client-side concept
        with no server-side query support.
        Returns empty list — the bot will only see the current message.
        """
        _logger.info(
            "telegram_thread_history_not_available",
            msg="Telegram Bot API does not support fetching thread replies.",
        )
        return []

    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> str:
        _logger.debug("telegram_sending_message", channel_id=channel_id, thread_id=thread_id)
        try:
            result = self._bot.send_message(
                chat_id=int(channel_id),
                text=text,
                message_thread_id=int(thread_id) if thread_id else None,
            )
            return str(result.message_id)
        except Exception:
            _logger.exception("telegram_send_message_failed", channel_id=channel_id)
            return ""

    def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        try:
            reaction = telebot.types.ReactionTypeEmoji(emoji=emoji)
            self._bot.set_message_reaction(
                chat_id=int(channel_id),
                message_id=int(message_id),
                reaction=[reaction],
            )
        except Exception:
            _logger.exception("telegram_add_reaction_failed", channel_id=channel_id, emoji=emoji)

    def on_message(self, handler: Callable[[PlatformMessage], None]) -> None:
        self._message_handler = handler

        @self._bot.message_handler(func=self._is_bot_mentioned)  # type: ignore[untyped-decorator]
        def handle_mention(message: Any) -> None:
            if self._message_handler:
                platform_message = self._to_platform_message(message)
                self._message_handler(platform_message)

    def on_reaction(self, handler: Callable[[PlatformReaction], None]) -> None:
        _logger.debug(
            "telegram_reaction_listening_not_supported",
            msg="Telegram Bot API does not support listening for reactions",
        )

    def start(self) -> None:
        _logger.info("telegram_platform_starting")

        bot_info = self._bot.get_me()
        self._bot_username = bot_info.username or ""
        self._bot_user_id = str(bot_info.id)
        _logger.info(
            "telegram_bot_identified",
            username=self._bot_username,
            bot_user_id=self._bot_user_id,
        )

        thread = threading.Thread(
            target=self._bot.infinity_polling,
            daemon=True,
        )
        thread.start()
        _logger.info("telegram_platform_started")

    def _is_bot_mentioned(self, message: Any) -> bool:
        if not message.entities:
            return False

        for entity in message.entities:
            if entity.type == "mention" and message.text:
                mention = message.text[entity.offset : entity.offset + entity.length]
                if mention == f"@{self._bot_username}":
                    return True
        return False

    def _to_platform_message(self, message: Any) -> PlatformMessage:
        raw: dict[str, Any] = {
            "message_id": message.message_id,
            "chat_id": message.chat.id,
            "from_user_id": message.from_user.id if message.from_user else None,
        }

        return PlatformMessage(
            id=str(message.message_id),
            channel_id=str(message.chat.id),
            text=message.text or "",
            user=PlatformUser(
                user_id=str(message.from_user.id) if message.from_user else "",
                name=message.from_user.username or "" if message.from_user else "",
                raw=raw,
            ),
            timestamp=float(message.date) if message.date else 0.0,
            thread_id=str(message.message_thread_id) if message.message_thread_id else None,
            raw=raw,
        )
