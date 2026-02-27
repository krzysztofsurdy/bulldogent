import signal
import threading
from typing import Any

import structlog

from bulldogent.approval import ApprovalManager
from bulldogent.baseline.chunker import Chunker
from bulldogent.baseline.config import BaselineConfig, load_baseline_config
from bulldogent.baseline.learner import Learner
from bulldogent.baseline.retriever import BaselineRetriever
from bulldogent.bot import Bot
from bulldogent.embedding import create_embedding_provider
from bulldogent.embedding.provider import AbstractEmbeddingProvider
from bulldogent.events.emitter import EventEmitter
from bulldogent.llm.provider import ProviderType
from bulldogent.llm.provider.registry import get_provider_registry
from bulldogent.llm.tool.adapters import (
    ConfluenceTool,
    GitHubTool,
    JiraTool,
    KnowledgeTool,
    TeamsTool,
)
from bulldogent.llm.tool.registry import ToolRegistry
from bulldogent.messaging.platform.registry import get_platform_registry
from bulldogent.teams import TeamsConfig, load_teams_config
from bulldogent.util import PROJECT_ROOT, load_yaml_config
from bulldogent.util.db import configure_engine, init_db
from bulldogent.util.logging import configure_logging

_logger = structlog.get_logger()
_TOOLS_CONFIG_PATH = PROJECT_ROOT / "config" / "tools.yaml"
_OBSERVABILITY_CONFIG_PATH = PROJECT_ROOT / "config" / "observability.yaml"


def _register_tools(
    tool_registry: ToolRegistry,
    teams_config: TeamsConfig | None = None,
) -> None:
    tool_config = load_yaml_config(_TOOLS_CONFIG_PATH)

    if jira_cfg := tool_config.get("jira"):
        try:
            url = jira_cfg.get("url", "")
            username = jira_cfg.get("username", "")
            api_token = jira_cfg.get("api_token", "")

            if not all([url, username, api_token]):
                _logger.debug("tool_skipped", tool="jira", reason="missing config")
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
            token = github_cfg.get("token", "")

            if not token:
                _logger.debug("tool_skipped", tool="github", reason="missing config")
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
            url = confluence_cfg.get("url", "")
            username = confluence_cfg.get("username", "")
            api_token = confluence_cfg.get("api_token", "")

            if not url:
                _logger.debug("tool_skipped", tool="confluence", reason="missing config")
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


def _init_retriever(
    config: BaselineConfig,
    embedding_provider: AbstractEmbeddingProvider,
) -> BaselineRetriever | None:
    try:
        retriever = BaselineRetriever(
            embedding_provider=embedding_provider,
            retrieval_config=config.retrieval,
        )
        _logger.info("baseline_retriever_loaded")
        return retriever
    except Exception:
        _logger.debug("baseline_init_skipped", exc_info=True)
        return None


def _init_learner(
    config: BaselineConfig,
    embedding_provider: AbstractEmbeddingProvider,
) -> Learner | None:
    learning = config.learning
    if not learning or not learning.enabled:
        return None

    try:
        chunker = Chunker(
            chunk_size=config.chunking.chunk_size,
            overlap=config.chunking.overlap,
        )
        learner = Learner(embedding_provider=embedding_provider, chunker=chunker)
        _logger.info("learner_loaded")
        return learner
    except Exception:
        _logger.debug("learner_init_failed", exc_info=True)
        return None


def _init_logging() -> None:
    try:
        obs_config = load_yaml_config(_OBSERVABILITY_CONFIG_PATH)
        logging_config = obs_config.get("logging", {})
    except Exception:
        configure_logging()
        return

    json_output = logging_config.get("json_output", True)
    log_level = logging_config.get("log_level", "INFO")
    configure_logging(json_output=bool(json_output), log_level=str(log_level))


def main() -> None:
    _init_logging()

    platform_registry = get_platform_registry()
    provider_registry = get_provider_registry()
    tool_registry = ToolRegistry()

    config = load_baseline_config()
    configure_engine(config.database_url)
    init_db()

    teams_config: TeamsConfig = load_teams_config()
    event_emitter = EventEmitter()
    approval_manager = ApprovalManager(event_emitter=event_emitter)

    embedding_provider = create_embedding_provider(config.embedding)
    retriever = _init_retriever(config, embedding_provider)
    learner = _init_learner(config, embedding_provider)

    _register_tools(tool_registry, teams_config=teams_config)

    if retriever:
        try:
            tool_registry.register(KnowledgeTool(config={}, retriever=retriever))
        except Exception:
            _logger.debug("tool_skipped", tool="knowledge")

    if teams_config.teams or teams_config.user_mappings:
        try:
            tool_registry.register(TeamsTool({"teams_config": teams_config}))
        except Exception:
            _logger.debug("tool_skipped", tool="teams")

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
            retriever=retriever,
            learner=learner,
            event_emitter=event_emitter,
            teams_config=teams_config,
        )
        platform.on_message(bot.handle)
        platform.on_reaction(bot.handle_reaction)
        t = threading.Thread(target=platform.start, name=f"platform-{platform_name}", daemon=True)
        t.start()

    _logger.info("all_platforms_started")

    shutdown = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: shutdown.set())
    signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
    shutdown.wait()

    event_emitter.shutdown()


if __name__ == "__main__":
    main()
