import asyncio
import threading
from collections.abc import Callable
from typing import Any

import discord
import structlog

from slackbot.messaging.platform.config import DiscordConfig
from slackbot.messaging.platform.platform import AbstractMessagingPlatform
from slackbot.messaging.platform.types import PlatformMessage, PlatformType, PlatformUser

_logger = structlog.get_logger()


class DiscordPlatform(AbstractMessagingPlatform):
    """Discord messaging platform adapter.

    discord.py is async-only, so we run its event loop on a background thread
    and use run_coroutine_threadsafe() for sync calls from the main thread.
    """

    config: DiscordConfig

    def __init__(self, config: DiscordConfig) -> None:
        super().__init__(config)
        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        self._message_handler: Callable[[PlatformMessage], None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()

    def identify(self) -> PlatformType:
        return PlatformType.DISCORD

    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> str:
        if not self._ready.wait(timeout=10.0) or not self._loop:
            _logger.error("discord_not_started")
            return ""

        async def _send() -> str:
            target_id = int(thread_id) if thread_id else int(channel_id)
            channel = self._client.get_channel(target_id)
            if not channel:
                channel = await self._client.fetch_channel(target_id)

            if not isinstance(channel, discord.abc.Messageable):
                _logger.error("discord_channel_not_messageable", channel_id=channel_id)
                return ""

            msg = await channel.send(text)
            return str(msg.id)

        future = asyncio.run_coroutine_threadsafe(_send(), self._loop)
        return future.result(timeout=10.0)

    def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        if not self._ready.wait(timeout=10.0) or not self._loop:
            _logger.error("discord_not_started")
            return

        async def _react() -> None:
            channel = self._client.get_channel(int(channel_id))
            if not channel:
                channel = await self._client.fetch_channel(int(channel_id))

            if not isinstance(channel, discord.abc.Messageable):
                return

            message = await channel.fetch_message(int(message_id))
            await message.add_reaction(emoji)

        future = asyncio.run_coroutine_threadsafe(_react(), self._loop)
        future.result(timeout=10.0)

    def on_message(self, handler: Callable[[PlatformMessage], None]) -> None:
        self._message_handler = handler

        @self._client.event
        async def on_ready() -> None:
            _logger.info("discord_client_ready", user=str(self._client.user))
            self._ready.set()

        @self._client.event
        async def on_message(message: discord.Message) -> None:
            if message.author == self._client.user:
                return

            if self._client.user and self._client.user not in message.mentions:
                return

            if not self._message_handler:
                return

            platform_message = self._to_platform_message(message)
            self._message_handler(platform_message)

    def start(self) -> None:
        _logger.info("discord_platform_starting")

        def _thread_target() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._client.start(self.config.bot_token))

        thread = threading.Thread(target=_thread_target, daemon=True)
        thread.start()
        self._ready.wait()
        _logger.info("discord_platform_started")

    def _to_platform_message(self, message: discord.Message) -> PlatformMessage:
        raw: dict[str, Any] = {
            "id": message.id,
            "channel_id": message.channel.id,
            "author_id": message.author.id,
            "content": message.content,
        }

        thread_id: str | None = None
        if isinstance(message.channel, discord.Thread):
            thread_id = str(message.channel.id)

        return PlatformMessage(
            id=str(message.id),
            channel_id=str(message.channel.id),
            text=message.content,
            user=PlatformUser(
                user_id=str(message.author.id),
                name=message.author.display_name,
                raw=raw,
            ),
            timestamp=message.created_at.timestamp(),
            thread_id=thread_id,
            raw=raw,
        )
