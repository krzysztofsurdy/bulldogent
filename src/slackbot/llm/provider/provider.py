from abc import ABC, abstractmethod

from slackbot.llm.provider import BedrockConfig, OpenAIConfig, ProviderType, VertexConfig
from slackbot.llm.provider.adapters import BedrockProvider, OpenAIProvider, VertexProvider
from slackbot.llm.provider.config import AbstractProviderConfig
from slackbot.llm.provider.types import Message, ProviderResponse
from slackbot.llm.tool.types import ToolOperation


class AbstractProvider(ABC):
    def __init__(self, config: AbstractProviderConfig) -> None:
        self.config = config
        self.enabled = config.enabled

    @abstractmethod
    def identify(self) -> ProviderType: ...

    @abstractmethod
    def complete(
        self,
        messages: list[Message],
        tools: list[ToolOperation] | None = None,
    ) -> ProviderResponse:
        """
        Send a message to the LLM server and return a ProviderResponse object.

        Args:
            messages: Conversation history
            tools: Available tools the LLM can call (optional)

        Returns:
            ProviderResponse with either content or tool_calls
        """
        ...


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
