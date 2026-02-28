from unittest.mock import patch

from bulldogent.teams import (
    TeamConfig,
    TeamPlatformsConfig,
    TeamsConfig,
    TeamToolsConfig,
    UserMapping,
    UserToolsConfig,
    load_teams_config,
    pick_platform_id,
)


def _make_user(
    user_id: str = "alice",
    name: str = "Alice",
    email: str = "alice@example.com",
    jira_user_id: str = "617bea",
    jira_username: str = "alice.smith",
    slack_id: str = "U0ALICE",
    discord_id: str = "123",
) -> UserMapping:
    return UserMapping(
        id=user_id,
        name=name,
        tools=UserToolsConfig(
            google={"email": email},
            jira={"user_id": jira_user_id, "username": jira_username},
        ),
        platforms={"slack": slack_id, "discord": discord_id},
    )


def _make_team(
    team_id: str = "backend",
    name: str = "Backend",
    aliases: list[str] | None = None,
    groups: dict[str, list[str]] | None = None,
    jira_projects: list[str] | None = None,
    slack_channel: str = "C123",
) -> TeamConfig:
    return TeamConfig(
        id=team_id,
        name=name,
        aliases=aliases or [],
        groups=groups or {"default": ["alice", "bob"]},
        tools=TeamToolsConfig(
            jira={"projects": jira_projects or ["ALPHA"]},
        ),
        platforms=TeamPlatformsConfig(
            slack={"channel_id": slack_channel},
        ),
    )


def _make_config(
    users: dict[str, UserMapping] | None = None,
    teams: dict[str, TeamConfig] | None = None,
) -> TeamsConfig:
    if users is None:
        users = {
            "alice": _make_user("alice", "Alice", "alice@ex.com", slack_id="U0A"),
            "bob": _make_user("bob", "Bob", "bob@ex.com", slack_id="U0B"),
            "carol": _make_user("carol", "Carol", "carol@ex.com", slack_id="U0C"),
        }
    if teams is None:
        teams = {
            "backend": _make_team(
                groups={"default": ["alice", "bob"], "leads": ["alice"]},
            ),
            "frontend": _make_team(
                team_id="frontend",
                name="Frontend",
                aliases=["fe", "ui"],
                groups={"default": ["carol"]},
                jira_projects=["BETA"],
                slack_channel="C456",
            ),
        }
    return TeamsConfig(user_mappings=users, teams=teams)


# -- pick_platform_id -------------------------------------------------------


class TestPickPlatformId:
    def test_exact_match(self) -> None:
        assert pick_platform_id({"slack": "U1", "discord": "D1"}, "slack") == "U1"

    def test_first_available_when_no_platform(self) -> None:
        assert pick_platform_id({"slack": "U1", "discord": "D1"}, "") == "U1"

    def test_first_available_when_platform_missing(self) -> None:
        assert pick_platform_id({"slack": "U1"}, "discord") == "U1"

    def test_empty_dict(self) -> None:
        assert pick_platform_id({}, "slack") == ""


# -- TeamsConfig.get_user / get_team ----------------------------------------


class TestGetUserAndTeam:
    def test_get_user_found(self) -> None:
        cfg = _make_config()
        user = cfg.get_user("alice")
        assert user is not None
        assert user.name == "Alice"

    def test_get_user_not_found(self) -> None:
        cfg = _make_config()
        assert cfg.get_user("nobody") is None

    def test_get_team_found(self) -> None:
        cfg = _make_config()
        team = cfg.get_team("backend")
        assert team is not None
        assert team.name == "Backend"

    def test_get_team_not_found(self) -> None:
        cfg = _make_config()
        assert cfg.get_team("devops") is None


# -- TeamsConfig.get_team_members / member_ids ------------------------------


class TestTeamMembers:
    def test_member_ids_returns_default_group(self) -> None:
        team = _make_team(groups={"default": ["alice", "bob"], "leads": ["alice"]})
        assert team.member_ids == ["alice", "bob"]

    def test_get_team_members_resolves(self) -> None:
        cfg = _make_config()
        team = cfg.get_team("backend")
        assert team is not None
        members = cfg.get_team_members(team)
        assert len(members) == 2
        assert {m.id for m in members} == {"alice", "bob"}

    def test_get_team_members_skips_unknown_ids(self) -> None:
        cfg = _make_config()
        team = _make_team(groups={"default": ["alice", "unknown_user"]})
        members = cfg.get_team_members(team)
        assert len(members) == 1
        assert members[0].id == "alice"


