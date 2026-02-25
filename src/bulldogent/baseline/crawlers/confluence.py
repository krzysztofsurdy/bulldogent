import re
from typing import Any

import structlog

from bulldogent.baseline.chunker import Chunker
from bulldogent.baseline.config import ConfluenceSourceConfig
from bulldogent.baseline.crawlers import AbstractCrawler
from bulldogent.baseline.types import Chunk

_logger = structlog.get_logger()


class ConfluenceCrawler(AbstractCrawler):
    """Crawl Confluence spaces for pages."""

    def __init__(
        self,
        source_config: ConfluenceSourceConfig,
        tool_config: dict[str, Any],
        chunker: Chunker,
    ) -> None:
        super().__init__(source_config, tool_config, chunker)
        self._source_config: ConfluenceSourceConfig = source_config

    def crawl(self) -> list[Chunk]:
        from atlassian import Confluence

        cfg = self._tool_config.get("confluence", {})
        url = cfg.get("url", "")
        username = cfg.get("username", "")
        api_token = cfg.get("api_token", "")

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
        spaces = self._source_config.spaces
        max_pages = self._source_config.max_pages

        for space_key in spaces:
            _logger.info("indexing_confluence_space", space=space_key)
            try:
                pages = client.get_all_pages_from_space(
                    space_key,
                    start=0,
                    limit=max_pages,
                    expand="body.storage",
                )
            except Exception:
                # Confluence API errors are varied; log and continue to next space
                _logger.exception("confluence_space_crawl_failed", space=space_key)
                continue

            for page in pages:
                page_id = page.get("id", "")
                title = page.get("title", "Untitled")
                body_html = page.get("body", {}).get("storage", {}).get("value", "")
                body_text = _html_to_text(body_html)

                if not body_text.strip():
                    continue

                page_url = f"{url.rstrip('/')}/wiki/spaces/{space_key}/pages/{page_id}"
                page_chunks = self._chunker.chunk_text(
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
