import sys

import structlog

from bulldogent.baseline.config import load_baseline_config
from bulldogent.events.adapters.snowflake import SnowflakeSink
from bulldogent.events.config import EventSinkConfig, SnowflakeSinkConfig
from bulldogent.util.db import configure_engine, init_db

_logger = structlog.get_logger()


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] != "push":
        print("Usage: python -m bulldogent.events push [--batch-size N]")
        sys.exit(1)

    batch_size = 500
    if "--batch-size" in args:
        idx = args.index("--batch-size")
        if idx + 1 < len(args):
            batch_size = int(args[idx + 1])
        else:
            print("--batch-size requires a value")
            sys.exit(1)

    baseline_config = load_baseline_config()
    configure_engine(baseline_config.database_url)
    init_db()

    event_config = EventSinkConfig.load()
    if not event_config.enabled or event_config.sink is None:
        _logger.info("event_sink_disabled")
        return

    if not isinstance(event_config.sink, SnowflakeSinkConfig):
        _logger.error("unsupported_sink_type", sink_type=event_config.sink_type)
        sys.exit(1)

    sink = SnowflakeSink(event_config.sink)
    try:
        total = sink.push(batch_size=batch_size)
        _logger.info("events_pushed", total=total)
    finally:
        sink.close()


if __name__ == "__main__":
    main()
