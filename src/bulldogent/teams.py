"""Shared team and user identity mapping.

Loaded from ``config/teams.yaml``.  Provides a single source of truth for
team membership, per-system user IDs (tool integrations, messaging platforms),
and team-level resource references (Jira projects, Confluence spaces, etc.).

Users are defined once under ``user_mappings`` keyed by a stable ID
(e.g. ``alice_smith``).  Teams and approval groups reference users
by these IDs.

Each user and team has two namespaced trees:

- ``tools:`` --- per-tool-integration identities / resources
- ``platforms:`` --- per-messaging-platform identities / channels

Teams have ``groups`` --- named lists of user IDs.  The ``default`` group
is mandatory and contains all team members.  Additional groups (e.g.
``leads``, ``on_call``) can be used for approval routing via
``<team_id>.<group>`` syntax in ``platforms.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bulldogent.util import PROJECT_ROOT, load_yaml_config

_CONFIG_PATH = PROJECT_ROOT / "config" / "teams.yaml"


# -- User mapping -----------------------------------------------------------


@dataclass
class UserToolsConfig:
    """Per-tool identities for a single user."""

    google: dict[str, str] = field(default_factory=dict)
    jira: dict[str, str] = field(default_factory=dict)
    confluence: dict[str, str] = field(default_factory=dict)
    github: dict[str, str] = field(default_factory=dict)


@dataclass
class UserMapping:
    """Maps a person across all configured systems.

    ``tools`` contains per-tool-integration identities (google email,
    jira user_id, etc.).

    ``platforms`` is keyed by platform name (``slack``, ``discord``,
    ``teams``, ``telegram``) with the platform-specific user ID as value.
    """

    id: str = ""
    name: str = ""
    tools: UserToolsConfig = field(default_factory=UserToolsConfig)
    platforms: dict[str, str] = field(default_factory=dict)


# -- Team config -------------------------------------------------------------


@dataclass
class TeamToolsConfig:
    """Per-tool resources for a team."""

    google: dict[str, str] = field(default_factory=dict)
    jira: dict[str, str | list[str]] = field(default_factory=dict)
    confluence: dict[str, str | list[str]] = field(default_factory=dict)
    github: dict[str, str | list[str]] = field(default_factory=dict)


@dataclass
class TeamPlatformsConfig:
    """Per-platform settings for a team (e.g. channel IDs)."""

    slack: dict[str, str] = field(default_factory=dict)
    discord: dict[str, str] = field(default_factory=dict)
    teams: dict[str, str] = field(default_factory=dict)
    telegram: dict[str, str] = field(default_factory=dict)


@dataclass
class TeamConfig:
    id: str = ""
    name: str = ""
    aliases: list[str] = field(default_factory=list)
    groups: dict[str, list[str]] = field(default_factory=lambda: {"default": []})
    tools: TeamToolsConfig = field(default_factory=TeamToolsConfig)
    platforms: TeamPlatformsConfig = field(default_factory=TeamPlatformsConfig)

    @property
    def member_ids(self) -> list[str]:
        """All team members (the ``default`` group)."""
        return self.groups.get("default", [])


# -- Teams config (top-level) -----------------------------------------------


@dataclass
class TeamsConfig:
    user_mappings: dict[str, UserMapping] = field(default_factory=dict)
    teams: dict[str, TeamConfig] = field(default_factory=dict)

    def get_user(self, user_id: str) -> UserMapping | None:
        """Look up a user by their stable ID."""
        return self.user_mappings.get(user_id)

    def get_team(self, team_id: str) -> TeamConfig | None:
        """Look up a team by its stable ID."""
        return self.teams.get(team_id)

    def get_team_members(self, team: TeamConfig) -> list[UserMapping]:
        """Resolve a team's default group to full ``UserMapping`` objects."""
        return self.resolve_user_ids(team.member_ids)

    def get_group_members(self, team_id: str, group: str = "") -> list[UserMapping]:
        """Resolve a team group to ``UserMapping`` objects.

        Supports ``<team_id>.<group>`` format when *team_id* contains a dot.
        Falls back to the ``default`` group when no group is specified.
        """
        if "." in team_id and not group:
            team_id, group = team_id.rsplit(".", 1)
        if not group:
            group = "default"
        team = self.teams.get(team_id)
        if not team:
            return []
        user_ids = team.groups.get(group, [])
        return self.resolve_user_ids(user_ids)

    def resolve_user_ids(self, ids: list[str]) -> list[UserMapping]:
        """Resolve a list of user IDs to ``UserMapping`` objects."""
        return [self.user_mappings[uid] for uid in ids if uid in self.user_mappings]

    def resolve_platform_id(self, google_email: str, platform: str = "") -> str:
        """Resolve a Google email to a messaging platform user ID."""
        email_lower = google_email.lower()
        for mapping in self.user_mappings.values():
            if mapping.tools.google.get("email", "").lower() == email_lower:
                return pick_platform_id(mapping.platforms, platform)
        return ""

    def resolve_display_name(self, google_email: str) -> str:
        """Resolve a Google email to a display name."""
        email_lower = google_email.lower()
        for mapping in self.user_mappings.values():
            if mapping.tools.google.get("email", "").lower() == email_lower:
                return mapping.name or google_email
        return google_email

    def get_team_for_jira_project(self, project_key: str) -> TeamConfig | None:
        """Find the team that owns a Jira project."""
        key_upper = project_key.upper()
        for team in self.teams.values():
            projects = team.tools.jira.get("projects", [])
            if isinstance(projects, list) and key_upper in [p.upper() for p in projects]:
                return team
        return None

    def get_team_by_name(self, name: str) -> TeamConfig | None:
        """Find a team by name, ID, or alias."""
        name_lower = name.lower()
        if name_lower in self.teams:
            return self.teams[name_lower]
        for team in self.teams.values():
            if team.name.lower() == name_lower:
                return team
            if name_lower in [a.lower() for a in team.aliases]:
                return team
        return None

    def get_team_channel_id(self, team: TeamConfig, platform: str) -> str:
        """Get the channel ID for a team on a specific platform."""
        platform_cfg = getattr(team.platforms, platform, {})
        if isinstance(platform_cfg, dict):
            return str(platform_cfg.get("channel_id", ""))
        return ""

    def get_user_by_platform_id(self, platform: str, platform_user_id: str) -> UserMapping | None:
        """Reverse-lookup: find a user by their messaging platform ID."""
        for mapping in self.user_mappings.values():
            if mapping.platforms.get(platform) == platform_user_id:
                return mapping
        return None

    def get_user_teams(self, user_id: str) -> list[TeamConfig]:
        """Return all teams that include a user in their default group."""
        return [team for team in self.teams.values() if user_id in team.member_ids]


