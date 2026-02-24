from enum import StrEnum


class EventType(StrEnum):
    MESSAGE_RECEIVED = "message_received"
    BASELINE_CONTEXT_INJECTED = "baseline_context_injected"
    LLM_REQUEST = "llm_request"
    TOOL_CALLS_REQUESTED = "tool_calls_requested"
    TOOL_EXECUTED = "tool_executed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_TIMED_OUT = "approval_timed_out"
    LLM_RESPONSE = "llm_response"
    LEARNING_STORED = "learning_stored"
    ERROR = "error"
