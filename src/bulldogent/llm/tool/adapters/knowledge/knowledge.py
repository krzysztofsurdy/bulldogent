from pathlib import Path
from typing import Any

import structlog

from bulldogent.baseline.retriever import BaselineRetriever
from bulldogent.llm.tool.tool import AbstractTool, ToolConfig
from bulldogent.llm.tool.types import ToolOperationResult, ToolUserContext

_logger = structlog.get_logger()

_MAX_TOP_K = 20


class KnowledgeTool(AbstractTool):
    _operations_path = Path(__file__).parent / "operations.yaml"

    @property
    def name(self) -> str:
        return "knowledge"

    @property
    def description(self) -> str:
        return "Search the internal knowledge base (Confluence, GitHub, Jira, past conversations)"

    def __init__(self, config: ToolConfig, retriever: BaselineRetriever) -> None:
        super().__init__(config)
        self._retriever = retriever

    def run(
        self, operation: str, *, user_context: ToolUserContext | None = None, **kwargs: Any
    ) -> ToolOperationResult:
        _logger.info("knowledge_operation", operation=operation, params=list(kwargs.keys()))
        try:
            match operation:
                case "knowledge_search":
                    return self._search(**kwargs)
                case _:
                    return ToolOperationResult(
                        tool_operation_call_id="",
                        content=f"Unknown operation: {operation}",
                        success=False,
                    )
        except Exception as exc:
            _logger.error("knowledge_error", error=str(exc))
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"Knowledge search error: {exc}",
                success=False,
            )

    def _search(
        self,
        query: str,
        top_k: int | None = None,
        **_: Any,
    ) -> ToolOperationResult:
        if top_k is not None:
            top_k = min(top_k, _MAX_TOP_K)

        results = self._retriever.retrieve(query, top_k=top_k)

        if not results:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"No knowledge base results for: {query}",
            )

        lines = [f"Knowledge search: {query}\n"]
        lines.append(f"Results ({len(results)}):\n")

        for i, result in enumerate(results, 1):
            lines.append(f"{i}. [{result.source}] {result.title} (score: {result.score:.2f})")
            if result.url:
                lines.append(f"   {result.url}")
            lines.append(f"   {result.content}")
            lines.append("")

        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))
