from pathlib import Path
from typing import Any

import structlog
from atlassian import Jira

from bulldogent.llm.tool.tool import AbstractTool
from bulldogent.llm.tool.types import ToolOperationResult

_logger = structlog.get_logger()


def _safe(obj: Any, key: str, fallback: str = "Unknown") -> str:
    """Safely extract a display value from a possibly-None nested dict."""
    if not obj:
        return fallback
    if isinstance(obj, dict):
        return str(obj.get(key, fallback))
    return str(getattr(obj, key, fallback))


class JiraTool(AbstractTool):
    _operations_path = Path(__file__).parent / "operations.yaml"

    @property
    def name(self) -> str:
        return "jira"

    @property
    def description(self) -> str:
        base = "Jira issue tracking — search, view, create, update, and delete issues"
        if not self._projects:
            return base
        lines = [base, "Available projects:"]
        for p in self._projects:
            aliases = p.get("aliases", [])
            alias_str = f" (aliases: {', '.join(aliases)})" if aliases else ""
            desc = p.get("description", "")
            desc_str = f" — {desc}" if desc else ""
            lines.append(f"  - {p['prefix']} ({p['name']}){desc_str}{alias_str}")
        return "\n".join(lines)

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._projects: list[dict[str, Any]] = config.get("projects", [])
        self._client: Jira | None = None

    def _get_client(self) -> Jira:
        if self._client is None:
            self._client = Jira(
                url=self.config["url"],
                username=self.config["username"],
                password=self.config["api_token"],
                cloud=self.config.get("cloud", True),
            )
        return self._client

    # -- dispatch -------------------------------------------------------

    def run(self, operation: str, **kwargs: Any) -> ToolOperationResult:
        _logger.info("jira_operation", operation=operation, kwargs=kwargs)
        try:
            match operation:
                case "jira_search_issues":
                    return self._search(**kwargs)
                case "jira_get_issue":
                    return self._get_issue(**kwargs)
                case "jira_list_issue_types":
                    return self._list_issue_types(**kwargs)
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
        except Exception as exc:
            _logger.error("jira_error", error=str(exc))
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"Jira error: {exc}",
                success=False,
            )

    # -- project resolution ---------------------------------------------

    def resolve_project(self, operation: str, **kwargs: Any) -> str | None:
        match operation:
            case "jira_create_issue" | "jira_list_issue_types":
                key = kwargs.get("project_key", "")
                return self._resolve_project_key(key) if key else None
            case "jira_get_issue" | "jira_update_issue" | "jira_delete_issue":
                issue_key = kwargs.get("issue_key", "")
                return issue_key.split("-")[0] if "-" in issue_key else None
            case _:
                return None

    def _resolve_project_key(self, project: str) -> str:
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

    # -- JQL builder ----------------------------------------------------

    @staticmethod
    def _build_jql(
        project: str | None = None,
        status: str | None = None,
        issue_type: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
    ) -> str:
        clauses: list[str] = []
        if project:
            clauses.append(f'project = "{project}"')
        if status:
            clauses.append(f'status = "{status}"')
        if issue_type:
            clauses.append(f'issuetype = "{issue_type}"')
        if assignee:
            if assignee == "currentUser()":
                clauses.append("assignee = currentUser()")
            else:
                clauses.append(f'assignee = "{assignee}"')
        if labels:
            for label in labels:
                clauses.append(f'labels = "{label}"')
        jql = " AND ".join(clauses) if clauses else "ORDER BY created DESC"
        if clauses:
            jql += " ORDER BY updated DESC"
        return jql

    # -- operations -----------------------------------------------------

    def _search(
        self,
        project: str | None = None,
        status: str | None = None,
        issue_type: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
        jql: str | None = None,
        max_results: int = 10,
        **_: Any,
    ) -> ToolOperationResult:
        if jql is None:
            resolved_project = self._resolve_project_key(project) if project else None
            jql = self._build_jql(
                project=resolved_project,
                status=status,
                issue_type=issue_type,
                assignee=assignee,
                labels=labels,
            )

        client = self._get_client()
        data = client.jql(jql, limit=max_results)
        issues: list[Any] = (data or {}).get("issues", [])

        if not issues:
            return ToolOperationResult(
                tool_operation_call_id="", content="No issues found matching the query."
            )

        lines = [f"Found {len(issues)} issue(s):"]
        for issue in issues:
            key = issue["key"]
            fields = issue["fields"]
            summary = fields.get("summary", "")
            status_name = _safe(fields.get("status"), "name", "Unknown")
            assignee_name = _safe(fields.get("assignee"), "displayName", "Unassigned")
            lines.append(f"- {key}: {summary} ({status_name}, assigned to {assignee_name})")

        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _get_issue(self, issue_key: str, **_: Any) -> ToolOperationResult:
        client = self._get_client()
        issue = client.issue(issue_key)
        fields = issue["fields"]

        assignee_name = _safe(fields.get("assignee"), "displayName", "Unassigned")
        reporter_name = _safe(fields.get("reporter"), "displayName", "Unknown")
        priority_name = _safe(fields.get("priority"), "name", "None")
        issue_type_name = _safe(fields.get("issuetype"), "name", "Unknown")
        status_name = _safe(fields.get("status"), "name", "Unknown")
        issue_labels = fields.get("labels", [])
        label_str = ", ".join(issue_labels) if issue_labels else "None"
        description = fields.get("description") or "No description"

        lines = [
            f"{issue['key']}: {fields.get('summary', '')}",
            f"Type: {issue_type_name}",
            f"Status: {status_name}",
            f"Priority: {priority_name}",
            f"Assignee: {assignee_name}",
            f"Reporter: {reporter_name}",
            f"Labels: {label_str}",
            f"Created: {fields.get('created', '?')}",
            f"Updated: {fields.get('updated', '?')}",
            f"Description: {description}",
        ]
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _list_issue_types(self, project_key: str, **_: Any) -> ToolOperationResult:
        client = self._get_client()
        resolved = self._resolve_project_key(project_key)
        issue_types = client.issue_createmeta_issuetypes(resolved)

        if not issue_types:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"No issue types found for project {resolved}.",
            )

        if isinstance(issue_types, dict):
            values = issue_types.get("values", issue_types)
        else:
            values = issue_types
        lines = [f"Issue types for {resolved}:"]
        for it in values:
            name = it.get("name", "Unknown") if isinstance(it, dict) else str(it)
            desc = it.get("description", "") if isinstance(it, dict) else ""
            lines.append(f"- {name}: {desc or 'No description'}")

        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _create_issue(
        self,
        project_key: str,
        summary: str,
        issue_type: str,
        description: str | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        **_: Any,
    ) -> ToolOperationResult:
        resolved_key = self._resolve_project_key(project_key)
        client = self._get_client()

        fields: dict[str, Any] = {
            "project": {"key": resolved_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = description
        if priority:
            fields["priority"] = {"name": priority}
        if assignee:
            fields["assignee"] = {"name": assignee}

        result = client.issue_create(fields=fields)
        issue_key = result.get("key", "?")
        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Created issue {issue_key}: {summary}",
        )

    def _update_issue(
        self,
        issue_key: str,
        summary: str | None = None,
        description: str | None = None,
        status: str | None = None,
        **_: Any,
    ) -> ToolOperationResult:
        client = self._get_client()
        updated_parts: list[str] = []

        fields: dict[str, Any] = {}
        if summary:
            fields["summary"] = summary
            updated_parts.append("summary")
        if description:
            fields["description"] = description
            updated_parts.append("description")
        if fields:
            client.update_issue_field(issue_key, fields)

        if status:
            transitions = client.get_issue_transitions(issue_key)
            target = next(
                (t for t in transitions if t["name"].lower() == status.lower()),
                None,
            )
            if target is None:
                available = ", ".join(t["name"] for t in transitions)
                return ToolOperationResult(
                    tool_operation_call_id="",
                    content=(
                        f"Cannot transition {issue_key} to '{status}'. "
                        f"Available transitions: {available}"
                    ),
                    success=False,
                )
            client.issue_transition(issue_key, target["id"])
            updated_parts.append(f"status → {status}")

        if not updated_parts:
            return ToolOperationResult(
                tool_operation_call_id="",
                content="No fields to update.",
                success=False,
            )

        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Updated {issue_key}: {', '.join(updated_parts)}",
        )

    def _delete_issue(self, issue_key: str, **_: Any) -> ToolOperationResult:
        client = self._get_client()
        client.delete_issue(issue_key)

        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Deleted issue {issue_key}",
        )
