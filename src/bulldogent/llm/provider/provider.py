from abc import ABC, abstractmethod

from bulldogent.llm.provider.config import AbstractProviderConfig
from bulldogent.llm.provider.types import Message, ProviderResponse, ProviderType
from bulldogent.llm.tool.types import ToolOperation


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
        operations: list[ToolOperation] | None = None,
    ) -> ProviderResponse:
        """
        Send a message to the LLM server and return a ProviderResponse object.

        Args:
            messages: Conversation history
            operations: Available tools the LLM can call (optional)

        Returns:
            ProviderResponse with either content or tool_calls
        """
        ...
