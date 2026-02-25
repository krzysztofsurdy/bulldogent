import fnmatch
from typing import Any

import structlog
from github import GithubException

from bulldogent.baseline.chunker import Chunker
from bulldogent.baseline.config import GitHubSourceConfig
from bulldogent.baseline.crawlers import AbstractCrawler
from bulldogent.baseline.types import Chunk

_logger = structlog.get_logger()


def _is_sensitive(file_path: str, patterns: list[str]) -> bool:
    """Check if a file path matches any sensitive pattern.

    Patterns without "/" match against the filename only.
    Patterns with "/" match against the full path (e.g. "config/secrets/*").
    """
    name = file_path.rsplit("/", maxsplit=1)[-1]
    for pat in patterns:
        if "/" in pat:
            if fnmatch.fnmatch(file_path, pat):
                return True
        else:
            if fnmatch.fnmatch(name, pat):
                return True
    return False


class GitHubCrawler(AbstractCrawler):
    """Crawl GitHub repositories for READMEs and issues."""

    def __init__(
        self,
        source_config: GitHubSourceConfig,
        tool_config: dict[str, Any],
        chunker: Chunker,
        summarizer: Any | None = None,
    ) -> None:
        super().__init__(source_config, tool_config, chunker)
        self._source_config: GitHubSourceConfig = source_config
        self._summarizer = summarizer

    def crawl(self) -> list[Chunk]:
        from github import Github

        cfg = self._tool_config.get("github", {})
        token = cfg.get("token", "")

        if not token:
            _logger.warning("github_skipped", reason="missing config")
            return []

        client = Github(token)
        default_org = cfg.get("default_org", "")
        global_include = self._source_config.include

        chunks: list[Chunk] = []

        for repo_cfg in self._source_config.repositories:
            repo_name = repo_cfg.name
            include = repo_cfg.include if repo_cfg.include else global_include

            if "/" not in repo_name and default_org:
                full_name = f"{default_org}/{repo_name}"
            else:
                full_name = repo_name
            _logger.info("indexing_github_repo", repo=full_name)

            try:
                repo = client.get_repo(full_name)
            except GithubException:
                _logger.warning("github_repo_not_found", repo=full_name)
                continue

            file_paths: list[str] = []
            for item in include:
                if item == "readme":
                    chunks.extend(self._crawl_readme(repo, full_name))
                elif item == "issues":
                    chunks.extend(self._crawl_github_issues(repo, full_name))
                else:
                    file_paths.append(item)

            summarize = repo_cfg.summarize if repo_cfg.include else True
            if file_paths:
                chunks.extend(self._crawl_repo_files(repo, full_name, file_paths, summarize))

        _logger.info("github_indexed", total_chunks=len(chunks))
        return chunks

    def _crawl_readme(self, repo: Any, full_name: str) -> list[Chunk]:
        try:
            readme = repo.get_readme()
            readme_text = readme.decoded_content.decode("utf-8", errors="replace")
            return self._chunker.chunk_text(
                text=readme_text,
                source="github",
                title=f"{full_name} README",
                url=readme.html_url,
                metadata={"repo": full_name, "file": "README.md"},
            )
        except GithubException:
            _logger.debug("github_no_readme", repo=full_name)
            return []

    def _crawl_repo_files(
        self, repo: Any, full_name: str, file_paths: list[str], summarize: bool = True
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        for file_path in file_paths:
            is_glob = file_path.endswith("/*")
            lookup_path = file_path.rstrip("/*") if is_glob else file_path
            try:
                content = repo.get_contents(lookup_path)
                files = content if isinstance(content, list) else [content]
                for content_file in files:
                    if content_file.type == "dir":
                        continue
                    if _is_sensitive(content_file.path, self._source_config.exclude_patterns):
                        _logger.warning(
                            "github_sensitive_file_skipped",
                            repo=full_name,
                            path=content_file.path,
                        )
                        continue
                    raw = content_file.decoded_content.decode("utf-8", errors="replace")
                    summary = (
                        self._summarize(raw, full_name, content_file.path) if summarize else ""
                    )
                    header = f"Repository: {full_name}\nFile: {content_file.path}"
                    if summary:
                        header += f"\nSummary: {summary}"
                    text = f"{header}\n\n{raw}"
                    file_chunks = self._chunker.chunk_text(
                        text=text,
                        source="github",
                        title=f"{full_name}/{content_file.path}",
                        url=content_file.html_url,
                        metadata={"repo": full_name, "file": content_file.path},
                    )
                    chunks.extend(file_chunks)
                    _logger.debug("github_file_indexed", repo=full_name, path=content_file.path)
            except GithubException:
                _logger.warning("github_file_not_found", repo=full_name, path=file_path)
        return chunks

    def _summarize(self, content: str, repo: str, path: str) -> str:
        """Generate a one-line summary of file content using a small LLM."""
        if self._summarizer is None:
            return ""
        try:
            return str(self._summarizer.summarize(content, repo, path))
        except Exception:
            _logger.debug("github_file_summary_failed", repo=repo, path=path)
            return ""

    def _crawl_github_issues(self, repo: Any, full_name: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        try:
            issues = repo.get_issues(state="all")
            count = 0
            for issue in issues:
                if issue.pull_request is not None:
                    continue
                text = f"{issue.title}\n\n{issue.body or ''}"
                issue_chunks = self._chunker.chunk_text(
                    text=text,
                    source="github",
                    title=f"{full_name}#{issue.number}: {issue.title}",
                    url=issue.html_url,
                    metadata={"repo": full_name, "issue": str(issue.number)},
                )
                chunks.extend(issue_chunks)
                count += 1
                if count >= 200:
                    break
        except GithubException:
            _logger.debug("github_issues_error", repo=full_name)
        return chunks
