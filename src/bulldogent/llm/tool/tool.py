from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from bulldogent.llm.tool.types import ToolOperation, ToolOperationResult, ToolUserContext
from bulldogent.util import load_yaml_config

ToolConfig = dict[str, Any]
"""Type alias for tool configuration dictionaries."""


class AbstractTool(ABC):
    """Base class for all tool adapters.

    Subclasses must define ``name``, ``description``, ``_operations_path``,
    and ``run``.  The YAML-driven schema loading and ``operations()`` method
    are provided here -- no need to duplicate across adapters.
    """

    _operations_path: Path  # each subclass sets this as a class attribute

    def __init__(self, config: ToolConfig):
        self.config = config
        self._operations_config: dict[str, Any] = load_yaml_config(self._operations_path)

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier (e.g., 'confluence', 'jira')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM usage"""
        ...

    def operations(self) -> list[ToolOperation]:
        """Build tool operations from the YAML config."""
        return [
            ToolOperation(
                name=op_name,
                description=op_config["description"],
                input_schema=self._build_schema(op_config),
            )
            for op_name, op_config in self._operations_config.items()
        ]

    @abstractmethod
    def run(
        self,
        operation: str,
        *,
        user_context: ToolUserContext | None = None,
        **kwargs: Any,
    ) -> ToolOperationResult:
        """Execute a tool operation."""
        ...

    def resolve_project(self, operation: str, **kwargs: Any) -> str | None:
        """Resolve which project an operation targets.

        Used for approval group resolution -- project-level overrides
        take precedence over operation and tool defaults.

        Returns:
            Project key/prefix, or None if no project context.
        """
        return None

    def validate(self, operation: str, **kwargs: Any) -> tuple[bool, str | None]:
        """Optional: Validate inputs before execution."""
        return True, None

    @staticmethod
    def _build_schema(op_config: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML parameter definitions into a JSON Schema object."""
        properties: dict[str, Any] = {}
        required: list[str] = []
        for param_name, param_def in op_config.get("parameters", {}).items():
            prop: dict[str, Any] = {"type": param_def["type"]}
            if desc := param_def.get("description"):
                prop["description"] = desc
            if "enum" in param_def:
                prop["enum"] = param_def["enum"]
            if "items" in param_def:
                prop["items"] = param_def["items"]
            properties[param_name] = prop
            if not param_def.get("optional", False):
                required.append(param_name)
        return {"type": "object", "properties": properties, "required": required}
