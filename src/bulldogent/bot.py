import re

import structlog

from bulldogent.llm.provider import AbstractProvider, Message, MessageRole, TextResponse
from bulldogent.messaging.platform import AbstractPlatformConfig
from bulldogent.messaging.platform.platform import AbstractPlatform
from bulldogent.messaging.platform.types import PlatformMessage
from bulldogent.util import PROJECT_ROOT, load_yaml_config

_logger = structlog.get_logger()

_MESSAGES_PATH = PROJECT_ROOT / "config" / "messages.yaml"


class Bot:
    def __init__(
        self,
        platform: AbstractPlatform,
        platform_config: AbstractPlatformConfig,
        provider: AbstractProvider,
    ) -> None:
        self.platform = platform
        self.platform_config = platform_config
        self.provider = provider
        self.messages = load_yaml_config(_MESSAGES_PATH)
        self.bot_name = self.messages["bot_name"]
        self.system_prompt = self.messages["system_prompt"].format(bot_name=self.bot_name)

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

        try:
            clean_text = re.sub(r"<@\w+>", "", message.text).strip()
            _logger.debug("llm_request_starting", clean_text=clean_text)

            provider_response = self.provider.complete(
                [
                    Message(role=MessageRole.SYSTEM, content=self.system_prompt),
                    Message(role=MessageRole.USER, content=clean_text),
                ]
            )

            if not isinstance(provider_response, TextResponse):
                _logger.warning("unexpected_response_type", type=type(provider_response).__name__)
                self.platform.send_message(
                    channel_id=message.channel_id,
                    text=self.messages["unexpected_response"],
                    thread_id=message.thread_id or message.id,
                )
                return

            _logger.info(
                "llm_response_received",
                length=len(provider_response.content),
                input_tokens=provider_response.usage.input_tokens,
                output_tokens=provider_response.usage.output_tokens,
                total_tokens=provider_response.usage.total_tokens,
            )

            self.platform.send_message(
                channel_id=message.channel_id,
                text=provider_response.content,
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
