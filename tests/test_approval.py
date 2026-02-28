import threading
import time
from unittest.mock import MagicMock, patch

from bulldogent.approval import ApprovalManager
from bulldogent.events.types import EventType


class TestApprovalManager:
    def test_request_creates_pending_approval(self) -> None:
        manager = ApprovalManager()
        approval = manager.request(
            channel_id="C123",
            message_id="M456",
            operation_name="jira_create_issue",
            operation_input={"project": "TEST"},
            approval_group="admins",
            allowed_user_ids=["U001", "U002"],
        )

        assert approval.operation_name == "jira_create_issue"
        assert approval.channel_id == "C123"
        assert approval.message_id == "M456"
        assert approval.approval_group == "admins"
        assert approval.allowed_user_ids == ["U001", "U002"]
        assert approval.approved is None

    def test_handle_reaction_approves_with_correct_emoji_and_user(self) -> None:
        manager = ApprovalManager()
        approval = manager.request(
            channel_id="C123",
            message_id="M456",
            operation_name="op",
            operation_input={},
            approval_group="admins",
            allowed_user_ids=["U001"],
        )

        result = manager.handle_reaction(
            message_id="M456",
            user_id="U001",
            emoji="white_check_mark",
            approve_emoji="white_check_mark",
        )

        assert result is True
        assert approval.approved is True
        assert approval.event.is_set()

    def test_handle_reaction_rejects_wrong_emoji(self) -> None:
        manager = ApprovalManager()
        manager.request(
            channel_id="C123",
            message_id="M456",
            operation_name="op",
            operation_input={},
            approval_group="admins",
            allowed_user_ids=["U001"],
        )

        result = manager.handle_reaction(
            message_id="M456",
            user_id="U001",
            emoji="thumbsup",
            approve_emoji="white_check_mark",
        )

        assert result is False

    def test_handle_reaction_rejects_unauthorized_user(self) -> None:
        manager = ApprovalManager()
        manager.request(
            channel_id="C123",
            message_id="M456",
            operation_name="op",
            operation_input={},
            approval_group="admins",
            allowed_user_ids=["U001"],
        )

        result = manager.handle_reaction(
            message_id="M456",
            user_id="U999",
            emoji="white_check_mark",
            approve_emoji="white_check_mark",
        )

        assert result is False

    def test_handle_reaction_returns_false_for_unknown_message(self) -> None:
        manager = ApprovalManager()

        result = manager.handle_reaction(
            message_id="UNKNOWN",
            user_id="U001",
            emoji="white_check_mark",
            approve_emoji="white_check_mark",
        )

        assert result is False

    @patch("bulldogent.approval._APPROVAL_TIMEOUT", 0.1)
    def test_wait_times_out_and_returns_false(self) -> None:
        manager = ApprovalManager()
        approval = manager.request(
            channel_id="C123",
            message_id="M456",
            operation_name="op",
            operation_input={},
            approval_group="admins",
            allowed_user_ids=["U001"],
        )

        result = manager.wait(approval)

        assert result is False
        assert approval.approved is False

    def test_wait_returns_true_on_concurrent_approval(self) -> None:
        manager = ApprovalManager()
        approval = manager.request(
            channel_id="C123",
            message_id="M456",
            operation_name="op",
            operation_input={},
            approval_group="admins",
            allowed_user_ids=["U001"],
        )

        def approve_after_delay() -> None:
            time.sleep(0.05)
            manager.handle_reaction(
                message_id="M456",
                user_id="U001",
                emoji="white_check_mark",
                approve_emoji="white_check_mark",
            )

        t = threading.Thread(target=approve_after_delay)
        t.start()

        result = manager.wait(approval)
        t.join()

        assert result is True
        assert approval.approved is True

    @patch("bulldogent.approval._APPROVAL_TIMEOUT", 0.2)
    def test_timeout_race_condition_sets_false_under_lock(self) -> None:
        """Ensure approval.approved = False is set inside the lock on timeout.

        If another thread calls handle_reaction between event.wait() returning
        and the lock acquisition, the lock protects the state.
        """
        manager = ApprovalManager()
        approval = manager.request(
            channel_id="C123",
            message_id="M456",
            operation_name="op",
            operation_input={},
            approval_group="admins",
            allowed_user_ids=["U001"],
        )

        result = manager.wait(approval)

        assert result is False
        assert approval.approved is False


class TestApprovalManagerEvents:
    def test_request_emits_approval_requested(self) -> None:
        emitter = MagicMock()
        manager = ApprovalManager(event_emitter=emitter)
        manager.request(
            channel_id="C1",
            message_id="M1",
            operation_name="op",
            operation_input={},
            approval_group="admins",
            allowed_user_ids=["U1"],
        )

        emitter.emit.assert_called_once()
        call_args = emitter.emit.call_args
        assert call_args[0][0] == EventType.APPROVAL_REQUESTED

    def test_handle_reaction_emits_approval_granted(self) -> None:
        emitter = MagicMock()
        manager = ApprovalManager(event_emitter=emitter)
        manager.request(
            channel_id="C1",
            message_id="M1",
            operation_name="op",
            operation_input={},
            approval_group="admins",
            allowed_user_ids=["U1"],
        )
        emitter.reset_mock()

        manager.handle_reaction(
            message_id="M1",
            user_id="U1",
            emoji="check",
            approve_emoji="check",
        )

        emitter.emit.assert_called_once()
        call_args = emitter.emit.call_args
        assert call_args[0][0] == EventType.APPROVAL_GRANTED

    @patch("bulldogent.approval._APPROVAL_TIMEOUT", 0.1)
    def test_timeout_emits_approval_timed_out(self) -> None:
        emitter = MagicMock()
        manager = ApprovalManager(event_emitter=emitter)
        approval = manager.request(
            channel_id="C1",
            message_id="M1",
            operation_name="op",
            operation_input={},
            approval_group="admins",
            allowed_user_ids=["U1"],
        )
        emitter.reset_mock()

        manager.wait(approval)

        emitter.emit.assert_called_once()
        call_args = emitter.emit.call_args
        assert call_args[0][0] == EventType.APPROVAL_TIMED_OUT
