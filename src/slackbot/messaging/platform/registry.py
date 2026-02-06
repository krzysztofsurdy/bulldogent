import structlog

from slackbot.messaging.platform.config import PlatformConfigGenerator
from slackbot.messaging.platform.platform import AbstractMessagingPlatform, PlatformFactory
from slackbot.messaging.platform.types import PlatformType

_logger = structlog.get_logger()
_platform_registry: "PlatformRegistry | None" = None


class PlatformRegistry:
    def __init__(self) -> None:
        self.platforms: dict[PlatformType, AbstractMessagingPlatform] = {}
        if _platform_registry is None:
            self._build()

    def get(self, platform_type: PlatformType) -> AbstractMessagingPlatform:
        if platform_type not in self.platforms:
            raise ValueError("platform not found", platform_type)
        return self.platforms[platform_type]

    def get_all(self) -> list[AbstractMessagingPlatform]:
        return list(self.platforms.values())

    def _build(self) -> None:
        global _platform_registry
        _platform_registry = self

        for platform_config in PlatformConfigGenerator().all():
            if not platform_config.enabled:
                continue

            try:
                platform = PlatformFactory().from_config(platform_config)
                _platform_registry._register_platform(
                    platform.identify(),
                    platform,
                )
            except Exception as e:
                _logger.error(
                    "platform_registration_failed",
                    error=str(e),
                )

        if not _platform_registry.platforms:
            raise ValueError("no_platform_registered")
        _logger.info("registry_initialized", platform_count=len(_platform_registry.platforms))

    def _register_platform(
        self,
        identifier: PlatformType,
        platform: AbstractMessagingPlatform,
    ) -> None:
        self.platforms[identifier] = platform
        _logger.info("platform_registered", identifier=identifier.value)
