import json
from typing import Any

import boto3  # type: ignore[import-untyped]
import structlog

from bulldogent.llm.provider.config import BedrockConfig
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
    """Convert ConversationMessage to Bedrock (Anthropic Messages API) format.

    Returns a list for consistency, though Bedrock groups tool results
    into a single message.
    """
    if isinstance(message, Message):
        return [{"role": message.role, "content": message.content}]

    if isinstance(message, AssistantToolCallMessage):
        return [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.input,
                    }
                    for call in message.tool_operation_calls
                ],
            }
        ]

    # ToolResultMessage — Bedrock groups all results in one user message
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": result.tool_operation_call_id,
                    "content": result.content,
                }
                for result in message.tool_operation_results
            ],
        }
    ]


def _tool_operation_to_provider_format(operation: ToolOperation) -> dict[str, Any]:
    """Convert Operation to Bedrock tool format."""
    return {
        "name": operation.name,
        "description": operation.description,
        "input_schema": {
            "json": operation.input_schema,
        },
    }


class BedrockProvider(AbstractProvider):
    """AWS Bedrock LLM provider implementation."""

    config: BedrockConfig

    def __init__(self, config: BedrockConfig) -> None:
        super().__init__(config)
        client_kwargs: dict[str, Any] = {"region_name": config.region}
        if config.api_url:
            client_kwargs["endpoint_url"] = config.api_url
        self.client = boto3.client("bedrock-runtime", **client_kwargs)

    def identify(self) -> ProviderType:
        return ProviderType.BEDROCK

    def complete(
        self,
        messages: list[ConversationMessage],
        operations: list[ToolOperation] | None = None,
    ) -> ProviderResponse:
        """Send messages to Bedrock and get response."""
        bedrock_messages: list[dict[str, Any]] = []
        for msg in messages:
            bedrock_messages.extend(_message_to_provider_format(msg))

        request_body: dict[str, Any] = {
            "anthropic_version": self.config.anthropic_version,
            "messages": bedrock_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        if operations:
            request_body["tools"] = [_tool_operation_to_provider_format(op) for op in operations]

        response = self.client.invoke_model(
            modelId=self.config.model,
            body=json.dumps(request_body),
        )

        response_body = json.loads(response["body"].read())
        stop_reason = response_body.get("stop_reason")

        bedrock_usage = response_body.get("usage", {})
        usage = TokenUsage(
            input_tokens=bedrock_usage.get("input_tokens", 0),
            output_tokens=bedrock_usage.get("output_tokens", 0),
        )

        if stop_reason == "tool_use":
            operation_calls = []
            for block in response_body.get("content", []):
                if block.get("type") == "tool_use":
                    operation_calls.append(
                        ToolOperationCall(
                            id=block["id"],
                            name=block["name"],
                            input=block.get("input", {}),
                        )
                    )

            _logger.info(
                "bedrock_response_finished",
                reason=stop_reason,
                tool_operation_calls_count=len(operation_calls),
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )

            return ToolUseResponse(tool_operation_calls=operation_calls, usage=usage)

        content = ""
        for block in response_body.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        _logger.info(
            "bedrock_response_finished",
            reason=stop_reason,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return TextResponse(content=content, usage=usage)
