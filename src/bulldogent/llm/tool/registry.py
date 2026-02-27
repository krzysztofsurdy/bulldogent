from typing import Any

import structlog

from bulldogent.llm.tool.tool import AbstractTool
from bulldogent.llm.tool.types import ToolOperation, ToolOperationResult, ToolUserContext
from bulldogent.util import PROJECT_ROOT, load_yaml_config

_logger = structlog.get_logger()
_PLATFORMS_CONFIG_PATH = PROJECT_ROOT / "config" / "platforms.yaml"


class ToolRegistry:
    """Collects tools and dispatches operation calls to the right tool.

    Think of it like a Symfony ServiceLocator -- holds tool instances,
    exposes a flat list of operations for the LLM, and routes execution
    calls back to the correct tool.
    """

    def __init__(self) -> None:
        self._tools: dict[str, AbstractTool] = {}
        self._operation_map: dict[str, AbstractTool] = {}
        platforms_config = load_yaml_config(_PLATFORMS_CONFIG_PATH)
        self._approval_config: dict[str, Any] = platforms_config.get("approvals", {})

    def register(self, tool: AbstractTool) -> None:
        if tool.name in self._tools:
            msg = f"Tool '{tool.name}' is already registered"
            raise ValueError(msg)

        self._tools[tool.name] = tool

        for operation in tool.operations():
            if operation.name in self._operation_map:
                existing = self._operation_map[operation.name]
                msg = f"Operation '{operation.name}' already registered by tool '{existing.name}'"
                raise ValueError(msg)
            self._operation_map[operation.name] = tool

        _logger.info(
            "tool_registered",
            tool=tool.name,
            operations=[op.name for op in tool.operations()],
        )

    def get_all_operations(self) -> list[ToolOperation]:
        operations: list[ToolOperation] = []
        for tool in self._tools.values():
            operations.extend(tool.operations())
        return operations

    def get_tool_descriptions(self) -> list[str]:
        """Return the description of each registered tool.

        These include dynamic context like available projects,
        repositories, and spaces -- intended for the system prompt.
        """
        return [tool.description for tool in self._tools.values()]

    def execute(
        self,
        operation_name: str,
        *,
        user_context: ToolUserContext | None = None,
        **kwargs: Any,
    ) -> ToolOperationResult:
        tool = self._operation_map.get(operation_name)
        if tool is None:
            msg = f"Unknown operation: '{operation_name}'"
            raise KeyError(msg)

        valid, error_message = tool.validate(operation_name, **kwargs)
        if not valid:
            _logger.warning(
                "tool_validation_failed",
                operation=operation_name,
                error=error_message,
            )
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"Validation failed: {error_message}",
                success=False,
            )

        return tool.run(operation_name, user_context=user_context, **kwargs)

    def resolve_project(self, operation_name: str, **kwargs: Any) -> str | None:
        tool = self._operation_map.get(operation_name)
        if tool is None:
            return None
        return tool.resolve_project(operation_name, **kwargs)

    def get_approval_group(self, operation_name: str, project: str | None = None) -> str | None:
        """Resolve the approval group for an operation.

        Two-level hierarchy, most specific wins:
        1. Project/entity override
        2. Operation default

        Unlisted operations require no approval.
        Use ~ in YAML to explicitly exempt a project.
        """
        tool = self._operation_map.get(operation_name)
        if tool is None:
            return None

        tool_config = self._approval_config.get(tool.name, {})
        entry = tool_config.get(operation_name)
        if entry is None:
            return None

        if project:
            proj = entry.get("projects", {})
            if project.upper() in proj:
                return proj[project.upper()] or None

        group: str | None = entry.get("approval_group")
        return group
