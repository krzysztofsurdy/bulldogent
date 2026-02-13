import asyncio
import threading
from collections.abc import Callable

import structlog
from aiohttp import web
from botbuilder.core import (  # type: ignore[import-untyped]
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.core.teams import TeamsActivityHandler  # type: ignore[import-untyped]
from botbuilder.schema import Activity  # type: ignore[import-untyped]

from bulldogent.messaging.platform.config import TeamsConfig
from bulldogent.messaging.platform.platform import AbstractPlatform
from bulldogent.messaging.platform.types import (
    PlatformMessage,
    PlatformReaction,
    PlatformType,
    PlatformUser,
)

_logger = structlog.get_logger()


class _TeamsBot(TeamsActivityHandler):  # type: ignore[misc]
    """Internal Teams activity handler that bridges to our platform handler."""

    def __init__(self, message_handler: Callable[[PlatformMessage], None] | None = None) -> None:
        super().__init__()
        self._message_handler = message_handler

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        if not self._message_handler:
            return

        TurnContext.remove_recipient_mention(turn_context.activity)
        activity = turn_context.activity

        platform_message = PlatformMessage(
            id=activity.id or "",
            channel_id=activity.conversation.id if activity.conversation else "",
            text=(activity.text or "").strip(),
            user=PlatformUser(
                user_id=activity.from_property.id if activity.from_property else "",
                name=activity.from_property.name if activity.from_property else "",
                raw={"activity": activity.as_dict()},
            ),
            timestamp=activity.timestamp.timestamp() if activity.timestamp else 0.0,
            thread_id=activity.reply_to_id,
            raw=activity.as_dict(),
        )

        self._message_handler(platform_message)


class TeamsPlatform(AbstractPlatform):
    """Microsoft Teams messaging platform adapter.

    Teams uses HTTP webhooks (not WebSocket like Slack).
    Runs an aiohttp server on a background thread to stay sync-compatible.
    """

    config: TeamsConfig

    def __init__(self, config: TeamsConfig) -> None:
        super().__init__(config)
        self._message_handler: Callable[[PlatformMessage], None] | None = None
        self._adapter = BotFrameworkAdapter(
            BotFrameworkAdapterSettings(
                app_id=config.app_id,
                app_password=config.app_password,
            )
        )
        self._bot = _TeamsBot()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()

    def identify(self) -> PlatformType:
        return PlatformType.TEAMS

    def get_bot_user_id(self) -> str:
        return self.config.app_id

    def get_thread_messages(
        self,
        channel_id: str,
        thread_id: str,
    ) -> list[PlatformMessage]:
        """Fetch thread history from Teams.

        Bot Framework SDK does not expose thread history directly.
        Would require Microsoft Graph API (separate auth flow).
        Returns empty list — the bot will only see the current message.
        """
        _logger.info(
            "teams_thread_history_not_available",
            msg="Bot Framework SDK does not support fetching thread history. "
            "Requires Microsoft Graph API integration.",
        )
        return []

    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> str:
        _logger.warning("teams_send_message_not_implemented")
        return ""

    def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        _logger.debug(
            "teams_reactions_not_supported",
            msg="Teams Bot Framework does not support adding reactions programmatically",
        )

    def on_message(self, handler: Callable[[PlatformMessage], None]) -> None:
        self._message_handler = handler
        self._bot._message_handler = handler

    def on_reaction(self, handler: Callable[[PlatformReaction], None]) -> None:
        _logger.debug(
            "teams_reactions_not_supported",
            msg="Teams Bot Framework does not support listening for reactions",
        )

    def start(self) -> None:
        _logger.info("teams_platform_starting", port=3978)

        async def handle_messages(req: web.Request) -> web.Response:
            body = await req.json()
            activity = Activity().deserialize(body)
            auth_header = req.headers.get("Authorization", "")
            await self._adapter.process_activity(activity, auth_header, self._bot.on_turn)
            return web.Response(status=201)

        async def _run_server() -> None:
            app = web.Application()
            app.router.add_post("/api/messages", handle_messages)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", 3978)
            await site.start()
            await asyncio.Event().wait()

        def _thread_target() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._ready.set()
            self._loop.run_until_complete(_run_server())

        thread = threading.Thread(target=_thread_target, daemon=True)
        thread.start()
        self._ready.wait()
        _logger.info("teams_platform_started")
