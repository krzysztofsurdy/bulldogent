from typing import Any

import structlog

from bulldogent.baseline.chunker import Chunker
from bulldogent.baseline.config import JiraSourceConfig
from bulldogent.baseline.crawlers import AbstractCrawler
from bulldogent.baseline.types import Chunk

_logger = structlog.get_logger()


class JiraCrawler(AbstractCrawler):
    """Crawl Jira projects for issues."""

    def __init__(
        self,
        source_config: JiraSourceConfig,
        tool_config: dict[str, Any],
        chunker: Chunker,
    ) -> None:
        super().__init__(source_config, tool_config, chunker)
        self._source_config: JiraSourceConfig = source_config

    def crawl(self) -> list[Chunk]:
        from atlassian import Jira

        cfg = self._tool_config.get("jira", {})
        url = cfg.get("url", "")
        username = cfg.get("username", "")
        api_token = cfg.get("api_token", "")

        if not url:
            _logger.warning("jira_skipped", reason="missing config")
            return []

        client = Jira(
            url=url,
            username=username,
            password=api_token,
            cloud=cfg.get("cloud", True),
        )

        chunks: list[Chunk] = []
        projects = self._source_config.projects
        max_issues = self._source_config.max_issues

        for project_key in projects:
            _logger.info("indexing_jira_project", project=project_key)
            try:
                jql = f'project = "{project_key}" ORDER BY updated DESC'
                data = client.jql(jql, limit=max_issues)
            except Exception:
                # Jira/Atlassian client raises varied exceptions; log and continue
                _logger.exception("jira_project_crawl_failed", project=project_key)
                continue

            issues: list[Any] = (data or {}).get("issues", [])

            for issue in issues:
                key = issue["key"]
                fields = issue["fields"]
                summary = fields.get("summary", "")
                description = fields.get("description") or ""
                text = f"{summary}\n\n{description}"

                if not text.strip():
                    continue

                issue_url = f"{url.rstrip('/')}/browse/{key}"
                issue_chunks = self._chunker.chunk_text(
                    text=text,
                    source="jira",
                    title=f"{key}: {summary}",
                    url=issue_url,
                    metadata={"project": project_key, "issue_key": key},
                )
                chunks.extend(issue_chunks)

            _logger.info(
                "jira_project_indexed",
                project=project_key,
                issues=len(issues),
                chunks=len(chunks),
            )

        return chunks
