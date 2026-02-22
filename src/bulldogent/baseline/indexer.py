import os
import re
from pathlib import Path
from typing import Any

import structlog

from bulldogent.baseline.chunker import chunk_text
from bulldogent.baseline.config import BaselineConfig
from bulldogent.baseline.types import Chunk
from bulldogent.embedding.provider import AbstractEmbeddingProvider
from bulldogent.util import PROJECT_ROOT, load_yaml_config

_logger = structlog.get_logger()

_TOOLS_CONFIG_PATH = PROJECT_ROOT / "config" / "tools.yaml"


class BaselineIndexer:
    def __init__(
        self,
        config: BaselineConfig,
        embedding_provider: AbstractEmbeddingProvider,
    ) -> None:
        self._config = config
        self._embedding_provider = embedding_provider
        self._tool_config = load_yaml_config(_TOOLS_CONFIG_PATH)

    def index_all(self) -> None:
        """Run all configured indexing sources."""
        all_chunks: list[Chunk] = []

        if self._config.sources.confluence.spaces:
            all_chunks.extend(self._crawl_confluence())

        if self._config.sources.github.repositories:
            all_chunks.extend(self._crawl_github())

        if self._config.sources.jira.projects:
            all_chunks.extend(self._crawl_jira())

        if self._config.sources.local.paths:
            all_chunks.extend(self._crawl_local())

        if not all_chunks:
            _logger.warning("no_chunks_produced")
            return

        self._store(all_chunks)

    def index_confluence(self) -> None:
        chunks = self._crawl_confluence()
        if chunks:
            self._store(chunks)

    def index_github(self) -> None:
        chunks = self._crawl_github()
        if chunks:
            self._store(chunks)

    def index_jira(self) -> None:
        chunks = self._crawl_jira()
        if chunks:
            self._store(chunks)

    def index_local(self) -> None:
        chunks = self._crawl_local()
        if chunks:
            self._store(chunks)

    # -- crawlers -----------------------------------------------------------

    def _crawl_confluence(self) -> list[Chunk]:
        from atlassian import Confluence

        cfg = self._tool_config.get("confluence", {})
        url = os.getenv(cfg.get("url_env", ""), "")
        username = os.getenv(cfg.get("username_env", ""), "")
        api_token = os.getenv(cfg.get("api_token_env", ""), "")

        if not url:
            _logger.warning("confluence_skipped", reason="missing config")
            return []

        client = Confluence(
            url=url,
            username=username,
            password=api_token,
            cloud=cfg.get("cloud", True),
        )

        chunks: list[Chunk] = []
        spaces = self._config.sources.confluence.spaces
        max_pages = self._config.sources.confluence.max_pages

        for space_key in spaces:
            _logger.info("indexing_confluence_space", space=space_key)
            pages = client.get_all_pages_from_space(
                space_key,
                start=0,
                limit=max_pages,
                expand="body.storage",
            )

            for page in pages:
                page_id = page.get("id", "")
                title = page.get("title", "Untitled")
                body_html = page.get("body", {}).get("storage", {}).get("value", "")
                body_text = _html_to_text(body_html)

                if not body_text.strip():
                    continue

                page_url = f"{url.rstrip('/')}/wiki/spaces/{space_key}/pages/{page_id}"
                page_chunks = chunk_text(
                    text=body_text,
                    source="confluence",
                    title=title,
                    url=page_url,
                    metadata={"space": space_key, "page_id": str(page_id)},
                )
                chunks.extend(page_chunks)

            _logger.info(
                "confluence_space_indexed",
                space=space_key,
                pages=len(pages),
                chunks=len(chunks),
            )

        return chunks

    def _crawl_github(self) -> list[Chunk]:
        from github import Github

        cfg = self._tool_config.get("github", {})
        token = os.getenv(cfg.get("token_env", ""), "")

        if not token:
            _logger.warning("github_skipped", reason="missing config")
            return []

        client = Github(token)
        default_org = cfg.get("default_org", "")
        repos = self._config.sources.github.repositories
        include = self._config.sources.github.include

        chunks: list[Chunk] = []

        for repo_name in repos:
            if "/" not in repo_name and default_org:
                full_name = f"{default_org}/{repo_name}"
            else:
                full_name = repo_name
            _logger.info("indexing_github_repo", repo=full_name)

            try:
                repo = client.get_repo(full_name)
            except Exception:
                _logger.warning("github_repo_not_found", repo=full_name)
                continue

            if "readme" in include:
                try:
                    readme = repo.get_readme()
                    readme_text = readme.decoded_content.decode("utf-8", errors="replace")
                    readme_chunks = chunk_text(
                        text=readme_text,
                        source="github",
                        title=f"{full_name} README",
                        url=readme.html_url,
                        metadata={"repo": full_name, "file": "README.md"},
                    )
                    chunks.extend(readme_chunks)
                except Exception:
                    _logger.debug("github_no_readme", repo=full_name)

            if "issues" in include:
                chunks.extend(self._crawl_github_issues(repo, full_name))

        _logger.info("github_indexed", total_chunks=len(chunks))
        return chunks

    @staticmethod
    def _crawl_github_issues(repo: Any, full_name: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        try:
            issues = repo.get_issues(state="all")
            count = 0
            for issue in issues:
                if issue.pull_request is not None:
                    continue
                text = f"{issue.title}\n\n{issue.body or ''}"
                issue_chunks = chunk_text(
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
        except Exception:
            _logger.debug("github_issues_error", repo=full_name)
        return chunks

    def _crawl_jira(self) -> list[Chunk]:
        from atlassian import Jira

        cfg = self._tool_config.get("jira", {})
        url = os.getenv(cfg.get("url_env", ""), "")
        username = os.getenv(cfg.get("username_env", ""), "")
        api_token = os.getenv(cfg.get("api_token_env", ""), "")

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
        projects = self._config.sources.jira.projects
        max_issues = self._config.sources.jira.max_issues

        for project_key in projects:
            _logger.info("indexing_jira_project", project=project_key)
            jql = f'project = "{project_key}" ORDER BY updated DESC'
            data = client.jql(jql, limit=max_issues)
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
                issue_chunks = chunk_text(
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

    def _crawl_local(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        paths = self._config.sources.local.paths

        for dir_path_str in paths:
            dir_path = Path(dir_path_str)
            if not dir_path.is_absolute():
                dir_path = PROJECT_ROOT / dir_path

            if not dir_path.exists():
                _logger.warning("local_dir_not_found", path=str(dir_path))
                continue

            _logger.info("indexing_local_dir", path=str(dir_path))

            for file_path in sorted(dir_path.rglob("*")):
                if file_path.suffix not in (".md", ".txt"):
                    continue
                if not file_path.is_file():
                    continue

                text = file_path.read_text(encoding="utf-8", errors="replace")
                if not text.strip():
                    continue

                if file_path.is_relative_to(PROJECT_ROOT):
                    relative = file_path.relative_to(PROJECT_ROOT)
                else:
                    relative = file_path
                file_chunks = chunk_text(
                    text=text,
                    source="local",
                    title=file_path.stem,
                    url=str(relative),
                    metadata={"path": str(relative)},
                )
                chunks.extend(file_chunks)

        _logger.info("local_indexed", total_chunks=len(chunks))
        return chunks

    # -- storage ------------------------------------------------------------

    def _store(self, chunks: list[Chunk]) -> None:
        import chromadb

        _logger.info("storing_chunks", count=len(chunks))

        storage_path = self._config.storage.path
        storage_path.mkdir(parents=True, exist_ok=True)

        client = chromadb.PersistentClient(path=str(storage_path))
        collection = client.get_or_create_collection(
            name="baseline",
            metadata={"hnsw:space": "cosine"},
        )

        texts = [c.content for c in chunks]
        embeddings = self._embedding_provider.embed(texts)

        ids = [f"{c.source}:{c.url}:{i}" for i, c in enumerate(chunks)]
        metadatas = [
            {"source": c.source, "title": c.title, "url": c.url, **c.metadata} for c in chunks
        ]

        # Upsert in batches (ChromaDB limit is ~41666 per call)
        batch_size = 5000
        for i in range(0, len(chunks), batch_size):
            end = i + batch_size
            collection.upsert(
                ids=ids[i:end],
                embeddings=embeddings[i:end],  # type: ignore[arg-type]
                documents=texts[i:end],
                metadatas=metadatas[i:end],  # type: ignore[arg-type]
            )

        _logger.info("chunks_stored", count=len(chunks))


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
