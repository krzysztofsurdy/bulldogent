from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from bulldogent.approval import ApprovalManager
from bulldogent.events.types import EventType
from bulldogent.llm.provider import (
    AbstractProvider,
    AssistantToolCallMessage,
    Message,
    MessageRole,
    TextResponse,
    TokenUsage,
    ToolResultMessage,
    ToolUseResponse,
)
from bulldogent.llm.provider.types import ConversationMessage
from bulldogent.llm.tool.registry import ToolRegistry
from bulldogent.llm.tool.types import ToolOperationResult, ToolUserContext
from bulldogent.messaging.platform import AbstractPlatformConfig
from bulldogent.messaging.platform.platform import AbstractPlatform
from bulldogent.messaging.platform.types import PlatformMessage, PlatformReaction
from bulldogent.teams import TeamsConfig
from bulldogent.util import PROJECT_ROOT, load_yaml_config

if TYPE_CHECKING:
    from bulldogent.baseline.learner import Learner
    from bulldogent.baseline.retriever import BaselineRetriever
    from bulldogent.events.emitter import EventEmitter

_logger = structlog.get_logger()

_MESSAGES_PATH = PROJECT_ROOT / "config" / "prompts.yaml"
_MAX_ITERATIONS = 15


@dataclass
class _LearnableQA:
    question: str
    answer: str
    channel_id: str
    thread_id: str | None
    timestamp: str


