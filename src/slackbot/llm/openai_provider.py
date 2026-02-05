import json
from typing import Any

import structlog
from openai import OpenAI

from slackbot.llm.provider import LLMProvider
from slackbot.llm.types import LLMResponse, Message, StopReason, Tool, ToolCall

logger = structlog.get_logger()


def message_to_openai(message: Message) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": message.content,
    }


def tool_to_openai(tool: Tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def complete(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
    ) -> LLMResponse:
        openai_messages = [message_to_openai(message) for message in messages]
        params = {
            "model": self.model,
            "messages": openai_messages,
        }

        if tools:
            params["tools"] = [tool_to_openai(tool) for tool in tools]

        response = self.client.chat.completions.create(**params)  # type: ignore[call-overload]
        choice = response.choices[0]
        finish_reason = choice.finish_reason

        if finish_reason == "tool_calls" and choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    input=json.loads(tc.function.arguments),
                )
                for tc in choice.message.tool_calls
            ]

            logger.info(
                "openai_response_finished", reason=finish_reason, tool_calls_qty=len(tool_calls)
            )

            return LLMResponse(
                stop_reason=StopReason.TOOL_USE,
                tool_calls=tool_calls,
            )

        logger.info("openai_response_finished", reason=finish_reason)
        return LLMResponse(stop_reason=StopReason.END_TURN, content=choice.message.content or "")
