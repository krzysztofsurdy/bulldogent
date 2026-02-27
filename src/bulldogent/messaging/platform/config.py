from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import structlog

from bulldogent.messaging.platform.types import PlatformType
from bulldogent.teams import TeamsConfig, load_teams_config, pick_platform_id
from bulldogent.util import PROJECT_ROOT, load_yaml_config

_logger = structlog.get_logger()
_DEFAULT_CONFIG = PROJECT_ROOT / "config" / "platforms.yaml"


class _ConfigDict(TypedDict):
    llm_provider: str
    reaction_handling: str
    reaction_error: str
    reaction_approval: str
    reaction_learn: str
    approval_groups: dict[str, list[str]]


@dataclass
class AbstractPlatformConfig(ABC):
    """Base config shared by all messaging platform adapters."""

    llm_provider: str
    reaction_handling: str
    reaction_error: str
    reaction_approval: str
    reaction_learn: str
    approval_groups: dict[str, list[str]]

    @classmethod
    def _read_common_config(
        cls,
        yaml_config: dict[str, Any],
        platform_name: str = "",
        teams_config: TeamsConfig | None = None,
    ) -> _ConfigDict:
        """Read common fields from the resolved YAML config.

        When *teams_config* is provided, approval group member IDs are resolved
        to platform-specific user IDs.  Raw IDs that don't match any user in
        ``teams.yaml`` are kept as-is (backwards compatible with hardcoded
        platform IDs).
        """
        raw_groups: dict[str, list[str]] = yaml_config.get("approval_groups", {})
        resolved_groups = _resolve_approval_groups(raw_groups, platform_name, teams_config)

        return _ConfigDict(
            llm_provider=yaml_config.get("llm_provider", ""),
            reaction_handling=yaml_config.get("reaction_handling", ""),
            reaction_error=yaml_config.get("reaction_error", ""),
            reaction_approval=yaml_config.get("reaction_approval", ""),
            reaction_learn=yaml_config.get("reaction_learn", ""),
            approval_groups=resolved_groups,
        )

    @classmethod
    @abstractmethod
    def from_yaml(
        cls,
        config: dict[str, Any],
        platform_name: str = "",
        teams_config: TeamsConfig | None = None,
    ) -> "AbstractPlatformConfig":
        """Factory method: Create config from resolved YAML dict"""
        ...


@dataclass
class SlackConfig(AbstractPlatformConfig):
    bot_token: str
    app_token: str

    @classmethod
    def from_yaml(
        cls,
        config: dict[str, Any],
        platform_name: str = "",
        teams_config: TeamsConfig | None = None,
    ) -> "SlackConfig":
        common = cls._read_common_config(config, platform_name, teams_config)

        bot_token = config.get("bot_token", "")
        if not bot_token:
            raise ValueError("Missing slack.bot_token")

        app_token = config.get("app_token", "")
        if not app_token:
            raise ValueError("Missing slack.app_token")

        return cls(
            bot_token=bot_token,
            app_token=app_token,
            **common,
        )



def _resolve_approval_groups(
    raw_groups: dict[str, list[str]],
    platform_name: str,
    teams_config: TeamsConfig | None,
) -> dict[str, list[str]]:
    """Resolve approval group member IDs to platform-specific user IDs.

    Each member entry can be:
    - A user ID from ``teams.yaml`` (e.g. ``alice_smith``)
    - A team group reference (e.g. ``backend.leads`` -> team "backend", group "leads")
    - A raw platform ID (backwards compat, kept as-is if no match)
    """
    if not teams_config:
        return raw_groups

    resolved: dict[str, list[str]] = {}
    for group_name, member_ids in raw_groups.items():
        platform_ids: list[str] = []
        for mid in member_ids:
            # Try team.group reference (e.g. "backend.leads")
            if "." in mid:
                group_members = teams_config.get_group_members(mid)
                for user in group_members:
                    pid = pick_platform_id(user.platforms, platform_name)
                    if pid:
                        platform_ids.append(pid)
                continue

            # Try direct user lookup
            direct_user = teams_config.get_user(mid)
            if direct_user:
                pid = pick_platform_id(direct_user.platforms, platform_name)
                if pid:
                    platform_ids.append(pid)
                    continue

            # Try as a team ID -> resolve default group
            team = teams_config.get_team(mid)
            if team:
                for member in teams_config.get_team_members(team):
                    pid = pick_platform_id(member.platforms, platform_name)
                    if pid:
                        platform_ids.append(pid)
                continue

            # Not found in teams.yaml -- keep raw (might be a hardcoded platform ID)
            platform_ids.append(mid)
        resolved[group_name] = platform_ids
    return resolved


class PlatformConfigGenerator:
    def __init__(self, config_location: Path = _DEFAULT_CONFIG) -> None:
        self.config = load_yaml_config(config_location)
        self._teams_config = load_teams_config()

    def generate(self) -> Iterator[AbstractPlatformConfig]:
        for platform_key, platform_config in self.config.items():
            try:
                match PlatformType(platform_key):
                    case PlatformType.SLACK:
                        yield SlackConfig.from_yaml(platform_config, "slack", self._teams_config)
            except (ValueError, KeyError):
                _logger.debug("platform_skipped", platform=platform_key)
