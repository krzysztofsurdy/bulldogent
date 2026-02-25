from pathlib import Path
from typing import Any

import structlog

from bulldogent.baseline.chunker import Chunker
from bulldogent.baseline.config import LocalSourceConfig
from bulldogent.baseline.crawlers import AbstractCrawler
from bulldogent.baseline.types import Chunk
from bulldogent.util import PROJECT_ROOT

_logger = structlog.get_logger()


class LocalCrawler(AbstractCrawler):
    """Crawl local file system directories for .md and .txt files."""

    def __init__(
        self,
        source_config: LocalSourceConfig,
        tool_config: dict[str, Any],
        chunker: Chunker,
    ) -> None:
        super().__init__(source_config, tool_config, chunker)
        self._source_config: LocalSourceConfig = source_config

    def crawl(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        paths = self._source_config.paths

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

                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    _logger.warning("local_file_read_failed", path=str(file_path))
                    continue

                if not text.strip():
                    continue

                if file_path.is_relative_to(PROJECT_ROOT):
                    relative = file_path.relative_to(PROJECT_ROOT)
                else:
                    relative = file_path
                file_chunks = self._chunker.chunk_text(
                    text=text,
                    source="local",
                    title=file_path.stem,
                    url=str(relative),
                    metadata={"path": str(relative)},
                )
                chunks.extend(file_chunks)

        _logger.info("local_indexed", total_chunks=len(chunks))
        return chunks
