import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bulldogent.baseline.models import Base


class StagedEvent(Base):
    __tablename__ = "staged_events"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, server_default="")
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    message_id: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    thread_id: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    iteration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_staged_events_event_type", "event_type"),
        Index("ix_staged_events_created_at", "created_at"),
        Index("ix_staged_events_pushed_at", "pushed_at"),
    )
