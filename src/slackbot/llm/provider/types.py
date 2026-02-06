from dataclasses import dataclass
from enum import StrEnum

from slackbot.llm.tool.types import ToolOperationCall


class ProviderType(StrEnum):
    OPENAI = "openai"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


class FinishReason(StrEnum):
    TOOL_USE = "tool_use"
    END_TURN = "end_turn"


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ProviderResponse:
    finish_reason: FinishReason
    content: str | None = None
    tool_operation_calls: list[ToolOperationCall] | None = None
