import structlog

from bulldogent.llm.provider.config import ProviderConfigGenerator
from bulldogent.llm.provider.factory import ProviderFactory
from bulldogent.llm.provider.provider import AbstractProvider
from bulldogent.llm.provider.types import ProviderType

_logger = structlog.get_logger()


class ProviderRegistry:
    def __init__(self) -> None:
        self.providers: dict[ProviderType, AbstractProvider] = {}
        self._build()

    def get(self, provider_type: ProviderType) -> AbstractProvider:
        if provider_type not in self.providers:
            raise ValueError("provider not found", provider_type)
        return self.providers[provider_type]

    def _build(self) -> None:
        for provider_config in ProviderConfigGenerator().generate():
            if not provider_config.enabled:
                continue

            try:
                provider = ProviderFactory().from_config(provider_config)
                self._register_provider(provider.identify(), provider)
            except (ValueError, ConnectionError, TimeoutError) as e:
                _logger.error(
                    "provider_registration_failed",
                    error=str(e),
                )

        if not self.providers:
            raise ValueError("no_provider_registered")
        _logger.info("registry_initialized", provider_count=len(self.providers))

    def _register_provider(self, identifier: ProviderType, provider: AbstractProvider) -> None:
        self.providers[identifier] = provider
        _logger.info("provider_registered", identifier=identifier.value)


_provider_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _provider_registry
    if _provider_registry is None:
        _provider_registry = ProviderRegistry()
    return _provider_registry
