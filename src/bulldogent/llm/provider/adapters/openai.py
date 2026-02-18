import json
from typing import Any

import structlog
from openai import OpenAI

from bulldogent.llm.provider.config import OpenAIConfig
from bulldogent.llm.provider.provider import AbstractProvider
from bulldogent.llm.provider.types import (
    AssistantToolCallMessage,
    ConversationMessage,
    Message,
    ProviderResponse,
    ProviderType,
    TextResponse,
    TokenUsage,
    ToolUseResponse,
)
from bulldogent.llm.tool.types import ToolOperation, ToolOperationCall

_logger = structlog.get_logger()


def _message_to_provider_format(message: ConversationMessage) -> list[dict[str, Any]]:
    """Convert ConversationMessage to OpenAI API format.

    Returns a list because ToolResultMessage produces one message per result.
    """
    if isinstance(message, Message):
        return [{"role": message.role, "content": message.content}]

    if isinstance(message, AssistantToolCallMessage):
        return [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.input),
                        },
                    }
                    for call in message.tool_operation_calls
                ],
            }
        ]

    # ToolResultMessage — OpenAI needs one message per tool result
    return [
        {
            "role": "tool",
            "tool_call_id": result.tool_operation_call_id,
            "content": result.content,
        }
        for result in message.tool_operation_results
    ]


def _tool_operation_to_provider_format(operation: ToolOperation) -> dict[str, Any]:
    """Convert Operation to OpenAI tool format."""
    return {
        "type": "function",
        "function": {
            "name": operation.name,
            "description": operation.description,
            "parameters": operation.input_schema,
        },
    }


class OpenAIProvider(AbstractProvider):
    """OpenAI LLM provider implementation."""

    config: OpenAIConfig

    def __init__(self, config: OpenAIConfig) -> None:
        super().__init__(config)
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_url,
        )

    def identify(self) -> ProviderType:
        return ProviderType.OPENAI

    def complete(
        self,
        messages: list[ConversationMessage],
        operations: list[ToolOperation] | None = None,
    ) -> ProviderResponse:
        """Send messages to OpenAI and get response."""
        _logger.info(
            "openai_request_starting", model=self.config.model, message_count=len(messages)
        )
        openai_messages: list[dict[str, Any]] = []
        for msg in messages:
            openai_messages.extend(_message_to_provider_format(msg))
        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": openai_messages,
            "max_completion_tokens": self.config.max_tokens,
        }

        if self.config.temperature is not None:
            params["temperature"] = self.config.temperature

        if operations:
            params["tools"] = [_tool_operation_to_provider_format(op) for op in operations]

        response = self.client.chat.completions.create(**params)
        choice = response.choices[0]
        finish_reason = choice.finish_reason

        usage = TokenUsage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        if finish_reason == "tool_calls" and choice.message.tool_calls:
            operation_calls = [
                ToolOperationCall(
                    id=tc.id,
                    name=tc.function.name,
                    input=json.loads(tc.function.arguments),
                )
                for tc in choice.message.tool_calls
            ]

            _logger.info(
                "openai_response_finished",
                reason=finish_reason,
                tool_operation_calls_count=len(operation_calls),
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )

            return ToolUseResponse(tool_operation_calls=operation_calls, usage=usage)

        _logger.info(
            "openai_response_finished",
            reason=finish_reason,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return TextResponse(content=choice.message.content or "", usage=usage)
