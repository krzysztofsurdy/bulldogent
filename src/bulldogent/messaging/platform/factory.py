from bulldogent.messaging.platform.adapter import (
    DiscordPlatform,
    SlackPlatform,
    TeamsPlatform,
    TelegramPlatform,
)
from bulldogent.messaging.platform.config import (
    AbstractPlatformConfig,
    DiscordConfig,
    SlackConfig,
    TeamsConfig,
    TelegramConfig,
)
from bulldogent.messaging.platform.platform import AbstractMessagingPlatform


class PlatformFactory:
    def from_config(self, config: AbstractPlatformConfig) -> AbstractMessagingPlatform:
        match config:
            case SlackConfig():
                return SlackPlatform(config)
            case TeamsConfig():
                return TeamsPlatform(config)
            case DiscordConfig():
                return DiscordPlatform(config)
            case TelegramConfig():
                return TelegramPlatform(config)
            case _:
                raise ValueError(f"Unknown platform config class: {config}")
