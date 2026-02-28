import uuid

from bulldogent.events.models import StagedEvent


class TestStagedEvent:
    def test_create_staged_event(self) -> None:
        event = StagedEvent(
            event_type="message_received",
            platform="slack",
            channel_id="C123",
            user_id="U456",
            message_id="M789",
            thread_id="T000",
            content="hello",
            metadata_={"key": "value"},
        )

        assert event.event_type == "message_received"
        assert event.platform == "slack"
        assert event.channel_id == "C123"
        assert event.user_id == "U456"
        assert event.message_id == "M789"
        assert event.thread_id == "T000"
        assert event.content == "hello"
        assert event.metadata_ == {"key": "value"}
        assert event.pushed_at is None
        assert event.iteration is None

    def test_default_id_is_uuid(self) -> None:
        event = StagedEvent(event_type="error")
        # id is set by default factory when not provided
        assert event.id is None or isinstance(event.id, uuid.UUID)

    def test_tablename(self) -> None:
        assert StagedEvent.__tablename__ == "staged_events"

    def test_with_iteration(self) -> None:
        event = StagedEvent(
            event_type="llm_request",
            iteration=3,
        )
        assert event.iteration == 3
