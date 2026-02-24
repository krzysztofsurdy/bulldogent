import sys

import structlog

from bulldogent.events.models import StagedEvent
from bulldogent.util.db import get_session

_logger = structlog.get_logger()


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] != "status":
        print("Usage: python -m bulldogent.events status")
        sys.exit(1)

    with get_session() as session:
        total = session.query(StagedEvent).count()
        _logger.info("staged_events_count", total=total)


if __name__ == "__main__":
    main()