class Bot:
    def __init__(
        self,
        platform: AbstractPlatform,
        platform_config: AbstractPlatformConfig,
        provider: AbstractProvider,
        tool_registry: ToolRegistry,
        approval_manager: ApprovalManager,
        retriever: BaselineRetriever | None = None,
        learner: Learner | None = None,
        event_emitter: EventEmitter | None = None,
        teams_config: TeamsConfig | None = None,
    ) -> None:
        self.platform = platform
        self.platform_config = platform_config
        self.provider = provider
        self.tool_registry = tool_registry
        self.approval_manager = approval_manager
        self.retriever: BaselineRetriever | None = retriever
        self.learner: Learner | None = learner
        self.event_emitter: EventEmitter | None = event_emitter
        self.teams_config: TeamsConfig | None = teams_config
        self._learnable: dict[str, _LearnableQA] = {}
        self.messages = load_yaml_config(_MESSAGES_PATH)
        self.bot_name = self.messages["bot_name"]
        self.organization = self.messages.get("organization", "")
        tool_descriptions = tool_registry.get_tool_descriptions()
        tool_inventory = "\n".join(f"- {desc}" for desc in tool_descriptions)
        self.system_prompt = self.messages["system_prompt"].format(
            bot_name=self.bot_name,
            organization=self.organization,
            current_date=datetime.now(UTC).strftime("%Y-%m-%d"),
            tool_inventory=tool_inventory,
            reaction_learn=platform_config.reaction_learn,
        )

    def _emit(
        self,
        event_type: EventType,
        message: PlatformMessage,
        *,
        iteration: int | None = None,
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self.event_emitter is None:
            return
        self.event_emitter.emit(
            event_type,
            platform=self.platform.identify().value,
            channel_id=message.channel_id,
            user_id=message.user.user_id,
            message_id=message.id,
            thread_id=message.thread_id or "",
            iteration=iteration,
            content=content,
            metadata=metadata,
        )

    def _clean_text(self, text: str) -> str:
        return re.sub(r"<@\w+>", "", text).strip()

    def _resolve_user_identity(self, message: PlatformMessage) -> str:
        """Resolve the asking user's identity from teams.yaml.

        Returns a context string with the user's name, teams, and roles.
        Falls back to platform info when no mapping is found.
        """
        platform_name = self.platform.identify().value
        platform_user_id = message.user.user_id
        platform_display = message.user.name

        if not self.teams_config:
            return (
                f"User asking: {platform_display} "
                f"(platform: {platform_name}, id: {platform_user_id})"
            )

        user = self.teams_config.get_user_by_platform_id(platform_name, platform_user_id)
        if not user:
            return (
                f"User asking: {platform_display} "
                f"(platform: {platform_name}, id: {platform_user_id})"
            )

        parts = [f"User asking: {user.name} (id: {user.id})"]

        # Tool identities
        if user.tools.jira:
            parts.append(f"Jira: {', '.join(f'{k}={v}' for k, v in user.tools.jira.items())}")
        if user.tools.confluence:
            parts.append(
                f"Confluence: {', '.join(f'{k}={v}' for k, v in user.tools.confluence.items())}"
            )
        if user.tools.github:
            parts.append(f"GitHub: {', '.join(f'{k}={v}' for k, v in user.tools.github.items())}")

        # Platform identities
        if user.platforms:
            parts.append(f"Platforms: {', '.join(f'{k}={v}' for k, v in user.platforms.items())}")

        return "\n".join(parts)

    def _build_conversation(self, message: PlatformMessage) -> list[ConversationMessage]:
        """Build LLM conversation from the incoming message.

        If the message is in a thread, fetches thread history and maps
        messages to USER/ASSISTANT roles. Otherwise, just the single message.
        Injects user identity and baseline knowledge context when available.
        """
        system_msg = Message(role=MessageRole.SYSTEM, content=self.system_prompt)
        identity_msg = Message(
            role=MessageRole.SYSTEM,
            content=self._resolve_user_identity(message),
        )

        if not message.thread_id:
            clean_text = self._clean_text(message.text)
            conversation: list[ConversationMessage] = [
                system_msg,
                identity_msg,
                Message(role=MessageRole.USER, content=clean_text),
            ]
            self._inject_baseline_context(conversation, clean_text)
            return conversation

        thread_messages = self.platform.get_thread_messages(
            channel_id=message.channel_id,
            thread_id=message.thread_id,
        )

        if not thread_messages:
            clean_text = self._clean_text(message.text)
            conversation = [
                system_msg,
                identity_msg,
                Message(role=MessageRole.USER, content=clean_text),
            ]
            self._inject_baseline_context(conversation, clean_text)
            return conversation

        bot_user_id = self.platform.get_bot_user_id()
        conversation = [system_msg, identity_msg]

        last_user_text = ""
        for msg in thread_messages:
            clean_text = self._clean_text(msg.text)
            if not clean_text:
                continue

            if msg.user.user_id == bot_user_id:
                conversation.append(Message(role=MessageRole.ASSISTANT, content=clean_text))
            else:
                prefixed = f"[{msg.user.name}]: {clean_text}"
                conversation.append(Message(role=MessageRole.USER, content=prefixed))
                last_user_text = clean_text

        _logger.info(
            "thread_context_loaded",
            thread_id=message.thread_id,
            thread_messages=len(thread_messages),
            conversation_messages=len(conversation) - 1,
        )

        self._inject_baseline_context(conversation, last_user_text)
        return conversation

    def _inject_baseline_context(self, conversation: list[ConversationMessage], query: str) -> None:
        """Retrieve relevant baseline knowledge and inject as a context message."""
        if not self.retriever or not query:
            return

        try:
            results = self.retriever.retrieve(query)
        except Exception:
            _logger.debug("baseline_retrieval_failed", exc_info=True)
            return

        if not results:
            return

        lines = ["Relevant internal context (from baseline knowledge):"]
        for result in results:
            lines.append(f"\n[{result.source}] {result.title}")
            if result.url:
                lines.append(f"Source: {result.url}")
            lines.append(result.content)

        context_text = "\n".join(lines)

        # Insert after system + identity messages (index 2), before user messages.
        # Use SYSTEM role since this is system-injected knowledge, not user input.
        context_msg = Message(role=MessageRole.SYSTEM, content=context_text)
        conversation.insert(2, context_msg)

        _logger.info("baseline_context_injected", chunks=len(results))

    def _request_approval(
        self,
        operation_name: str,
        operation_input: dict[str, Any],
        message: PlatformMessage,
        group: str,
        members: list[str],
    ) -> bool:
        thread_id = message.thread_id or message.id
        mentions = " ".join(f"<@{uid}>" for uid in members)
        approve_emoji = self.platform_config.reaction_approval
        approval_message_id = self.platform.send_message(
            channel_id=message.channel_id,
            text=self.messages["approval_request"].format(
                group=group,
                operation_name=operation_name,
                operation_input=operation_input,
                mentions=mentions,
                approve_emoji=approve_emoji,
            ),
            thread_id=thread_id,
        )

        approval = self.approval_manager.request(
            channel_id=message.channel_id,
            message_id=approval_message_id,
            operation_name=operation_name,
            operation_input=operation_input,
            approval_group=group,
            allowed_user_ids=members,
        )
        return self.approval_manager.wait(approval)

    def handle_reaction(self, reaction: PlatformReaction) -> None:
        _logger.debug(
            "reaction_received",
            message_id=reaction.message_id,
            user_id=reaction.user_id,
            emoji=reaction.emoji,
        )

        if reaction.emoji == self.platform_config.reaction_approval:
            self.approval_manager.handle_reaction(
                message_id=reaction.message_id,
                user_id=reaction.user_id,
                emoji=reaction.emoji,
                approve_emoji=self.platform_config.reaction_approval,
            )
            return

        learn_emoji = self.platform_config.reaction_learn
        if learn_emoji and reaction.emoji == learn_emoji:
            self._handle_learn_reaction(reaction)
            return

    def _handle_learn_reaction(self, reaction: PlatformReaction) -> None:
        key = f"{reaction.channel_id}:{reaction.message_id}"
        qa = self._learnable.pop(key, None)
        if not qa or not self.learner:
            _logger.debug("learn_reaction_ignored", message_id=reaction.message_id)
            return

        try:
            self.learner.learn(
                question=qa.question,
                answer=qa.answer,
                channel_id=qa.channel_id,
                thread_id=qa.thread_id,
                timestamp=qa.timestamp,
            )
            _logger.info("learned_from_reaction", message_id=reaction.message_id)
        except Exception:
            _logger.debug("learning_failed", exc_info=True)

    def _build_user_context(self, message: PlatformMessage) -> ToolUserContext:
        """Build a ToolUserContext from the incoming message."""
        platform_name = self.platform.identify().value
        platform_user_id = message.user.user_id
        user_id = ""

        if self.teams_config:
            user = self.teams_config.get_user_by_platform_id(platform_name, platform_user_id)
            if user:
                user_id = user.id

        return ToolUserContext(
            user_id=user_id or platform_user_id,
            platform_user_id=platform_user_id,
            platform=platform_name,
        )

    def handle(self, message: PlatformMessage) -> None:
        _logger.info(
            "message_received",
            channel_id=message.channel_id,
            user=message.user.name,
            message_id=message.id,
        )
        self._emit(EventType.MESSAGE_RECEIVED, message)

        user_context = self._build_user_context(message)

        handling_emoji = self.platform_config.reaction_handling
        self.platform.add_reaction(
            channel_id=message.channel_id,
            message_id=message.id,
            emoji=handling_emoji,
        )

        approval_groups = self.platform_config.approval_groups

        try:
            conversation = self._build_conversation(message)
            # Baseline context is injected inside _build_conversation; emit if present.
            # system + identity + user = 3 minimum; > 3 means context was injected.
            if self.retriever and len(conversation) > 3:
                self._emit(EventType.BASELINE_CONTEXT_INJECTED, message)
            operations = self.tool_registry.get_all_operations() or None
            total_usage = TokenUsage(input_tokens=0, output_tokens=0)
            response: TextResponse | ToolUseResponse | None = None

            iterations = 0
            while iterations < _MAX_ITERATIONS:
                _logger.debug(
                    "llm_request_starting",
                    message_count=len(conversation),
                    iteration=iterations,
                    in_thread=message.thread_id is not None,
                )
                self._emit(
                    EventType.LLM_REQUEST,
                    message,
                    iteration=iterations,
                    metadata={"message_count": len(conversation)},
                )

                response = self.provider.complete(conversation, operations=operations)
                total_usage = TokenUsage(
                    input_tokens=total_usage.input_tokens + response.usage.input_tokens,
                    output_tokens=total_usage.output_tokens + response.usage.output_tokens,
                )

                if isinstance(response, TextResponse):
                    break

                # ToolUseResponse — execute tools and feed results back
                _logger.info(
                    "tool_calls_requested",
                    iteration=iterations,
                    tool_count=len(response.tool_operation_calls),
                    tools=[c.name for c in response.tool_operation_calls],
                )
                self._emit(
                    EventType.TOOL_CALLS_REQUESTED,
                    message,
                    iteration=iterations,
                    metadata={"tools": [c.name for c in response.tool_operation_calls]},
                )

                results = []
                for call in response.tool_operation_calls:
                    project = self.tool_registry.resolve_project(call.name, **call.input)
                    group = self.tool_registry.get_approval_group(call.name, project)

                    if group:
                        members = approval_groups.get(group, [])
                        if members:
                            approved = self._request_approval(
                                call.name, call.input, message, group, members
                            )
                            if not approved:
                                results.append(
                                    ToolOperationResult(
                                        tool_operation_call_id=call.id,
                                        content=self.messages["approval_timeout"],
                                        success=False,
                                    )
                                )
                                continue
                        else:
                            _logger.warning(
                                "approval_group_empty",
                                group=group,
                                operation=call.name,
                            )
                            results.append(
                                ToolOperationResult(
                                    tool_operation_call_id=call.id,
                                    content=self.messages["approval_group_empty"].format(
                                        group=group,
                                    ),
                                    success=False,
                                )
                            )
                            continue

                    result = self.tool_registry.execute(
                        call.name, user_context=user_context, **call.input
                    )
                    result.tool_operation_call_id = call.id
                    _logger.info(
                        "tool_executed",
                        tool=call.name,
                        success=result.success,
                    )
                    self._emit(
                        EventType.TOOL_EXECUTED,
                        message,
                        iteration=iterations,
                        metadata={"tool": call.name, "success": result.success},
                    )
                    results.append(result)

                conversation.append(
                    AssistantToolCallMessage(
                        tool_operation_calls=response.tool_operation_calls,
                    )
                )
                conversation.append(ToolResultMessage(tool_operation_results=results))

                iterations += 1

            # Loop exhausted — LLM still wanted more tool calls but we hit
            # the iteration cap.  Force a final summary without tools.
            if not isinstance(response, TextResponse):
                _logger.warning(
                    "agentic_loop_exhausted",
                    iterations=iterations,
                )
                hint = self.messages["loop_exhausted_hint"].format(
                    max_iterations=_MAX_ITERATIONS,
                )
                conversation.append(Message(role=MessageRole.USER, content=hint))
                response = self.provider.complete(conversation, operations=None)
                total_usage = TokenUsage(
                    input_tokens=total_usage.input_tokens + response.usage.input_tokens,
                    output_tokens=total_usage.output_tokens + response.usage.output_tokens,
                )

            if not isinstance(response, TextResponse) or not response.content.strip():
                _logger.warning(
                    "agentic_loop_no_content",
                    iterations=iterations,
                    is_text=isinstance(response, TextResponse),
                )
                self.platform.send_message(
                    channel_id=message.channel_id,
                    text=self.messages["unexpected_response"],
                    thread_id=message.thread_id or message.id,
                )
                return

            _logger.info(
                "llm_response_received",
                length=len(response.content),
                iterations=iterations,
                input_tokens=total_usage.input_tokens,
                output_tokens=total_usage.output_tokens,
                total_tokens=total_usage.total_tokens,
            )
            self._emit(
                EventType.LLM_RESPONSE,
                message,
                iteration=iterations,
                content=response.content,
                metadata={
                    "input_tokens": total_usage.input_tokens,
                    "output_tokens": total_usage.output_tokens,
                    "total_tokens": total_usage.total_tokens,
                },
            )

            response_msg_id = self.platform.send_message(
                channel_id=message.channel_id,
                text=response.content,
                thread_id=message.thread_id or message.id,
            )

            if self.learner and response_msg_id:
                key = f"{message.channel_id}:{response_msg_id}"
                self._learnable[key] = _LearnableQA(
                    question=self._clean_text(message.text),
                    answer=response.content,
                    channel_id=message.channel_id,
                    thread_id=message.thread_id,
                    timestamp=str(message.timestamp),
                )

            self.platform.remove_reaction(
                channel_id=message.channel_id,
                message_id=message.id,
                emoji=handling_emoji,
            )
            _logger.info("message_handled", message_id=message.id)
        except Exception:
            # Catch all exceptions to prevent the bot listener from crashing.
            # Individual errors are logged; the bot must remain available for
            # subsequent messages even when a single handler fails.
            _logger.exception("handle_message_failed")
            self._emit(EventType.ERROR, message)
            self.platform.remove_reaction(
                channel_id=message.channel_id,
                message_id=message.id,
                emoji=handling_emoji,
            )
            self.platform.add_reaction(
                channel_id=message.channel_id,
                message_id=message.id,
                emoji=self.platform_config.reaction_error,
            )
            self.platform.send_message(
                channel_id=message.channel_id,
                text=self.messages["error_generic"],
                thread_id=message.thread_id or message.id,
            )
