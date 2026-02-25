import uuid
from typing import Any

import structlog
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from bulldogent.baseline.chunker import Chunker
from bulldogent.baseline.config import BaselineConfig
from bulldogent.baseline.crawlers import AbstractCrawler
from bulldogent.baseline.crawlers.confluence import ConfluenceCrawler
from bulldogent.baseline.crawlers.github import GitHubCrawler
from bulldogent.baseline.crawlers.jira import JiraCrawler
from bulldogent.baseline.crawlers.local import LocalCrawler
from bulldogent.baseline.models import Knowledge
from bulldogent.baseline.summarizer import FileSummarizer
from bulldogent.baseline.types import Chunk
from bulldogent.embedding.provider import AbstractEmbeddingProvider
from bulldogent.util import PROJECT_ROOT, load_yaml_config
from bulldogent.util.db import get_session

_logger = structlog.get_logger()

_TOOLS_CONFIG_PATH = PROJECT_ROOT / "config" / "tools.yaml"

# Mapping from source name to (crawler class, config attribute name)
_CRAWLER_MAP: dict[str, tuple[type[AbstractCrawler], str]] = {
    "confluence": (ConfluenceCrawler, "confluence"),
    "github": (GitHubCrawler, "github"),
    "jira": (JiraCrawler, "jira"),
    "local": (LocalCrawler, "local"),
}

# Attribute on each source config that indicates whether the source is configured
_SOURCE_CHECKS: dict[str, str] = {
    "confluence": "spaces",
    "github": "repositories",
    "jira": "projects",
    "local": "paths",
}


class BaselineIndexer:
    def __init__(
        self,
        config: BaselineConfig,
        embedding_provider: AbstractEmbeddingProvider,
    ) -> None:
        self._config = config
        self._embedding_provider = embedding_provider
        self._tool_config = load_yaml_config(_TOOLS_CONFIG_PATH)
        self._chunker = Chunker(
            chunk_size=config.chunking.chunk_size,
            overlap=config.chunking.overlap,
        )
        self._summarizer: FileSummarizer | None = None
        if config.summarizer:
            self._summarizer = FileSummarizer(
                api_key=config.summarizer.api_key,
                model=config.summarizer.model,
                api_url=config.summarizer.api_url,
            )

    def _get_crawler(self, source: str) -> AbstractCrawler:
        """Create a crawler instance for the given source name."""
        crawler_cls, config_attr = _CRAWLER_MAP[source]
        source_config: Any = getattr(self._config.sources, config_attr)
        if source == "github":
            return GitHubCrawler(source_config, self._tool_config, self._chunker, self._summarizer)
        return crawler_cls(source_config, self._tool_config, self._chunker)

    def _is_source_configured(self, source: str) -> bool:
        """Check if a source has any items configured."""
        config_attr = _CRAWLER_MAP[source][1]
        source_config = getattr(self._config.sources, config_attr)
        check_attr = _SOURCE_CHECKS[source]
        return bool(getattr(source_config, check_attr))

    def index_all(self) -> None:
        """Run all configured indexing sources."""
        all_chunks: list[Chunk] = []

        for source in _CRAWLER_MAP:
            if self._is_source_configured(source):
                crawler = self._get_crawler(source)
                all_chunks.extend(crawler.crawl())

        if not all_chunks:
            _logger.warning("no_chunks_produced")
            return

        self._store(all_chunks)

    def index_confluence(self) -> None:
        chunks = self._get_crawler("confluence").crawl()
        if chunks:
            self._store(chunks)

    def index_github(self) -> None:
        chunks = self._get_crawler("github").crawl()
        if chunks:
            self._store(chunks)

    def index_jira(self) -> None:
        chunks = self._get_crawler("jira").crawl()
        if chunks:
            self._store(chunks)

    def index_local(self) -> None:
        chunks = self._get_crawler("local").crawl()
        if chunks:
            self._store(chunks)

    # -- storage ------------------------------------------------------------

    def _store(self, chunks: list[Chunk]) -> None:
        _logger.info("storing_chunks", count=len(chunks))

        texts = [c.content for c in chunks]
        embeddings = self._embedding_provider.embed(texts)

        # Determine which sources we're re-indexing and delete old rows
        sources = {c.source for c in chunks}

        try:
            with get_session() as session:
                session.execute(delete(Knowledge).where(Knowledge.source.in_(sources)))

                rows = [
                    Knowledge(
                        id=uuid.uuid4(),
                        source=chunk.source,
                        title=chunk.title,
                        content=chunk.content,
                        url=chunk.url,
                        metadata_=chunk.metadata,
                        embedding=embeddings[i],
                    )
                    for i, chunk in enumerate(chunks)
                ]
                session.add_all(rows)
                session.commit()
        except SQLAlchemyError:
            _logger.exception("indexing_store_failed", sources=list(sources))
            raise

        _logger.info("chunks_stored", count=len(chunks))
