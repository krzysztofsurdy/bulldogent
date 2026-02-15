import re
from pathlib import Path
from typing import Any

import structlog
from atlassian import Confluence

from bulldogent.llm.tool.tool import AbstractTool
from bulldogent.llm.tool.types import ToolOperationResult

_logger = structlog.get_logger()


class ConfluenceTool(AbstractTool):
    _operations_path = Path(__file__).parent / "operations.yaml"

    @property
    def name(self) -> str:
        return "confluence"

    @property
    def description(self) -> str:
        base = "Confluence wiki — search pages, read content, browse spaces"
        spaces = self.config.get("spaces", [])
        if not spaces:
            return base
        space_list = ", ".join(f"{s['key']} ({s.get('name', '')})" for s in spaces)
        return f"{base}\nAvailable spaces: {space_list}"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._spaces: list[dict[str, Any]] = config.get("spaces", [])
        self._client: Confluence | None = None

    def _get_client(self) -> Confluence:
        if self._client is None:
            self._client = Confluence(
                url=self.config["url"],
                username=self.config.get("username"),
                password=self.config.get("api_token"),
                cloud=self.config.get("cloud", True),
            )
        return self._client

    # -- dispatch -------------------------------------------------------

    def run(self, operation: str, **kwargs: Any) -> ToolOperationResult:
        _logger.info("confluence_operation", operation=operation, kwargs=kwargs)
        try:
            match operation:
                case "confluence_search":
                    return self._search(**kwargs)
                case "confluence_get_page":
                    return self._get_page(**kwargs)
                case "confluence_get_children":
                    return self._get_children(**kwargs)
                case "confluence_list_spaces":
                    return self._list_spaces(**kwargs)
                case _:
                    return ToolOperationResult(
                        tool_operation_call_id="",
                        content=f"Unknown operation: {operation}",
                        success=False,
                    )
        except Exception as exc:
            _logger.error("confluence_error", error=str(exc))
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"Confluence error: {exc}",
                success=False,
            )

    # -- project resolution for approval --------------------------------

    def resolve_project(self, operation: str, **kwargs: Any) -> str | None:
        if space := kwargs.get("space"):
            return str(space).upper()
        if page_id := kwargs.get("page_id"):
            return str(page_id)
        return None

    # -- CQL builder ----------------------------------------------------

    @staticmethod
    def _build_cql(
        space: str | None = None,
        title: str | None = None,
        text: str | None = None,
        label: str | None = None,
    ) -> str:
        clauses: list[str] = ["type = page"]
        if space:
            clauses.append(f'space = "{space}"')
        if title:
            clauses.append(f'title ~ "{title}"')
        if text:
            clauses.append(f'text ~ "{text}"')
        if label:
            clauses.append(f'label = "{label}"')
        return " AND ".join(clauses) + " ORDER BY lastmodified DESC"

    # -- content helpers ------------------------------------------------

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Strip HTML tags to produce readable plain text."""
        text = re.sub(r"<br\s*/?>", "\n", html)
        text = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # -- operations -----------------------------------------------------

    def _search(
        self,
        space: str | None = None,
        title: str | None = None,
        text: str | None = None,
        label: str | None = None,
        cql: str | None = None,
        limit: int = 10,
        **_: Any,
    ) -> ToolOperationResult:
        if cql is None:
            cql = self._build_cql(space=space, title=title, text=text, label=label)

        client = self._get_client()
        results = client.cql(cql, limit=limit)
        pages = results.get("results", [])

        if not pages:
            return ToolOperationResult(tool_operation_call_id="", content="No pages found.")

        lines = [f"Found {len(pages)} page(s):"]
        for page in pages:
            content = page.get("content", page)
            page_title = content.get("title", "Untitled")
            space_info = content.get("space", {})
            space_key = space_info.get("key", "?") if isinstance(space_info, dict) else "?"
            page_id = content.get("id", "")
            lines.append(f"- [{space_key}] {page_title} (id: {page_id})")

        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _get_page(
        self,
        page_id: str | None = None,
        space: str | None = None,
        title: str | None = None,
        **_: Any,
    ) -> ToolOperationResult:
        client = self._get_client()

        if page_id:
            page = client.get_page_by_id(page_id, expand="body.storage,version,space")
        elif space and title:
            page = client.get_page_by_title(space, title, expand="body.storage,version")
        else:
            return ToolOperationResult(
                tool_operation_call_id="",
                content="Provide either page_id, or both space and title.",
                success=False,
            )

        if not page:
            return ToolOperationResult(
                tool_operation_call_id="", content="Page not found.", success=False
            )

        page_title = page.get("title", "Untitled")
        version = page.get("version", {}).get("number", "?")
        space_info = page.get("space", {})
        space_key = space_info.get("key", "?") if isinstance(space_info, dict) else "?"

        body_html = page.get("body", {}).get("storage", {}).get("value", "")
        body_text = self._html_to_text(body_html) if body_html else "No content"

        lines = [
            f"{page_title}",
            f"Space: {space_key} | Version: {version} | ID: {page.get('id', '?')}",
            "",
            body_text,
        ]
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _get_children(self, page_id: str, limit: int = 25, **_: Any) -> ToolOperationResult:
        client = self._get_client()
        children = client.get_page_child_by_type(page_id, type="page", start=0, limit=limit)

        if not children:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"No child pages found for page {page_id}.",
            )

        lines = [f"Child pages of {page_id} ({len(children)}):"]
        for child in children:
            child_title = child.get("title", "Untitled")
            child_id = child.get("id", "?")
            lines.append(f"- {child_title} (id: {child_id})")

        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _list_spaces(self, limit: int = 50, **_: Any) -> ToolOperationResult:
        client = self._get_client()
        response = client.get_all_spaces(start=0, limit=limit)
        spaces = response.get("results", []) if isinstance(response, dict) else response

        if not spaces:
            return ToolOperationResult(tool_operation_call_id="", content="No spaces found.")

        lines = [f"Confluence spaces ({len(spaces)}):"]
        for space in spaces:
            key = space.get("key", "?")
            space_name = space.get("name", "Unnamed")
            space_type = space.get("type", "")
            lines.append(f"- {key}: {space_name} ({space_type})")

        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))
