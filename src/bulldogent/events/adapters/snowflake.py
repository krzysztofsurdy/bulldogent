from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, update

from bulldogent.events.config import SnowflakeSinkConfig
from bulldogent.events.models import StagedEvent
from bulldogent.events.sink import AbstractEventSink
from bulldogent.util.db import get_session

_logger = structlog.get_logger()


class SnowflakeSink(AbstractEventSink):
    def __init__(self, config: SnowflakeSinkConfig) -> None:
        self._config = config
        self._conn: Any = None

    def _connect(self) -> Any:
        if self._conn is not None:
            return self._conn

        import snowflake.connector

        self._conn = snowflake.connector.connect(
            account=self._config.account,
            user=self._config.user,
            password=self._config.password,
            warehouse=self._config.warehouse,
            database=self._config.database,
            schema=self._config.schema_name,
            role=self._config.role,
        )
        return self._conn

    def push(self, batch_size: int = 500) -> int:
        total_pushed = 0

        while True:
            with get_session() as session:
                stmt = (
                    select(StagedEvent)
                    .where(StagedEvent.pushed_at.is_(None))
                    .order_by(StagedEvent.created_at)
                    .limit(batch_size)
                )
                rows = session.execute(stmt).scalars().all()

                if not rows:
                    break

                conn = self._connect()
                cursor = conn.cursor()
                try:
                    table = self._config.table
                    insert_sql = (
                        f"INSERT INTO {table} "  # noqa: S608
                        "(id, created_at, event_type, platform, channel_id, "
                        "user_id, message_id, thread_id, iteration, content, metadata) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                    )
                    params = [
                        (
                            str(row.id),
                            row.created_at.isoformat() if row.created_at else None,
                            row.event_type,
                            row.platform,
                            row.channel_id,
                            row.user_id,
                            row.message_id,
                            row.thread_id,
                            row.iteration,
                            row.content,
                            str(row.metadata_),
                        )
                        for row in rows
                    ]
                    cursor.executemany(insert_sql, params)
                finally:
                    cursor.close()

                row_ids = [row.id for row in rows]
                session.execute(
                    update(StagedEvent)
                    .where(StagedEvent.id.in_(row_ids))
                    .values(pushed_at=datetime.now(UTC))
                )
                session.commit()
                total_pushed += len(rows)

                _logger.info("snowflake_batch_pushed", count=len(rows))

        return total_pushed

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
