import structlog

from bulldogent.messaging.platform.config import PlatformConfigGenerator
from bulldogent.messaging.platform.factory import PlatformFactory
from bulldogent.messaging.platform.platform import AbstractPlatform
from bulldogent.messaging.platform.types import PlatformType

_logger = structlog.get_logger()


class PlatformRegistry:
    def __init__(self) -> None:
        self.platforms: dict[PlatformType, AbstractPlatform] = {}
        self._build()

    def get(self, platform_type: PlatformType) -> AbstractPlatform:
        if platform_type not in self.platforms:
            raise ValueError("platform not found", platform_type)
        return self.platforms[platform_type]

    def get_all(self) -> list[AbstractPlatform]:
        return list(self.platforms.values())

    def _build(self) -> None:
        for platform_config in PlatformConfigGenerator().generate():
            try:
                platform = PlatformFactory().from_config(platform_config)
                self._register_platform(platform.identify(), platform)
            except (ValueError, ConnectionError, TimeoutError) as e:
                _logger.error(
                    "platform_registration_failed",
                    error=str(e),
                )

        if not self.platforms:
            raise ValueError("no_platform_registered")
        _logger.info("registry_initialized", platform_count=len(self.platforms))

    def _register_platform(
        self,
        identifier: PlatformType,
        platform: AbstractPlatform,
    ) -> None:
        self.platforms[identifier] = platform
        _logger.info("platform_registered", identifier=identifier.value)


_platform_registry: PlatformRegistry | None = None


def get_platform_registry() -> PlatformRegistry:
    global _platform_registry
    if _platform_registry is None:
        _platform_registry = PlatformRegistry()
    return _platform_registry
