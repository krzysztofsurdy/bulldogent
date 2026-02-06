from dataclasses import dataclass
from typing import Any


@dataclass
class ToolOperation:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolOperationCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolOperationResult:
    tool_operation_call_id: str
    content: str
    success: bool = True
