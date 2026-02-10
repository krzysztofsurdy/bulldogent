import signal
import threading

import structlog

from bulldogent.bot import Bot
from bulldogent.llm.provider import ProviderType
from bulldogent.llm.provider.registry import get_provider_registry
from bulldogent.messaging.platform.registry import get_platform_registry

_logger = structlog.get_logger()


def main() -> None:
    platform_registry = get_platform_registry()
    provider_registry = get_provider_registry()

    for platform in platform_registry.get_all():
        platform_name = platform.identify().value
        provider_type = ProviderType(platform.config.llm_provider)
        _logger.info("wiring_bot", platform=platform_name, provider=provider_type.value)

        provider = provider_registry.get(provider_type)
        bot = Bot(
            platform=platform,
            platform_config=platform.config,
            provider=provider,
        )
        platform.on_message(bot.handle)
        platform.start()

    _logger.info("all_platforms_started")

    shutdown = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: shutdown.set())
    signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
    shutdown.wait()


if __name__ == "__main__":
    main()
