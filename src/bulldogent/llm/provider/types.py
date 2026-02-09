from dataclasses import dataclass
from enum import StrEnum

from bulldogent.llm.tool.types import ToolOperationCall


class ProviderType(StrEnum):
    OPENAI = "openai"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class Message:
    role: MessageRole
    content: str


@dataclass
class TextResponse:
    content: str


@dataclass
class ToolUseResponse:
    tool_operation_calls: list[ToolOperationCall]


type ProviderResponse = TextResponse | ToolUseResponse
