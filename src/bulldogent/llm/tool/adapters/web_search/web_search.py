from pathlib import Path
from typing import Any

import structlog
from tavily import TavilyClient

from bulldogent.llm.tool.tool import AbstractTool
from bulldogent.llm.tool.types import ToolOperationResult

_logger = structlog.get_logger()

_SNIPPET_MAX_LEN = 300


class WebSearchTool(AbstractTool):
    _operations_path = Path(__file__).parent / "operations.yaml"

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for current, real-time information"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._default_max_results: int = config.get("default_max_results", 5)
        self._default_depth: str = config.get("default_search_depth", "basic")
        self._client: TavilyClient | None = None

    def _get_client(self) -> TavilyClient:
        if self._client is None:
            self._client = TavilyClient(api_key=self.config["api_key"])
        return self._client

    # -- dispatch -------------------------------------------------------

    def run(self, operation: str, **kwargs: Any) -> ToolOperationResult:
        _logger.info("web_search_operation", operation=operation, kwargs=kwargs)
        try:
            match operation:
                case "web_search":
                    return self._search(**kwargs)
                case _:
                    return ToolOperationResult(
                        tool_operation_call_id="",
                        content=f"Unknown operation: {operation}",
                        success=False,
                    )
        except Exception as exc:
            _logger.error("web_search_error", error=str(exc))
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"Web search error: {exc}",
                success=False,
            )

    # -- operations -----------------------------------------------------

    def _search(
        self,
        query: str,
        max_results: int | None = None,
        search_depth: str | None = None,
        **_: Any,
    ) -> ToolOperationResult:
        client = self._get_client()
        response = client.search(
            query=query,
            max_results=max_results or self._default_max_results,
            search_depth=search_depth or self._default_depth,
        )

        results = response.get("results", [])
        if not results:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"No results found for: {query}",
            )

        lines = [f"Web search: {query}\n"]

        answer = response.get("answer")
        if answer:
            lines.append(f"Summary: {answer}\n")

        lines.append(f"Results ({len(results)}):\n")
        for i, result in enumerate(results, 1):
            title = result.get("title", "Untitled")
            url = result.get("url", "")
            content = result.get("content", "")
            if len(content) > _SNIPPET_MAX_LEN:
                content = content[:_SNIPPET_MAX_LEN] + "..."

            lines.append(f"{i}. {title}")
            if url:
                lines.append(f"   {url}")
            if content:
                lines.append(f"   {content}")
            lines.append("")

        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))
