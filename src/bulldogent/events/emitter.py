from __future__ import annotations

import queue
import threading
from typing import Any

import structlog
from sqlalchemy.orm import Session

from bulldogent.events.models import StagedEvent
from bulldogent.events.types import EventType
from bulldogent.util.db import get_engine

_logger = structlog.get_logger()

_BATCH_SIZE = 100
_QUEUE_MAX = 10_000
_SHUTDOWN_TIMEOUT = 10
_SENTINEL = object()


class EventEmitter:
    def __init__(self) -> None:
        self._queue: queue.Queue[StagedEvent | object] = queue.Queue(maxsize=_QUEUE_MAX)
        self._thread = threading.Thread(target=self._drain, name="event-emitter", daemon=True)
        self._thread.start()

    def emit(
        self,
        event_type: EventType,
        *,
        platform: str = "",
        channel_id: str = "",
        user_id: str = "",
        message_id: str = "",
        thread_id: str = "",
        iteration: int | None = None,
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = StagedEvent(
            event_type=event_type.value,
            platform=platform,
            channel_id=channel_id,
            user_id=user_id,
            message_id=message_id,
            thread_id=thread_id,
            iteration=iteration,
            content=content,
            metadata_=metadata or {},
        )
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            _logger.warning("event_queue_full", event_type=event_type.value)

    def shutdown(self) -> None:
        try:
            self._queue.put(_SENTINEL, timeout=_SHUTDOWN_TIMEOUT)
        except queue.Full:
            _logger.warning("event_emitter_shutdown_queue_full")
            return
        self._thread.join(timeout=_SHUTDOWN_TIMEOUT)

    def _drain(self) -> None:
        while True:
            batch: list[StagedEvent] = []
            try:
                item = self._queue.get(block=True)
                if item is _SENTINEL:
                    self._flush(batch)
                    return
                batch.append(item)  # type: ignore[arg-type]

                while len(batch) < _BATCH_SIZE:
                    try:
                        item = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    if item is _SENTINEL:
                        self._flush(batch)
                        return
                    batch.append(item)  # type: ignore[arg-type]

                self._flush(batch)
            except Exception:
                _logger.exception("event_emitter_drain_error")

    @staticmethod
    def _flush(batch: list[StagedEvent]) -> None:
        if not batch:
            return
        try:
            with Session(get_engine()) as session:
                session.add_all(batch)
                session.commit()
        except Exception:
            _logger.exception("event_emitter_flush_error", count=len(batch))
