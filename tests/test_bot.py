from unittest.mock import MagicMock, patch

from bulldogent.approval import ApprovalManager
from bulldogent.bot import Bot
from bulldogent.events.types import EventType
from bulldogent.llm.provider.types import (
    Message,
    MessageRole,
    TextResponse,
    TokenUsage,
    ToolUseResponse,
)
from bulldogent.llm.tool.types import ToolOperationCall, ToolOperationResult
from bulldogent.messaging.platform.types import PlatformMessage, PlatformUser

_SYS_PROMPT = "You are {bot_name} at {organization}. Date: {current_date}. Tools: {tool_inventory}"

_MESSAGES: dict[str, str] = {
    "bot_name": "Tokyo",
    "organization": "test-org",
    "system_prompt": _SYS_PROMPT,
    "approval_request": "Approve {operation_name} {operation_input}"
    " {group} {mentions} {approve_emoji}",
    "approval_timeout": "Timed out.",
    "approval_group_empty": "Group {group} has no members.",
    "loop_exhausted_hint": "Max {max_iterations} reached.",
    "unexpected_response": "Unexpected.",
    "error_generic": "Error.",
}


def _make_platform_config() -> MagicMock:
    config = MagicMock()
    config.llm_provider = "openai"
    config.reaction_handling = "eyes"
    config.reaction_error = "x"
    config.reaction_approval = "white_check_mark"
    config.reaction_learn = "brain"
    config.approval_groups = {"admins": ["U001"]}
    return config


def _make_message(
    text: str = "hello",
    thread_id: str | None = None,
    message_id: str = "M1",
    channel_id: str = "C1",
) -> PlatformMessage:
    return PlatformMessage(
        id=message_id,
        channel_id=channel_id,
        text=text,
        user=PlatformUser(user_id="U100", name="alice", raw={}),
        timestamp=1000.0,
        thread_id=thread_id,
        raw={},
    )


def _make_bot(
    platform: MagicMock | None = None,
    provider: MagicMock | None = None,
    retriever: MagicMock | None = None,
    learner: MagicMock | None = None,
    event_emitter: MagicMock | None = None,
) -> Bot:
    if platform is None:
        platform = MagicMock()
        platform.get_bot_user_id.return_value = "BOT"
        platform.get_thread_messages.return_value = []
        platform.send_message.return_value = "sent_msg_id"
    if provider is None:
        provider = MagicMock()

    config = _make_platform_config()
    tool_registry = MagicMock()
    tool_registry.get_all_operations.return_value = []
    tool_registry.get_tool_descriptions.return_value = []
    approval_manager = ApprovalManager()

    with patch("bulldogent.bot.load_yaml_config", return_value=_MESSAGES):
        bot = Bot(
            platform=platform,
            platform_config=config,
            provider=provider,
            tool_registry=tool_registry,
            approval_manager=approval_manager,
            retriever=retriever,
            learner=learner,
            event_emitter=event_emitter,
        )

    return bot


class TestBuildConversation:
    def test_single_message_no_thread(self) -> None:
        bot = _make_bot()
        msg = _make_message(text="<@BOT> what is up")

        conversation = bot._build_conversation(msg)

        # system + identity + user
        assert len(conversation) == 3
        assert isinstance(conversation[0], Message)
        assert conversation[0].role == MessageRole.SYSTEM
        assert isinstance(conversation[1], Message)
        assert conversation[1].role == MessageRole.SYSTEM
        assert "User asking" in conversation[1].content
        assert isinstance(conversation[2], Message)
        assert conversation[2].role == MessageRole.USER
        assert conversation[2].content == "what is up"

    def test_thread_messages_mapped_to_roles(self) -> None:
        platform = MagicMock()
        platform.get_bot_user_id.return_value = "BOT"
        platform.send_message.return_value = "sent_msg_id"

        thread_msgs = [
            PlatformMessage(
                id="T1",
                channel_id="C1",
                text="hey bot",
                user=PlatformUser(user_id="U100", name="alice", raw={}),
                timestamp=1.0,
                thread_id="T0",
                raw={},
            ),
            PlatformMessage(
                id="T2",
                channel_id="C1",
                text="hi there",
                user=PlatformUser(user_id="BOT", name="tokyo", raw={}),
                timestamp=2.0,
                thread_id="T0",
                raw={},
            ),
            PlatformMessage(
                id="T3",
                channel_id="C1",
                text="<@BOT> follow up",
                user=PlatformUser(user_id="U100", name="alice", raw={}),
                timestamp=3.0,
                thread_id="T0",
                raw={},
            ),
        ]
        platform.get_thread_messages.return_value = thread_msgs

        bot = _make_bot(platform=platform)
        msg = _make_message(text="<@BOT> follow up", thread_id="T0")

        conversation = bot._build_conversation(msg)

        # system + identity + 3 thread messages
        assert len(conversation) == 5
        assert conversation[1].role == MessageRole.SYSTEM  # identity
        assert conversation[2].role == MessageRole.USER
        assert conversation[3].role == MessageRole.ASSISTANT
        assert conversation[4].role == MessageRole.USER