# -- Helpers -----------------------------------------------------------------


def pick_platform_id(platform_ids: dict[str, str], platform: str) -> str:
    """Return the ID for a specific platform, or the first available."""
    if platform and platform in platform_ids:
        return platform_ids[platform]
    if platform_ids:
        return next(iter(platform_ids.values()))
    return ""


def _parse_user_mapping(user_id: str, raw: dict[str, Any]) -> UserMapping:
    tools_raw: dict[str, Any] = raw.get("tools", {})
    platforms: dict[str, str] = {str(k): str(v) for k, v in (raw.get("platforms") or {}).items()}
    return UserMapping(
        id=user_id,
        name=str(raw.get("name", "")),
        tools=UserToolsConfig(
            google=tools_raw.get("google", {}),
            jira=tools_raw.get("jira", {}),
            confluence=tools_raw.get("confluence", {}),
            github=tools_raw.get("github", {}),
        ),
        platforms=platforms,
    )


def _parse_team(team_id: str, raw: dict[str, Any]) -> TeamConfig:
    tools_raw: dict[str, Any] = raw.get("tools", {})
    platforms_raw: dict[str, Any] = raw.get("platforms", {})

    raw_groups: dict[str, list[str]] = raw.get("groups", {})
    if "default" not in raw_groups:
        raw_groups["default"] = []

    return TeamConfig(
        id=team_id,
        name=raw.get("name", team_id),
        aliases=raw.get("aliases", []),
        groups=raw_groups,
        tools=TeamToolsConfig(
            google=tools_raw.get("google", {}),
            jira=tools_raw.get("jira", {}),
            confluence=tools_raw.get("confluence", {}),
            github=tools_raw.get("github", {}),
        ),
        platforms=TeamPlatformsConfig(
            slack=platforms_raw.get("slack", {}),
            discord=platforms_raw.get("discord", {}),
            teams=platforms_raw.get("teams", {}),
            telegram=platforms_raw.get("telegram", {}),
        ),
    )


def load_teams_config() -> TeamsConfig:
    """Load team and user mappings from ``config/teams.yaml``."""
    try:
        raw = load_yaml_config(_CONFIG_PATH)
    except Exception:
        return TeamsConfig()

    if not raw:
        return TeamsConfig()

    raw_users: dict[str, Any] = raw.get("user_mappings", {})
    user_mappings: dict[str, UserMapping] = {
        uid: _parse_user_mapping(uid, data)
        for uid, data in raw_users.items()
        if isinstance(data, dict)
    }

    raw_teams: dict[str, Any] = raw.get("teams", {})
    teams: dict[str, TeamConfig] = {
        tid: _parse_team(tid, data) for tid, data in raw_teams.items() if isinstance(data, dict)
    }

    return TeamsConfig(user_mappings=user_mappings, teams=teams)