# -- TeamsConfig.get_group_members ------------------------------------------


class TestGetGroupMembers:
    def test_team_dot_group(self) -> None:
        cfg = _make_config()
        members = cfg.get_group_members("backend.leads")
        assert len(members) == 1
        assert members[0].id == "alice"

    def test_team_with_explicit_default(self) -> None:
        cfg = _make_config()
        members = cfg.get_group_members("backend", "default")
        assert len(members) == 2

    def test_unknown_team(self) -> None:
        cfg = _make_config()
        assert cfg.get_group_members("devops.leads") == []

    def test_unknown_group(self) -> None:
        cfg = _make_config()
        assert cfg.get_group_members("backend.reviewers") == []


# -- TeamsConfig.resolve_platform_id ----------------------------------------


class TestResolvePlatformId:
    def test_resolve_by_email(self) -> None:
        cfg = _make_config()
        assert cfg.resolve_platform_id("alice@ex.com", "slack") == "U0A"

    def test_resolve_case_insensitive(self) -> None:
        cfg = _make_config()
        assert cfg.resolve_platform_id("Alice@EX.com", "slack") == "U0A"

    def test_resolve_unknown_email(self) -> None:
        cfg = _make_config()
        assert cfg.resolve_platform_id("nobody@ex.com") == ""

    def test_resolve_first_available_when_no_platform(self) -> None:
        cfg = _make_config()
        pid = cfg.resolve_platform_id("alice@ex.com", "")
        assert pid == "U0A"


# -- TeamsConfig.resolve_display_name ---------------------------------------


class TestResolveDisplayName:
    def test_resolve_found(self) -> None:
        cfg = _make_config()
        assert cfg.resolve_display_name("alice@ex.com") == "Alice"

    def test_resolve_fallback_to_email(self) -> None:
        cfg = _make_config()
        assert cfg.resolve_display_name("nobody@ex.com") == "nobody@ex.com"

    def test_resolve_user_without_name(self) -> None:
        user = _make_user(user_id="noname", name="", email="noname@ex.com")
        cfg = _make_config(users={"noname": user}, teams={})
        assert cfg.resolve_display_name("noname@ex.com") == "noname@ex.com"


# -- TeamsConfig.get_team_by_name -------------------------------------------


class TestGetTeamByName:
    def test_by_id(self) -> None:
        cfg = _make_config()
        team = cfg.get_team_by_name("backend")
        assert team is not None
        assert team.id == "backend"

    def test_by_display_name(self) -> None:
        cfg = _make_config()
        team = cfg.get_team_by_name("Frontend")
        assert team is not None
        assert team.id == "frontend"

    def test_by_alias(self) -> None:
        cfg = _make_config()
        team = cfg.get_team_by_name("fe")
        assert team is not None
        assert team.id == "frontend"

    def test_case_insensitive(self) -> None:
        cfg = _make_config()
        assert cfg.get_team_by_name("BACKEND") is not None

    def test_not_found(self) -> None:
        cfg = _make_config()
        assert cfg.get_team_by_name("devops") is None


# -- TeamsConfig.get_team_for_jira_project ----------------------------------


class TestGetTeamForJiraProject:
    def test_found(self) -> None:
        cfg = _make_config()
        team = cfg.get_team_for_jira_project("ALPHA")
        assert team is not None
        assert team.id == "backend"

    def test_case_insensitive(self) -> None:
        cfg = _make_config()
        assert cfg.get_team_for_jira_project("alpha") is not None

    def test_not_found(self) -> None:
        cfg = _make_config()
        assert cfg.get_team_for_jira_project("UNKNOWN") is None


# -- TeamsConfig.get_team_channel_id ----------------------------------------


class TestGetTeamChannelId:
    def test_found(self) -> None:
        cfg = _make_config()
        team = cfg.get_team("backend")
        assert team is not None
        assert cfg.get_team_channel_id(team, "slack") == "C123"

    def test_unknown_platform(self) -> None:
        cfg = _make_config()
        team = cfg.get_team("backend")
        assert team is not None
        assert cfg.get_team_channel_id(team, "telegram") == ""


