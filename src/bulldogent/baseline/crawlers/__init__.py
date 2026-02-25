from abc import ABC, abstractmethod
from typing import Any

from bulldogent.baseline.chunker import Chunker
from bulldogent.baseline.types import Chunk


class AbstractCrawler(ABC):
    """Base class for all baseline knowledge crawlers."""

    def __init__(
        self,
        source_config: Any,
        tool_config: dict[str, Any],
        chunker: Chunker,
    ) -> None:
        self._source_config = source_config
        self._tool_config = tool_config
        self._chunker = chunker

    @abstractmethod
    def crawl(self) -> list[Chunk]:
        """Crawl the data source and return a list of chunks."""
        ...
