from collections.abc import Iterator
from pathlib import Path
from typing import Any, TypeVar

import structlog
from github import Github, GithubException
from github.GithubObject import GithubObject
from github.PaginatedList import PaginatedList
from github.Repository import Repository

from bulldogent.llm.tool.tool import AbstractTool
from bulldogent.llm.tool.types import ToolOperationResult

_logger = structlog.get_logger()

T = TypeVar("T", bound=GithubObject)
_MAX_PATCH_LINES = 50


class GitHubTool(AbstractTool):
    _operations_path = Path(__file__).parent / "operations.yaml"

    @property
    def name(self) -> str:
        return "github"

    @property
    def description(self) -> str:
        base = "GitHub — issues, pull requests, releases, and CI workflows"
        repos = self.config.get("repositories", [])
        if not repos:
            return base
        lines = [base, "Available repositories:"]
        for r in repos:
            desc = r.get("description", "")
            desc_str = f" — {desc}" if desc else ""
            lines.append(f"  - {r['name']}{desc_str}")
        return "\n".join(lines)

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._default_org: str = config.get("default_org", "")
        self._gh: Github | None = None

    def _get_client(self) -> Github:
        if self._gh is None:
            self._gh = Github(self.config["token"])
        return self._gh

    def _parse_repo_name(self, repo: str) -> str:
        """Expand short repo names using default_org config."""
        if "/" in repo:
            return repo
        if self._default_org:
            return f"{self._default_org}/{repo}"
        return repo

    def _repo(self, repo: str) -> Repository:
        return self._get_client().get_repo(self._parse_repo_name(repo))

    # -- dispatch -------------------------------------------------------

    def run(self, operation: str, **kwargs: Any) -> ToolOperationResult:
        _logger.info("github_operation", operation=operation, kwargs=kwargs)
        try:
            match operation:
                case "github_list_issues":
                    return self._list_issues(**kwargs)
                case "github_create_issue":
                    return self._create_issue(**kwargs)
                case "github_list_prs":
                    return self._list_prs(**kwargs)
                case "github_get_pr":
                    return self._get_pr(**kwargs)
                case "github_get_pr_files":
                    return self._get_pr_files(**kwargs)
                case "github_merge_pr":
                    return self._merge_pr(**kwargs)
                case "github_add_comment":
                    return self._add_comment(**kwargs)
                case "github_list_releases":
                    return self._list_releases(**kwargs)
                case "github_get_release":
                    return self._get_release(**kwargs)
                case "github_publish_release":
                    return self._publish_release(**kwargs)
                case "github_list_workflows":
                    return self._list_workflows(**kwargs)
                case "github_get_workflow_runs":
                    return self._get_workflow_runs(**kwargs)
                case "github_get_workflow_run_jobs":
                    return self._get_workflow_run_jobs(**kwargs)
                case _:
                    return ToolOperationResult(
                        tool_operation_call_id="",
                        content=f"Unknown operation: {operation}",
                        success=False,
                    )
        except GithubException as exc:
            _logger.error("github_api_error", status=exc.status, data=exc.data)
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"GitHub API error ({exc.status}): {exc.data}",
                success=False,
            )

    # -- project resolution for approval --------------------------------

    def resolve_project(self, operation: str, **kwargs: Any) -> str | None:
        repo = kwargs.get("repo")
        if not repo:
            return None
        return self._parse_repo_name(repo)

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _collect(paginated: PaginatedList[T], limit: int) -> list[T]:
        """Iterate a PyGithub PaginatedList up to *limit* items."""
        items: list[T] = []
        page: Iterator[T] = iter(paginated)
        for _ in range(limit):
            try:
                items.append(next(page))
            except StopIteration:
                break
        return items

    @staticmethod
    def _truncate_patch(patch: str | None) -> str:
        if not patch:
            return "(no diff)"
        lines = patch.splitlines()
        if len(lines) <= _MAX_PATCH_LINES:
            return patch
        truncated = "\n".join(lines[:_MAX_PATCH_LINES])
        remaining = len(lines) - _MAX_PATCH_LINES
        return f"{truncated}\n... ({remaining} more lines)"

    # -- operations: issues ---------------------------------------------

    def _list_issues(
        self,
        repo: str,
        state: str = "open",
        labels: list[str] | None = None,
        limit: int = 20,
        **_: Any,
    ) -> ToolOperationResult:
        repository = self._repo(repo)
        kwargs: dict[str, Any] = {"state": state}
        if labels:
            kwargs["labels"] = [repository.get_label(name) for name in labels]

        raw_issues = self._collect(repository.get_issues(**kwargs), limit * 2)
        # filter out pull requests — GitHub API returns PRs as issues
        issues = [i for i in raw_issues if i.pull_request is None][:limit]

        if not issues:
            return ToolOperationResult(tool_operation_call_id="", content="No issues found.")

        lines = [f"Found {len(issues)} issue(s) in {repository.full_name}:"]
        for issue in issues:
            assignee = issue.assignee.login if issue.assignee else "unassigned"
            label_str = ", ".join(lb.name for lb in issue.labels) if issue.labels else ""
            suffix = f" [{label_str}]" if label_str else ""
            lines.append(f"- #{issue.number}: {issue.title} ({issue.state}, {assignee}){suffix}")
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _create_issue(
        self,
        repo: str,
        title: str,
        body: str | None = None,
        labels: list[str] | None = None,
        **_: Any,
    ) -> ToolOperationResult:
        repository = self._repo(repo)
        kwargs: dict[str, Any] = {"title": title}
        if body:
            kwargs["body"] = body
        if labels:
            kwargs["labels"] = labels
        issue = repository.create_issue(**kwargs)
        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Created issue #{issue.number}: {issue.title}\n{issue.html_url}",
        )

    # -- operations: pull requests --------------------------------------

    def _list_prs(
        self,
        repo: str,
        state: str = "open",
        limit: int = 20,
        **_: Any,
    ) -> ToolOperationResult:
        repository = self._repo(repo)
        prs = self._collect(repository.get_pulls(state=state), limit)

        if not prs:
            return ToolOperationResult(tool_operation_call_id="", content="No pull requests found.")

        lines = [f"Found {len(prs)} PR(s) in {repository.full_name}:"]
        for pr in prs:
            author = pr.user.login if pr.user else "unknown"
            lines.append(f"- #{pr.number}: {pr.title} ({pr.state}, by {author})")
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _get_pr(self, repo: str, pr_number: int, **_: Any) -> ToolOperationResult:
        pr = self._repo(repo).get_pull(pr_number)
        mergeable = "yes" if pr.mergeable else ("no" if pr.mergeable is False else "unknown")
        lines = [
            f"#{pr.number}: {pr.title}",
            f"State: {pr.state}",
            f"Author: {pr.user.login if pr.user else 'unknown'}",
            f"Base: {pr.base.ref} <- Head: {pr.head.ref}",
            f"Mergeable: {mergeable}",
            f"Changes: +{pr.additions} -{pr.deletions} ({pr.changed_files} files)",
            f"URL: {pr.html_url}",
        ]
        if pr.body:
            lines.append(f"Description: {pr.body}")
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _get_pr_files(self, repo: str, pr_number: int, **_: Any) -> ToolOperationResult:
        pr = self._repo(repo).get_pull(pr_number)
        files = list(pr.get_files())

        if not files:
            return ToolOperationResult(
                tool_operation_call_id="", content="No files changed in this PR."
            )

        lines = [f"Files changed in #{pr_number} ({len(files)} files):"]
        for f in files:
            patch = self._truncate_patch(f.patch)
            lines.append(f"\n--- {f.filename} ({f.status}, +{f.additions} -{f.deletions})")
            lines.append(patch)
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _merge_pr(
        self,
        repo: str,
        pr_number: int,
        commit_message: str | None = None,
        **_: Any,
    ) -> ToolOperationResult:
        pr = self._repo(repo).get_pull(pr_number)

        if pr.merged:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"PR #{pr_number} is already merged.",
                success=False,
            )
        if pr.mergeable is False:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"PR #{pr_number} is not mergeable. Resolve conflicts first.",
                success=False,
            )

        merge_kwargs: dict[str, Any] = {"merge_method": "squash"}
        if commit_message:
            merge_kwargs["commit_message"] = commit_message

        result = pr.merge(**merge_kwargs)
        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Merged PR #{pr_number}: {result.message} (sha: {result.sha[:8]})",
        )

    # -- operations: comments -------------------------------------------

    def _add_comment(self, repo: str, number: int, body: str, **_: Any) -> ToolOperationResult:
        repository = self._repo(repo)
        issue = repository.get_issue(number)
        comment = issue.create_comment(body)
        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Comment added to #{number}: {comment.html_url}",
        )

    # -- operations: releases -------------------------------------------

    def _list_releases(self, repo: str, limit: int = 10, **_: Any) -> ToolOperationResult:
        repository = self._repo(repo)
        releases = self._collect(repository.get_releases(), limit)

        if not releases:
            return ToolOperationResult(tool_operation_call_id="", content="No releases found.")

        lines = [f"Releases in {repository.full_name}:"]
        for rel in releases:
            flags = []
            if rel.draft:
                flags.append("draft")
            if rel.prerelease:
                flags.append("pre-release")
            flag_str = f" ({', '.join(flags)})" if flags else ""
            lines.append(f"- {rel.tag_name}: {rel.title or '(no title)'}{flag_str}")
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _get_release(self, repo: str, tag: str, **_: Any) -> ToolOperationResult:
        repository = self._repo(repo)
        release = repository.get_release(tag)
        flags = []
        if release.draft:
            flags.append("draft")
        if release.prerelease:
            flags.append("pre-release")
        lines = [
            f"Release: {release.tag_name}",
            f"Title: {release.title or '(no title)'}",
            f"Author: {release.author.login if release.author else 'unknown'}",
            f"Published: {release.published_at or 'not published'}",
            f"Flags: {', '.join(flags) if flags else 'none'}",
            f"URL: {release.html_url}",
        ]
        if release.body:
            lines.append(f"Notes: {release.body}")
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _publish_release(self, repo: str, tag: str, **_: Any) -> ToolOperationResult:
        repository = self._repo(repo)
        release = repository.get_release(tag)

        if not release.draft:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"Release {tag} is not a draft — nothing to publish.",
                success=False,
            )

        release.update_release(
            name=release.title or tag,
            message=release.body or "",
            draft=False,
            prerelease=True,
        )
        return ToolOperationResult(
            tool_operation_call_id="",
            content=f"Published {tag} as pre-release.",
        )

    # -- operations: workflows ------------------------------------------

    def _list_workflows(self, repo: str, **_: Any) -> ToolOperationResult:
        repository = self._repo(repo)
        workflows = list(repository.get_workflows())

        if not workflows:
            return ToolOperationResult(tool_operation_call_id="", content="No workflows found.")

        lines = [f"Workflows in {repository.full_name}:"]
        for wf in workflows:
            lines.append(f"- [{wf.id}] {wf.name} ({wf.state})")
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _get_workflow_runs(
        self,
        repo: str,
        workflow_id: int,
        branch: str | None = None,
        status: str | None = None,
        limit: int = 10,
        **_: Any,
    ) -> ToolOperationResult:
        repository = self._repo(repo)
        workflow = repository.get_workflow(workflow_id)

        run_kwargs: dict[str, Any] = {}
        if branch:
            run_kwargs["branch"] = branch
        if status:
            run_kwargs["status"] = status

        runs = self._collect(workflow.get_runs(**run_kwargs), limit)

        if not runs:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"No runs found for workflow '{workflow.name}'.",
            )

        lines = [f"Runs for workflow '{workflow.name}':"]
        for run in runs:
            branch_name = run.head_branch or "unknown"
            lines.append(
                f"- [{run.id}] {run.display_title} "
                f"({run.status}/{run.conclusion or 'pending'}, branch: {branch_name})"
            )
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))

    def _get_workflow_run_jobs(self, repo: str, run_id: int, **_: Any) -> ToolOperationResult:
        repository = self._repo(repo)
        run = repository.get_workflow_run(run_id)
        jobs = list(run.jobs())

        if not jobs:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"No jobs found for run {run_id}.",
            )

        lines = [f"Jobs for run {run_id} ({run.display_title}):"]
        for job in jobs:
            lines.append(f"\n  {job.name} — {job.status}/{job.conclusion or 'pending'}")
            for step in job.steps:
                marker = "x" if step.conclusion == "failure" else " "
                lines.append(f"    [{marker}] {step.name} ({step.conclusion or step.status})")
        return ToolOperationResult(tool_operation_call_id="", content="\n".join(lines))
