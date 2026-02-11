from dataclasses import dataclass
from enum import StrEnum

from bulldogent.llm.tool.types import ToolOperationCall, ToolOperationResult


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
class AssistantToolCallMessage:
    tool_operation_calls: list[ToolOperationCall]


@dataclass
class ToolResultMessage:
    tool_operation_results: list[ToolOperationResult]


type ConversationMessage = Message | AssistantToolCallMessage | ToolResultMessage


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class TextResponse:
    content: str
    usage: TokenUsage


@dataclass
class ToolUseResponse:
    tool_operation_calls: list[ToolOperationCall]
    usage: TokenUsage


type ProviderResponse = TextResponse | ToolUseResponse
