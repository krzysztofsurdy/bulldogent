from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from bulldogent.events.types import EventType

if TYPE_CHECKING:
    from bulldogent.events.emitter import EventEmitter

_logger = structlog.get_logger()

_APPROVAL_TIMEOUT = 300  # 5 minutes


@dataclass
class PendingApproval:
    operation_name: str
    operation_input: dict[str, Any]
    approval_group: str
    allowed_user_ids: list[str]
    channel_id: str
    message_id: str
    event: threading.Event = field(default_factory=threading.Event)
    approved: bool | None = None


class ApprovalManager:
    def __init__(self, event_emitter: EventEmitter | None = None) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, PendingApproval] = {}
        self._event_emitter: EventEmitter | None = event_emitter

    def request(
        self,
        channel_id: str,
        message_id: str,
        operation_name: str,
        operation_input: dict[str, Any],
        approval_group: str,
        allowed_user_ids: list[str],
    ) -> PendingApproval:
        approval = PendingApproval(
            operation_name=operation_name,
            operation_input=operation_input,
            approval_group=approval_group,
            allowed_user_ids=allowed_user_ids,
            channel_id=channel_id,
            message_id=message_id,
        )
        with self._lock:
            self._pending[message_id] = approval

        _logger.info(
            "approval_requested",
            operation=operation_name,
            group=approval_group,
            message_id=message_id,
        )
        if self._event_emitter:
            self._event_emitter.emit(
                EventType.APPROVAL_REQUESTED,
                channel_id=channel_id,
                message_id=message_id,
                metadata={"operation": operation_name, "group": approval_group},
            )
        return approval

    def wait(self, approval: PendingApproval) -> bool:
        signaled = approval.event.wait(timeout=_APPROVAL_TIMEOUT)

        with self._lock:
            self._pending.pop(approval.message_id, None)
            if not signaled:
                _logger.info("approval_timed_out", message_id=approval.message_id)
                if self._event_emitter:
                    self._event_emitter.emit(
                        EventType.APPROVAL_TIMED_OUT,
                        channel_id=approval.channel_id,
                        message_id=approval.message_id,
                        metadata={"operation": approval.operation_name},
                    )
                approval.approved = False

        return approval.approved or False

    def handle_reaction(
        self,
        message_id: str,
        user_id: str,
        emoji: str,
        approve_emoji: str,
    ) -> bool:
        with self._lock:
            approval = self._pending.get(message_id)

        if approval is None:
            return False

        if emoji != approve_emoji:
            return False

        if user_id not in approval.allowed_user_ids:
            _logger.info(
                "approval_unauthorized_user",
                user=user_id,
                message_id=message_id,
            )
            return False

        approval.approved = True
        approval.event.set()
        _logger.info("approval_granted", message_id=message_id, user=user_id)
        if self._event_emitter:
            self._event_emitter.emit(
                EventType.APPROVAL_GRANTED,
                channel_id=approval.channel_id,
                message_id=message_id,
                user_id=user_id,
                metadata={"operation": approval.operation_name},
            )
        return True
