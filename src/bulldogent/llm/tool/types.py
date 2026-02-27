from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolUserContext:
    """User context passed to tools that need per-user credentials."""

    user_id: str = ""
    platform_user_id: str = ""
    platform: str = ""
    google_email: str = ""
    extra: dict[str, str] = field(default_factory=dict)


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
