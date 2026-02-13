from abc import ABC, abstractmethod
from typing import Any

from bulldogent.llm.tool.types import ToolOperation, ToolOperationResult


class AbstractTool(ABC):
    def __init__(self, config: dict[str, Any]):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier (e.g., 'confluence', 'jira')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM usage"""
        pass

    @abstractmethod
    def operations(self) -> list[ToolOperation]:
        """
        Return list of Tool definitions for LLM.

        A single tool implementation can expose multiple operations.
        Example: JiraTool might expose 'search_issues' and 'get_issue'.
        """
        ...

    @abstractmethod
    def run(self, operation: str, **kwargs: Any) -> ToolOperationResult:
        """
        Execute a tool operation.

        Args:
            operation: The operation name (matches Tool.name from get_schemas)
            **kwargs: Operation parameters from LLM

        Returns:
            ToolResult with success status and content
        """
        ...

    def resolve_project(self, operation: str, **kwargs: Any) -> str | None:
        """Resolve which project an operation targets.

        Used for approval group resolution — project-level overrides
        take precedence over operation and tool defaults.

        Returns:
            Project key/prefix, or None if no project context.
        """
        return None

    def validate(self, operation: str, **kwargs: Any) -> tuple[bool, str | None]:
        """
        Optional: Validate inputs before execution.

        Returns:
            (is_valid, error_message)
        """
        return True, None
