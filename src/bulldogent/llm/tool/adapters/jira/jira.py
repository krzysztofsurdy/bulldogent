from pathlib import Path
from typing import Any

import httpx
import structlog

from bulldogent.llm.tool.tool import AbstractTool
from bulldogent.llm.tool.types import ToolOperation, ToolOperationResult
from bulldogent.util import load_yaml_config

_logger = structlog.get_logger()
_OPERATIONS_PATH = Path(__file__).parent / "operations.yaml"


class JiraTool(AbstractTool):
    @property
    def name(self) -> str:
        return "jira"

    @property
    def description(self) -> str:
        base = "Jira issue tracking — search, view, create, update, and delete issues"
        if not self._projects:
            return base
        project_list = ", ".join(f"{p['prefix']} ({p['name']})" for p in self._projects)
        return f"{base}\nAvailable projects: {project_list}"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._projects: list[dict[str, Any]] = config.get("projects", [])
        self._operations_config = load_yaml_config(_OPERATIONS_PATH)
        self._client = httpx.Client(
            base_url=config["url"].rstrip("/"),
            auth=httpx.BasicAuth(config["username"], config["api_token"]),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    def operations(self) -> list[ToolOperation]:
        result = []
        for op_name, op_config in self._operations_config.items():
            result.append(
                ToolOperation(
                    name=op_name,
                    description=op_config["description"],
                    input_schema=self._build_schema(op_config),
                )
            )
        return result

    def run(self, operation: str, **kwargs: Any) -> ToolOperationResult:
        _logger.info("jira_operation", operation=operation, kwargs=kwargs)
        try:
            match operation:
                case "jira_search_issues":
                    return self._search(**kwargs)
                case "jira_get_issue":
                    return self._get_issue(**kwargs)
                case "jira_create_issue":
                    return self._create_issue(**kwargs)
                case "jira_update_issue":
                    return self._update_issue(**kwargs)
                case "jira_delete_issue":
                    return self._delete_issue(**kwargs)
                case _:
                    return ToolOperationResult(
                        tool_operation_call_id="",
                        content=f"Unknown operation: {operation}",
                        success=False,
                    )
        except httpx.HTTPStatusError as e:
            _logger.error("jira_http_error", status=e.response.status_code, body=e.response.text)
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"Jira API error: {e.response.status_code} {e.response.reason_phrase}",
                success=False,
            )
        except httpx.HTTPError as e:
            _logger.error("jira_connection_error", error=str(e))
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"Failed to connect to Jira: {e}",
                success=False,
            )

    def _build_schema(self, op_config: dict[str, Any]) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for param_name, param_def in op_config.get("parameters", {}).items():
            properties[param_name] = {
                "type": param_def["type"],
                "description": param_def.get("description", ""),
            }
            if not param_def.get("optional", False):
                required.append(param_name)
        return {"type": "object", "properties": properties, "required": required}

    def _resolve_project_key(self, project: str) -> str:
        """Resolve a project name or alias to its Jira prefix."""
        lookup = project.lower()
        for p in self._projects:
            prefix = str(p["prefix"])
            if prefix.lower() == lookup:
                return prefix
            if str(p.get("name", "")).lower() == lookup:
                return prefix
            for alias in p.get("aliases", []):
                if str(alias).lower() == lookup:
                    return prefix
        return project.upper()

    # -- HTTP operations --

    def _search(self, jql: str, max_results: int = 10, **_: Any) -> ToolOperationResult:
        response = self._client.get(
            "/rest/api/3/search",
            params={"jql": jql, "maxResults": max_results},
        )
        response.raise_for_status()
        data = response.json()

        issues = data.get("issues", [])
        if not issues:
            content = "No issues found matching the query."
        else:
            lines = [f"Found {len(issues)} issue(s):"]
            for issue in issues:
                key = issue["key"]
                fields = issue["fields"]
                summary = fields.get("summary", "")
                status = fields.get("status", {}).get("name", "Unknown")
                assignee = fields.get("assignee")
                assignee_name = (
                    assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
                )
                lines.append(f"- {key}: {summary} ({status}, assigned to {assignee_name})")
            content = "\n".join(lines)

        return ToolOperationResult(tool_operation_call_id="", content=content)

    def _get_issue(self, issue_key: str, **_: Any) -> ToolOperationResult:
        response = self._client.get(f"/rest/api/3/issue/{issue_key}")
        response.raise_for_status()
        data = response.json()

        fields = data["fields"]
        key = data["key"]
        summary = fields.get("summary", "")
        status = fields.get("status", {}).get("name", "Unknown")
        assignee = fields.get("assignee", {})
        assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        priority = fields.get("priority", {})
        priority_name = priority.get("name", "None") if priority else "None"
        description = self._extract_text(fields.get("description"))

        lines = [
            f"{key}: {summary}",
            f"Type: {issue_type}",
            f"Status: {status}",
            f"Priority: {priority_name}",
            f"Assignee: {assignee_name}",
        ]
        if description:
            lines.append(f"Description: {description}")

        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _create_issue(
        self,
        project_key: str,
        summary: str,
        issue_type: str,
        description: str | None = None,
        **_: Any,
    ) -> ToolOperationResult:
        resolved_key = self._resolve_project_key(project_key)
        payload: dict[str, Any] = {
            "fields": {
                "project": {"key": resolved_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
            }
        }
        if description:
            payload["fields"]["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }

        response = self._client.post("/rest/api/3/issue", json=payload)
        response.raise_for_status()
        data = response.json()

        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Created issue {data['key']}: {summary}",
        )

    def _update_issue(
        self,
        issue_key: str,
        summary: str | None = None,
        description: str | None = None,
        **_: Any,
    ) -> ToolOperationResult:
        fields: dict[str, Any] = {}
        if summary:
            fields["summary"] = summary
        if description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }

        if not fields:
            return ToolOperationResult(
                tool_operation_call_id="",
                content="No fields to update.",
                success=False,
            )

        response = self._client.put(f"/rest/api/3/issue/{issue_key}", json={"fields": fields})
        response.raise_for_status()

        updated = ", ".join(fields.keys())
        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Updated {issue_key}: {updated}",
        )

    def _delete_issue(self, issue_key: str, **_: Any) -> ToolOperationResult:
        response = self._client.delete(f"/rest/api/3/issue/{issue_key}")
        response.raise_for_status()

        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Deleted issue {issue_key}",
        )

    def _extract_text(self, description: Any) -> str:
        """Extract plain text from Atlassian Document Format (ADF)."""
        if not description or not isinstance(description, dict):
            return ""
        texts: list[str] = []
        for block in description.get("content", []):
            for inline in block.get("content", []):
                if inline.get("type") == "text":
                    texts.append(inline.get("text", ""))
        return " ".join(texts)
