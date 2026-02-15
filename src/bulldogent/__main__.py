import os
import signal
import threading
from typing import Any

import structlog

from bulldogent.approval import ApprovalManager
from bulldogent.bot import Bot
from bulldogent.llm.provider import ProviderType
from bulldogent.llm.provider.registry import get_provider_registry
from bulldogent.llm.tool.adapters import ConfluenceTool, GitHubTool, JiraTool, WebSearchTool
from bulldogent.llm.tool.registry import ToolRegistry
from bulldogent.messaging.platform.registry import get_platform_registry
from bulldogent.util import PROJECT_ROOT, load_yaml_config

_logger = structlog.get_logger()
_TOOLS_CONFIG_PATH = PROJECT_ROOT / "config" / "tools.yaml"


def _register_tools(tool_registry: ToolRegistry) -> None:
    tool_config = load_yaml_config(_TOOLS_CONFIG_PATH)

    if jira_cfg := tool_config.get("jira"):
        try:
            url = os.getenv(jira_cfg["url_env"], "")
            username = os.getenv(jira_cfg["username_env"], "")
            api_token = os.getenv(jira_cfg["api_token_env"], "")

            if not all([url, username, api_token]):
                _logger.debug("tool_skipped", tool="jira", reason="missing env vars")
            else:
                jira_config: dict[str, Any] = {
                    "url": url,
                    "username": username,
                    "api_token": api_token,
                    "projects": jira_cfg.get("projects", []),
                }
                tool_registry.register(JiraTool(jira_config))
        except (ValueError, KeyError):
            _logger.debug("tool_skipped", tool="jira")

    if github_cfg := tool_config.get("github"):
        try:
            token = os.getenv(github_cfg["token_env"], "")

            if not token:
                _logger.debug("tool_skipped", tool="github", reason="missing env vars")
            else:
                github_config: dict[str, Any] = {
                    "token": token,
                    "default_org": github_cfg.get("default_org", ""),
                    "repositories": github_cfg.get("repositories", []),
                }
                tool_registry.register(GitHubTool(github_config))
        except (ValueError, KeyError):
            _logger.debug("tool_skipped", tool="github")

    if confluence_cfg := tool_config.get("confluence"):
        try:
            url = os.getenv(confluence_cfg["url_env"], "")
            username = os.getenv(confluence_cfg.get("username_env", ""), "")
            api_token = os.getenv(confluence_cfg.get("api_token_env", ""), "")

            if not url:
                _logger.debug("tool_skipped", tool="confluence", reason="missing env vars")
            else:
                confluence_config: dict[str, Any] = {
                    "url": url,
                    "username": username,
                    "api_token": api_token,
                    "cloud": confluence_cfg.get("cloud", True),
                    "spaces": confluence_cfg.get("spaces", []),
                }
                tool_registry.register(ConfluenceTool(confluence_config))
        except (ValueError, KeyError):
            _logger.debug("tool_skipped", tool="confluence")

    if ws_cfg := tool_config.get("web_search"):
        try:
            api_key = os.getenv(ws_cfg["api_key_env"], "")

            if not api_key:
                _logger.debug("tool_skipped", tool="web_search", reason="missing env vars")
            else:
                ws_config: dict[str, Any] = {
                    "api_key": api_key,
                    "default_max_results": ws_cfg.get("default_max_results", 5),
                    "default_search_depth": ws_cfg.get("default_search_depth", "basic"),
                }
                tool_registry.register(WebSearchTool(ws_config))
        except (ValueError, KeyError):
            _logger.debug("tool_skipped", tool="web_search")


def main() -> None:
    platform_registry = get_platform_registry()
    provider_registry = get_provider_registry()
    tool_registry = ToolRegistry()
    approval_manager = ApprovalManager()

    _register_tools(tool_registry)

    for platform in platform_registry.get_all():
        platform_name = platform.identify().value
        provider_type = ProviderType(platform.config.llm_provider)
        _logger.info("wiring_bot", platform=platform_name, provider=provider_type.value)

        provider = provider_registry.get(provider_type)
        bot = Bot(
            platform=platform,
            platform_config=platform.config,
            provider=provider,
            tool_registry=tool_registry,
            approval_manager=approval_manager,
        )
        platform.on_message(bot.handle)
        platform.on_reaction(bot.handle_reaction)
        platform.start()

    _logger.info("all_platforms_started")

    shutdown = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: shutdown.set())
    signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
    shutdown.wait()


if __name__ == "__main__":
    main()
