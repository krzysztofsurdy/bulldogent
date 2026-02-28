import time
from unittest.mock import MagicMock, patch

from bulldogent.events.emitter import EventEmitter
from bulldogent.events.types import EventType


class TestEventEmitter:
    @patch("bulldogent.events.emitter.get_engine")
    def test_emit_writes_to_db(self, mock_get_engine: MagicMock) -> None:
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch("bulldogent.events.emitter.Session", return_value=mock_session):
            emitter = EventEmitter()
            emitter.emit(
                EventType.MESSAGE_RECEIVED,
                platform="slack",
                channel_id="C1",
                user_id="U1",
                message_id="M1",
            )
            time.sleep(0.1)
            emitter.shutdown()

        mock_session.add_all.assert_called()
        mock_session.commit.assert_called()
        batch = mock_session.add_all.call_args[0][0]
        assert len(batch) >= 1
        assert batch[0].event_type == "message_received"
        assert batch[0].platform == "slack"

    @patch("bulldogent.events.emitter.get_engine")
    def test_queue_full_drops_event(self, mock_get_engine: MagicMock) -> None:
        mock_get_engine.return_value = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with (
            patch("bulldogent.events.emitter._QUEUE_MAX", 1),
            patch("bulldogent.events.emitter.Session", return_value=mock_session),
        ):
            emitter = EventEmitter()
            # First emit fills the queue (drain thread may or may not have started)
            emitter.emit(EventType.MESSAGE_RECEIVED, platform="slack")
            # Rapidly emit more — at least one should be dropped when queue is full
            for _i in range(20):
                emitter.emit(EventType.ERROR, platform="slack")

            emitter.shutdown()

        # The emitter should not raise; some events may have been dropped

    @patch("bulldogent.events.emitter.get_engine")
    def test_shutdown_flushes_remaining(self, mock_get_engine: MagicMock) -> None:
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch("bulldogent.events.emitter.Session", return_value=mock_session):
            emitter = EventEmitter()
            for i in range(5):
                emitter.emit(
                    EventType.TOOL_EXECUTED,
                    platform="slack",
                    metadata={"index": i},
                )
            emitter.shutdown()

        # All events should have been flushed
        total_flushed = sum(len(call[0][0]) for call in mock_session.add_all.call_args_list)
        assert total_flushed == 5

    @patch("bulldogent.events.emitter.get_engine")
    def test_batching(self, mock_get_engine: MagicMock) -> None:
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch("bulldogent.events.emitter.Session", return_value=mock_session):
            emitter = EventEmitter()
            for _i in range(150):
                emitter.emit(EventType.LLM_REQUEST, platform="slack")
            time.sleep(0.3)
            emitter.shutdown()

        # All 150 should be flushed (possibly in multiple batches)
        total_flushed = sum(len(call[0][0]) for call in mock_session.add_all.call_args_list)
        assert total_flushed == 150

    def test_emit_with_metadata(self) -> None:
        with (
            patch("bulldogent.events.emitter.get_engine"),
            patch("bulldogent.events.emitter.Session") as mock_session_cls,
        ):
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = mock_session

            emitter = EventEmitter()
            emitter.emit(
                EventType.TOOL_EXECUTED,
                platform="discord",
                metadata={"tool": "jira_search", "success": True},
            )
            time.sleep(0.1)
            emitter.shutdown()

            batch = mock_session.add_all.call_args[0][0]
            assert batch[0].metadata_ == {"tool": "jira_search", "success": True}