class TestBaselineContextInjection:
    def test_injects_context_when_retriever_returns_results(self) -> None:
        retriever = MagicMock()
        retriever.retrieve.return_value = [
            MagicMock(source="confluence", title="Doc A", url="http://a", content="content a"),
        ]

        bot = _make_bot(retriever=retriever)
        msg = _make_message(text="how to deploy")

        conversation = bot._build_conversation(msg)

        # system + identity + context + user = 4
        assert len(conversation) == 4
        context_msg = conversation[2]
        assert isinstance(context_msg, Message)
        assert context_msg.role == MessageRole.SYSTEM
        assert "content a" in context_msg.content

    def test_no_injection_when_retriever_is_none(self) -> None:
        bot = _make_bot(retriever=None)
        msg = _make_message(text="hello")

        conversation = bot._build_conversation(msg)

        # system + identity + user = 3
        assert len(conversation) == 3


class TestHandleLoopExhaustion:
    def test_loop_exhaustion_sends_summary_request(self) -> None:
        platform = MagicMock()
        platform.get_bot_user_id.return_value = "BOT"
        platform.get_thread_messages.return_value = []
        platform.send_message.return_value = "sent_msg_id"

        provider = MagicMock()
        tool_call = ToolOperationCall(id="tc1", name="search", input={"q": "test"})
        tool_response = ToolUseResponse(
            tool_operation_calls=[tool_call],
            usage=TokenUsage(input_tokens=10, output_tokens=10),
        )
        final_text = TextResponse(
            content="Here is a summary.",
            usage=TokenUsage(input_tokens=5, output_tokens=5),
        )
        # Return tool use responses for 15 iterations, then a text response for the summary
        provider.complete.side_effect = [tool_response] * 15 + [final_text]

        tool_registry = MagicMock()
        tool_registry.get_all_operations.return_value = []
        tool_registry.get_tool_descriptions.return_value = []
        tool_registry.resolve_project.return_value = None
        tool_registry.get_approval_group.return_value = None
        tool_registry.execute.return_value = ToolOperationResult(
            tool_operation_call_id="tc1",
            content="result",
            success=True,
        )

        config = _make_platform_config()
        approval_manager = ApprovalManager()

        with patch("bulldogent.bot.load_yaml_config", return_value=_MESSAGES):
            bot = Bot(
                platform=platform,
                platform_config=config,
                provider=provider,
                tool_registry=tool_registry,
                approval_manager=approval_manager,
            )

        msg = _make_message(text="do everything")
        bot.handle(msg)

        # 15 tool iterations + 1 final summary = 16 calls
        assert provider.complete.call_count == 16
        platform.send_message.assert_called_once()
        assert "Here is a summary." in platform.send_message.call_args[1]["text"]


class TestApprovalGroupEmpty:
    def test_empty_group_blocks_execution(self) -> None:
        platform = MagicMock()
        platform.get_bot_user_id.return_value = "BOT"
        platform.get_thread_messages.return_value = []
        platform.send_message.return_value = "sent_msg_id"

        tool_call = ToolOperationCall(id="tc1", name="dangerous_op", input={})
        tool_response = ToolUseResponse(
            tool_operation_calls=[tool_call],
            usage=TokenUsage(input_tokens=10, output_tokens=10),
        )
        text_response = TextResponse(
            content="Done.",
            usage=TokenUsage(input_tokens=5, output_tokens=5),
        )
        provider = MagicMock()
        provider.complete.side_effect = [tool_response, text_response]

        tool_registry = MagicMock()
        tool_registry.get_all_operations.return_value = []
        tool_registry.get_tool_descriptions.return_value = []
        tool_registry.resolve_project.return_value = None
        tool_registry.get_approval_group.return_value = "admins"

        config = _make_platform_config()
        # Empty approval group for "admins"
        config.approval_groups = {"admins": []}

        approval_manager = ApprovalManager()

        with patch("bulldogent.bot.load_yaml_config", return_value=_MESSAGES):
            bot = Bot(
                platform=platform,
                platform_config=config,
                provider=provider,
                tool_registry=tool_registry,
                approval_manager=approval_manager,
            )

        msg = _make_message(text="do something dangerous")
        bot.handle(msg)

        # The tool should NOT have been executed
        tool_registry.execute.assert_not_called()


class TestEventEmission:
    def test_handle_emits_message_received_and_llm_response(self) -> None:
        provider = MagicMock()
        provider.complete.return_value = TextResponse(
            content="Hi!", usage=TokenUsage(input_tokens=5, output_tokens=5)
        )

        event_emitter = MagicMock()
        bot = _make_bot(provider=provider, event_emitter=event_emitter)
        msg = _make_message(text="hello")
        bot.handle(msg)

        emit_calls = event_emitter.emit.call_args_list
        event_types = [call[0][0] for call in emit_calls]
        assert EventType.MESSAGE_RECEIVED in event_types
        assert EventType.LLM_REQUEST in event_types
        assert EventType.LLM_RESPONSE in event_types

    def test_handle_emits_error_on_exception(self) -> None:
        provider = MagicMock()
        provider.complete.side_effect = RuntimeError("boom")

        event_emitter = MagicMock()
        bot = _make_bot(provider=provider, event_emitter=event_emitter)
        msg = _make_message(text="hello")
        bot.handle(msg)

        emit_calls = event_emitter.emit.call_args_list
        event_types = [call[0][0] for call in emit_calls]
        assert EventType.ERROR in event_types

    def test_no_emitter_does_not_raise(self) -> None:
        provider = MagicMock()
        provider.complete.return_value = TextResponse(
            content="Hi!", usage=TokenUsage(input_tokens=5, output_tokens=5)
        )

        bot = _make_bot(provider=provider, event_emitter=None)
        msg = _make_message(text="hello")
        # Should not raise
        bot.handle(msg)
