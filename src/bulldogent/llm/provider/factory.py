from bulldogent.llm.provider import BedrockConfig, OpenAIConfig, VertexConfig
from bulldogent.llm.provider.adapters import BedrockProvider, OpenAIProvider, VertexProvider
from bulldogent.llm.provider.config import AbstractProviderConfig
from bulldogent.llm.provider.provider import AbstractProvider


class ProviderFactory:
    def from_config(self, config: AbstractProviderConfig) -> AbstractProvider:
        match config:
            case OpenAIConfig():
                return OpenAIProvider(config)
            case BedrockConfig():
                return BedrockProvider(config)
            case VertexConfig():
                return VertexProvider(config)
            case _:
                raise ValueError(f"Unknown provider config class: {config}")
