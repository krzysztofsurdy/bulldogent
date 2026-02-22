import sys

import structlog

from bulldogent.baseline.config import load_baseline_config
from bulldogent.baseline.indexer import BaselineIndexer
from bulldogent.embedding import create_embedding_provider

_logger = structlog.get_logger()

_VALID_SOURCES = ("confluence", "github", "jira", "local")


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] != "index":
        sources = ",".join(_VALID_SOURCES)
        print(f"Usage: python -m bulldogent.baseline index [--source {{{sources}}}]")
        sys.exit(1)

    source: str | None = None
    if "--source" in args:
        idx = args.index("--source")
        if idx + 1 < len(args):
            source = args[idx + 1]
            if source not in _VALID_SOURCES:
                print(f"Invalid source: {source}. Must be one of: {', '.join(_VALID_SOURCES)}")
                sys.exit(1)
        else:
            print("--source requires a value")
            sys.exit(1)

    config = load_baseline_config()
    embedding_provider = create_embedding_provider(config.embedding)
    indexer = BaselineIndexer(config, embedding_provider)

    if source:
        _logger.info("indexing_source", source=source)
        getattr(indexer, f"index_{source}")()
    else:
        _logger.info("indexing_all_sources")
        indexer.index_all()

    _logger.info("indexing_complete")


if __name__ == "__main__":
    main()