# -- TeamsConfig.get_user_by_platform_id ------------------------------------


class TestGetUserByPlatformId:
    def test_found(self) -> None:
        cfg = _make_config()
        user = cfg.get_user_by_platform_id("slack", "U0A")
        assert user is not None
        assert user.id == "alice"

    def test_not_found(self) -> None:
        cfg = _make_config()
        assert cfg.get_user_by_platform_id("slack", "UXXX") is None

    def test_wrong_platform(self) -> None:
        cfg = _make_config()
        assert cfg.get_user_by_platform_id("telegram", "U0A") is None


# -- TeamsConfig.get_user_teams ---------------------------------------------


class TestGetUserTeams:
    def test_user_in_one_team(self) -> None:
        cfg = _make_config()
        teams = cfg.get_user_teams("carol")
        assert len(teams) == 1
        assert teams[0].id == "frontend"

    def test_user_in_multiple_teams(self) -> None:
        cfg = _make_config()
        teams = cfg.get_user_teams("alice")
        assert len(teams) == 1
        assert teams[0].id == "backend"

    def test_unknown_user(self) -> None:
        cfg = _make_config()
        assert cfg.get_user_teams("nobody") == []


# -- load_teams_config ------------------------------------------------------


class TestLoadTeamsConfig:
    @patch("bulldogent.teams.load_yaml_config")
    def test_load_full(self, mock_load: object) -> None:
        mock_load.return_value = {  # type: ignore[union-attr]
            "user_mappings": {
                "alice": {
                    "name": "Alice",
                    "tools": {
                        "google": {"email": "alice@ex.com"},
                        "jira": {"user_id": "617", "username": "alice"},
                    },
                    "platforms": {"slack": "U0A"},
                },
            },
            "teams": {
                "backend": {
                    "name": "Backend",
                    "aliases": ["be"],
                    "groups": {
                        "default": ["alice"],
                        "leads": ["alice"],
                    },
                    "tools": {
                        "jira": {"projects": ["ALPHA"]},
                    },
                    "platforms": {
                        "slack": {"channel_id": "C123"},
                    },
                },
            },
        }

        cfg = load_teams_config()

        assert "alice" in cfg.user_mappings
        user = cfg.user_mappings["alice"]
        assert user.name == "Alice"
        assert user.tools.google == {"email": "alice@ex.com"}
        assert user.tools.jira == {"user_id": "617", "username": "alice"}
        assert user.platforms == {"slack": "U0A"}

        assert "backend" in cfg.teams
        team = cfg.teams["backend"]
        assert team.name == "Backend"
        assert team.aliases == ["be"]
        assert team.groups == {"default": ["alice"], "leads": ["alice"]}
        assert team.member_ids == ["alice"]
        assert team.tools.jira == {"projects": ["ALPHA"]}
        assert team.platforms.slack == {"channel_id": "C123"}

    @patch("bulldogent.teams.load_yaml_config")
    def test_load_empty(self, mock_load: object) -> None:
        mock_load.return_value = {}  # type: ignore[union-attr]
        cfg = load_teams_config()
        assert cfg.user_mappings == {}
        assert cfg.teams == {}

    @patch("bulldogent.teams.load_yaml_config")
    def test_load_missing_file(self, mock_load: object) -> None:
        mock_load.side_effect = FileNotFoundError  # type: ignore[union-attr]
        cfg = load_teams_config()
        assert cfg.user_mappings == {}
        assert cfg.teams == {}

    @patch("bulldogent.teams.load_yaml_config")
    def test_default_group_injected_if_missing(self, mock_load: object) -> None:
        mock_load.return_value = {  # type: ignore[union-attr]
            "user_mappings": {},
            "teams": {
                "backend": {
                    "groups": {"leads": ["alice"]},
                },
            },
        }
        cfg = load_teams_config()
        assert "default" in cfg.teams["backend"].groups
        assert cfg.teams["backend"].groups["default"] == []

    @patch("bulldogent.teams.load_yaml_config")
    def test_team_name_defaults_to_id(self, mock_load: object) -> None:
        mock_load.return_value = {  # type: ignore[union-attr]
            "user_mappings": {},
            "teams": {
                "my_team": {
                    "groups": {"default": []},
                },
            },
        }
        cfg = load_teams_config()
        assert cfg.teams["my_team"].name == "my_team"
