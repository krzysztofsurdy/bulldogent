from bulldogent.messaging.platform.adapter import SlackPlatform
from bulldogent.messaging.platform.config import AbstractPlatformConfig, SlackConfig
from bulldogent.messaging.platform.platform import AbstractPlatform


class PlatformFactory:
    def from_config(self, config: AbstractPlatformConfig) -> AbstractPlatform:
        match config:
            case SlackConfig():
                return SlackPlatform(config)
            case _:
                raise ValueError(f"Unknown platform config class: {config}")
