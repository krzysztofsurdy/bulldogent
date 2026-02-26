from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from bulldogent.llm.tool.tool import AbstractTool, ToolConfig
from bulldogent.llm.tool.types import ToolOperationResult, ToolUserContext
from bulldogent.teams import TeamConfig, TeamsConfig, UserMapping

_logger = structlog.get_logger()


def _format_user(user: UserMapping, teams_config: TeamsConfig) -> str:
    """Format a user's full identity as readable text."""
    lines = [f"{user.name} (id: {user.id})"]

    if user.tools.google:
        lines.append(f"  Google: {', '.join(f'{k}={v}' for k, v in user.tools.google.items())}")
    if user.tools.jira:
        lines.append(f"  Jira: {', '.join(f'{k}={v}' for k, v in user.tools.jira.items())}")
    if user.tools.confluence:
        lines.append(
            f"  Confluence: {', '.join(f'{k}={v}' for k, v in user.tools.confluence.items())}"
        )
    if user.tools.github:
        lines.append(f"  GitHub: {', '.join(f'{k}={v}' for k, v in user.tools.github.items())}")
    if user.platforms:
        lines.append(f"  Platforms: {', '.join(f'{k}={v}' for k, v in user.platforms.items())}")

    user_teams = teams_config.get_user_teams(user.id)
    if user_teams:
        team_parts: list[str] = []
        for team in user_teams:
            groups = [
                g for g, members in team.groups.items() if g != "default" and user.id in members
            ]
            if groups:
                team_parts.append(f"{team.name} ({', '.join(groups)})")
            else:
                team_parts.append(team.name)
        lines.append(f"  Teams: {', '.join(team_parts)}")

    return "\n".join(lines)


def _format_team(team: TeamConfig, teams_config: TeamsConfig) -> str:
    """Format a team's full details as readable text."""
    lines = [f"{team.name} (id: {team.id})"]

    if team.aliases:
        lines.append(f"  Aliases: {', '.join(team.aliases)}")

    for group_name, member_ids in team.groups.items():
        members = teams_config.resolve_user_ids(member_ids)
        names = [m.name or m.id for m in members]
        lines.append(f"  Group '{group_name}': {', '.join(names)}")

    # Tool resources
    if team.tools.google:
        lines.append(f"  Google: {', '.join(f'{k}={v}' for k, v in team.tools.google.items())}")
    if team.tools.jira:
        jira = team.tools.jira
        for k, v in jira.items():
            lines.append(f"  Jira {k}: {v}")
    if team.tools.confluence:
        conf = team.tools.confluence
        for k, v in conf.items():
            lines.append(f"  Confluence {k}: {v}")
    if team.tools.github:
        gh = team.tools.github
        for k, v in gh.items():
            lines.append(f"  GitHub {k}: {v}")

    # Platform channels
    for platform in ("slack", "discord", "teams", "telegram"):
        cfg = getattr(team.platforms, platform, {})
        if isinstance(cfg, dict) and cfg:
            lines.append(f"  {platform}: {', '.join(f'{k}={v}' for k, v in cfg.items())}")

    return "\n".join(lines)


class TeamsTool(AbstractTool):
    _operations_path = Path(__file__).parent / "operations.yaml"

    _REQUIRED_CONFIG_KEYS = ("teams_config",)

    @property
    def name(self) -> str:
        return "teams"

    @property
    def description(self) -> str:
        return (
            "Look up team and user identity data — members, role groups, "
            "calendar IDs, Jira projects, platform channels"
        )

    def __init__(self, config: ToolConfig) -> None:
        super().__init__(config)
        self._teams_config: TeamsConfig = config["teams_config"]

    def run(
        self, operation: str, *, user_context: ToolUserContext | None = None, **kwargs: Any
    ) -> ToolOperationResult:
        _logger.info("teams_operation", operation=operation, params=list(kwargs.keys()))
        try:
            match operation:
                case "teams_get_user":
                    return self._get_user(**kwargs)
                case "teams_get_team":
                    return self._get_team(**kwargs)
                case "teams_list_teams":
                    return self._list_teams(**kwargs)
                case "teams_get_user_teams":
                    return self._get_user_teams(**kwargs)
                case _:
                    return ToolOperationResult(
                        tool_operation_call_id="",
                        content=f"Unknown operation: {operation}",
                        success=False,
                    )
        except Exception as exc:
            _logger.error("teams_error", error=str(exc))
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"Teams error: {exc}",
                success=False,
            )

    def _get_user(self, query: str = "", **_: Any) -> ToolOperationResult:
        if not query:
            return ToolOperationResult(
                tool_operation_call_id="",
                content="No query provided.",
                success=False,
            )

        tc = self._teams_config
        query_lower = query.lower()

        # Try direct ID lookup
        user = tc.get_user(query)

        # Try by name
        if not user:
            for mapping in tc.user_mappings.values():
                if mapping.name.lower() == query_lower:
                    user = mapping
                    break

        # Try by platform ID
        if not user:
            for platform in ("slack", "discord", "teams", "telegram"):
                user = tc.get_user_by_platform_id(platform, query)
                if user:
                    break

        if not user:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"No user found matching: {query}",
            )

        return ToolOperationResult(
            tool_operation_call_id="",
            content=_format_user(user, tc),
        )

    def _get_team(self, query: str = "", **_: Any) -> ToolOperationResult:
        if not query:
            return ToolOperationResult(
                tool_operation_call_id="",
                content="No query provided.",
                success=False,
            )

        team = self._teams_config.get_team_by_name(query)
        if not team:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"No team found matching: {query}",
            )

        return ToolOperationResult(
            tool_operation_call_id="",
            content=_format_team(team, self._teams_config),
        )

    def _list_teams(self, **_: Any) -> ToolOperationResult:
        tc = self._teams_config
        if not tc.teams:
            return ToolOperationResult(
                tool_operation_call_id="",
                content="No teams configured.",
            )

        lines: list[str] = []
        for team in tc.teams.values():
            aliases = f" (aliases: {', '.join(team.aliases)})" if team.aliases else ""
            members = len(team.member_ids)
            lines.append(f"- {team.name} (id: {team.id}){aliases} — {members} members")

        return ToolOperationResult(
            tool_operation_call_id="",
            content="\n".join(lines),
        )

    def _get_user_teams(self, user_id: str = "", **_: Any) -> ToolOperationResult:
        if not user_id:
            return ToolOperationResult(
                tool_operation_call_id="",
                content="No user_id provided.",
                success=False,
            )

        tc = self._teams_config
        user = tc.get_user(user_id)
        if not user:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"No user found with id: {user_id}",
            )

        teams = tc.get_user_teams(user_id)
        if not teams:
            return ToolOperationResult(
                tool_operation_call_id="",
                content=f"{user.name} is not a member of any team.",
            )

        lines = [f"Teams for {user.name} ({user_id}):"]
        for team in teams:
            lines.append("")
            lines.append(_format_team(team, tc))
            groups = [
                g for g, members in team.groups.items() if g != "default" and user_id in members
            ]
            if groups:
                lines.append(f"  User roles: {', '.join(groups)}")

        return ToolOperationResult(
            tool_operation_call_id="",
            content="\n".join(lines),
        )
