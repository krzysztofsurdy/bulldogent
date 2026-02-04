from typing import Protocol

from slackbot.llm.types import LLMResponse, Message, Tool


class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
    ) -> LLMResponse:
        """
        Send a message to the LLM server and return a LLMResponse object.

        Args:
            messages: Conversation history
            tools: Available tools the LLM can call (optional)

        Returns:
            LLMResponse with either content or tool_calls
        """
        ...
