import re
from datetime import UTC, datetime
from typing import Any

import structlog

from bulldogent.approval import ApprovalManager
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
from bulldogent.llm.tool.types import ToolOperationResult
from bulldogent.messaging.platform import AbstractPlatformConfig
from bulldogent.messaging.platform.platform import AbstractPlatform
from bulldogent.messaging.platform.types import PlatformMessage, PlatformReaction
from bulldogent.util import PROJECT_ROOT, load_yaml_config

_logger = structlog.get_logger()

_MESSAGES_PATH = PROJECT_ROOT / "config" / "messages.yaml"
_MAX_ITERATIONS = 15


class Bot:
    def __init__(
        self,
        platform: AbstractPlatform,
        platform_config: AbstractPlatformConfig,
        provider: AbstractProvider,
        tool_registry: ToolRegistry,
        approval_manager: ApprovalManager,
    ) -> None:
        self.platform = platform
        self.platform_config = platform_config
        self.provider = provider
        self.tool_registry = tool_registry
        self.approval_manager = approval_manager
        self.messages = load_yaml_config(_MESSAGES_PATH)
        self.bot_name = self.messages["bot_name"]
        tool_descriptions = tool_registry.get_tool_descriptions()
        tool_inventory = "\n".join(f"- {desc}" for desc in tool_descriptions)
        self.system_prompt = self.messages["system_prompt"].format(
            bot_name=self.bot_name,
            current_date=datetime.now(UTC).strftime("%Y-%m-%d"),
            tool_inventory=tool_inventory,
        )

    def _clean_text(self, text: str) -> str:
        return re.sub(r"<@\w+>", "", text).strip()

    def _build_conversation(self, message: PlatformMessage) -> list[ConversationMessage]:
        """Build LLM conversation from the incoming message.

        If the message is in a thread, fetches thread history and maps
        messages to USER/ASSISTANT roles. Otherwise, just the single message.
        """
        system_msg = Message(role=MessageRole.SYSTEM, content=self.system_prompt)

        if not message.thread_id:
            clean_text = self._clean_text(message.text)
            return [system_msg, Message(role=MessageRole.USER, content=clean_text)]

        thread_messages = self.platform.get_thread_messages(
            channel_id=message.channel_id,
            thread_id=message.thread_id,
        )

        if not thread_messages:
            clean_text = self._clean_text(message.text)
            return [system_msg, Message(role=MessageRole.USER, content=clean_text)]

        bot_user_id = self.platform.get_bot_user_id()
        conversation: list[ConversationMessage] = [system_msg]

        for msg in thread_messages:
            clean_text = self._clean_text(msg.text)
            if not clean_text:
                continue

            if msg.user.user_id == bot_user_id:
                conversation.append(Message(role=MessageRole.ASSISTANT, content=clean_text))
            else:
                prefixed = f"[{msg.user.name}]: {clean_text}"
                conversation.append(Message(role=MessageRole.USER, content=prefixed))

        _logger.info(
            "thread_context_loaded",
            thread_id=message.thread_id,
            thread_messages=len(thread_messages),
            conversation_messages=len(conversation) - 1,
        )

        return conversation

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
            approve_emoji=self.platform_config.reaction_approval,
        )
        self.approval_manager.handle_reaction(
            message_id=reaction.message_id,
            user_id=reaction.user_id,
            emoji=reaction.emoji,
            approve_emoji=self.platform_config.reaction_approval,
        )

    def handle(self, message: PlatformMessage) -> None:
        _logger.info(
            "message_received",
            channel_id=message.channel_id,
            user=message.user.name,
            message_id=message.id,
        )

        self.platform.add_reaction(
            channel_id=message.channel_id,
            message_id=message.id,
            emoji=self.platform_config.reaction_acknowledged,
        )

        approval_groups = self.platform_config.approval_groups

        try:
            conversation = self._build_conversation(message)
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

                    result = self.tool_registry.execute(call.name, **call.input)
                    result.tool_operation_call_id = call.id
                    _logger.info(
                        "tool_executed",
                        tool=call.name,
                        success=result.success,
                    )
                    results.append(result)

                conversation.append(
                    AssistantToolCallMessage(
                        tool_operation_calls=response.tool_operation_calls,
                    )
                )
                conversation.append(ToolResultMessage(tool_operation_results=results))

                iterations += 1

            if not isinstance(response, TextResponse):
                _logger.warning(
                    "agentic_loop_exhausted",
                    iterations=iterations,
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

            self.platform.send_message(
                channel_id=message.channel_id,
                text=response.content,
                thread_id=message.thread_id or message.id,
            )

            self.platform.add_reaction(
                channel_id=message.channel_id,
                message_id=message.id,
                emoji=self.platform_config.reaction_handled,
            )
            _logger.info("message_handled", message_id=message.id)
        except Exception:
            _logger.exception("handle_message_failed")
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
