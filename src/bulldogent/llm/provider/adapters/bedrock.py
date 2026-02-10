import json
from typing import Any

import boto3  # type: ignore[import-untyped]
import structlog

from bulldogent.llm.provider.config import BedrockConfig
from bulldogent.llm.provider.provider import AbstractProvider
from bulldogent.llm.provider.types import (
    Message,
    ProviderResponse,
    ProviderType,
    TextResponse,
    ToolUseResponse,
)
from bulldogent.llm.tool.types import ToolOperation, ToolOperationCall

_logger = structlog.get_logger()


def _message_to_provider_format(message: Message) -> dict[str, Any]:
    """Convert Message to Bedrock API format."""
    return {
        "role": message.role,
        "content": message.content,
    }


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
        self.client = boto3.client("bedrock-runtime", region_name=config.region)

    def identify(self) -> ProviderType:
        return ProviderType.BEDROCK

    def complete(
        self,
        messages: list[Message],
        operations: list[ToolOperation] | None = None,
    ) -> ProviderResponse:
        """Send messages to Bedrock and get response."""
        bedrock_messages = [_message_to_provider_format(message) for message in messages]

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

        if stop_reason == "tool_use":
            # Bedrock returns tool use blocks in content
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
            )

            return ToolUseResponse(tool_operation_calls=operation_calls)

        # Extract text content
        content = ""
        for block in response_body.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        _logger.info("bedrock_response_finished", reason=stop_reason)
        return TextResponse(content=content)
