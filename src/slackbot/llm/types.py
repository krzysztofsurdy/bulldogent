from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class StopReason(StrEnum):
    TOOL_USE = "tool_use"
    END_TURN = "end_turn"


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResult:
    tool_call_id: str
    content: str


@dataclass
class LLMResponse:
    stop_reason: StopReason
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
