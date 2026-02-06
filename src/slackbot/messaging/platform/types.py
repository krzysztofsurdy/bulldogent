from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class PlatformType(StrEnum):
    SLACK = "slack"
    TEAMS = "teams"
    DISCORD = "discord"
    TELEGRAM = "telegram"


@dataclass
class PlatformUser:
    user_id: str
    name: str
    raw: dict[str, Any]


@dataclass
class PlatformMessage:
    id: str
    channel_id: str
    text: str
    user: PlatformUser
    timestamp: float
    thread_id: str | None
    raw: dict[str, Any]
