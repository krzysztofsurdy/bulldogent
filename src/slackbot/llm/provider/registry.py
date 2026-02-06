import structlog

from slackbot.llm.provider.config import ProviderConfigGenerator
from slackbot.llm.provider.provider import AbstractProvider, ProviderFactory
from slackbot.llm.provider.types import ProviderType

_logger = structlog.get_logger()
_provider_registry: "ProviderRegistry | None" = None


class ProviderRegistry:
    def __init__(self) -> None:
        self.providers: dict[ProviderType, AbstractProvider] = {}
        if _provider_registry is None:
            self._build()

    def get(self, provider_type: ProviderType) -> AbstractProvider:
        if provider_type not in self.providers:
            raise ValueError("provider not found", provider_type)
        return self.providers[provider_type]

    def _build(self) -> None:
        global _provider_registry
        _provider_registry = self

        for provider_config in ProviderConfigGenerator().all():
            if not provider_config.enabled:
                continue

            try:
                provider = ProviderFactory().from_config(provider_config)
                _provider_registry._register_provider(provider.identify(), provider)
            except Exception as e:
                _logger.error(
                    "provider_registration_failed",
                    error=str(e),
                )

        if not _provider_registry.providers:
            raise ValueError("no_provider_registered")
        _logger.info("registry_initialized", provider_count=len(_provider_registry.providers))

    def _register_provider(self, identifier: ProviderType, provider: AbstractProvider) -> None:
        self.providers[identifier] = provider
        _logger.info("provider_registered", identifier=identifier.value)
