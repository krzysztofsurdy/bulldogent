import signal

import structlog

from slackbot.messaging.platform.registry import get_platform_registry
from slackbot.messaging.platform.types import PlatformMessage

_logger = structlog.get_logger()


def main() -> None:
    registry = get_platform_registry()

    def handle_message(message: PlatformMessage) -> None:
        _logger.info("message_received", text=message.text, user=message.user.name)

    for platform in registry.get_all():
        platform.on_message(handle_message)
        platform.start()

    _logger.info("all_platforms_started")
    signal.pause()


if __name__ == "__main__":
    main()
