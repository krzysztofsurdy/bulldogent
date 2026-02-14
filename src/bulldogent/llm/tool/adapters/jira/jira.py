from pathlib import Path
from typing import Any

import structlog
from jira import JIRA, JIRAError

from bulldogent.llm.tool.tool import AbstractTool
from bulldogent.llm.tool.types import ToolOperationResult

_logger = structlog.get_logger()


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
        project_list = ", ".join(f"{p['prefix']} ({p['name']})" for p in self._projects)
        return f"{base}\nAvailable projects: {project_list}"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._projects: list[dict[str, Any]] = config.get("projects", [])
        self._client: JIRA | None = None

    def _get_client(self) -> JIRA:
        """Lazy-initialise the JIRA client on first use."""
        if self._client is None:
            self._client = JIRA(
                server=self.config["url"],
                basic_auth=(self.config["username"], self.config["api_token"]),
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
        except JIRAError as exc:
            _logger.error("jira_api_error", status=exc.status_code, text=exc.text)
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"Jira API error ({exc.status_code}): {exc.text}",
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
        issues = client.search_issues(jql, maxResults=max_results)

        if not issues:
            return ToolOperationResult(
                tool_operation_call_id="", content="No issues found matching the query."
            )

        lines = [f"Found {len(issues)} issue(s):"]
        for issue in issues:
            f = issue.fields
            assignee_name = (
                getattr(f.assignee, "displayName", "Unassigned") if f.assignee else "Unassigned"
            )
            lines.append(
                f"- {issue.key}: {f.summary} ({f.status.name}, assigned to {assignee_name})"
            )
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _get_issue(self, issue_key: str, **_: Any) -> ToolOperationResult:
        client = self._get_client()
        issue = client.issue(issue_key)
        f = issue.fields

        assignee_name = (
            getattr(f.assignee, "displayName", "Unassigned") if f.assignee else "Unassigned"
        )
        reporter_name = getattr(f.reporter, "displayName", "Unknown") if f.reporter else "Unknown"
        priority_name = getattr(f.priority, "name", "None") if f.priority else "None"
        labels = ", ".join(f.labels) if f.labels else "None"
        description = f.description or "No description"

        lines = [
            f"{issue.key}: {f.summary}",
            f"Type: {f.issuetype.name}",
            f"Status: {f.status.name}",
            f"Priority: {priority_name}",
            f"Assignee: {assignee_name}",
            f"Reporter: {reporter_name}",
            f"Labels: {labels}",
            f"Created: {f.created}",
            f"Updated: {f.updated}",
            f"Description: {description}",
        ]
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _list_issue_types(self, project_key: str, **_: Any) -> ToolOperationResult:
        client = self._get_client()
        resolved = self._resolve_project_key(project_key)
        project = client.project(resolved)
        issue_types = project.issueTypes

        if not issue_types:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"No issue types found for project {resolved}.",
            )

        lines = [f"Issue types for {resolved}:"]
        for it in issue_types:
            lines.append(f"- {it.name}: {it.description or 'No description'}")
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

        issue = client.create_issue(fields=fields)
        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Created issue {issue.key}: {summary}",
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
        issue = client.issue(issue_key)
        updated_parts: list[str] = []

        # field updates
        fields: dict[str, Any] = {}
        if summary:
            fields["summary"] = summary
            updated_parts.append("summary")
        if description:
            fields["description"] = description
            updated_parts.append("description")
        if fields:
            issue.update(fields=fields)

        # status transition
        if status:
            transitions = client.transitions(issue)
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
            client.transition_issue(issue, target["id"])
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
        issue = client.issue(issue_key)
        issue.delete()  # type: ignore[no-untyped-call]

        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Deleted issue {issue_key}",
        )
