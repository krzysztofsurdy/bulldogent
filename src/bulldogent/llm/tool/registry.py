from typing import Any

import structlog

from bulldogent.llm.tool.tool import AbstractTool
from bulldogent.llm.tool.types import ToolOperation, ToolOperationResult

_logger = structlog.get_logger()


class ToolRegistry:
    """Collects tools and dispatches operation calls to the right tool.

    Think of it like a Symfony ServiceLocator — holds tool instances,
    exposes a flat list of operations for the LLM, and routes execution
    calls back to the correct tool.
    """

    def __init__(self) -> None:
        self._tools: dict[str, AbstractTool] = {}
        self._operation_map: dict[str, AbstractTool] = {}

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

    def execute(self, operation_name: str, **kwargs: Any) -> ToolOperationResult:
        tool = self._operation_map.get(operation_name)
        if tool is None:
            msg = f"Unknown operation: '{operation_name}'"
            raise KeyError(msg)

        return tool.run(operation_name, **kwargs)
