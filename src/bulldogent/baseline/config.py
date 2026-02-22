import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bulldogent.embedding.config import (
    AbstractEmbeddingConfig,
    BedrockEmbeddingConfig,
    EmbeddingProviderType,
    OpenAIEmbeddingConfig,
    VertexEmbeddingConfig,
)
from bulldogent.util import PROJECT_ROOT, load_yaml_config

_BASELINE_CONFIG_PATH = PROJECT_ROOT / "config" / "baseline.yaml"


@dataclass
class StorageConfig:
    path: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "baseline")


@dataclass
class ConfluenceSourceConfig:
    spaces: list[str] = field(default_factory=list)
    max_pages: int = 500


@dataclass
class GitHubSourceConfig:
    repositories: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=lambda: ["readme"])


@dataclass
class JiraSourceConfig:
    projects: list[str] = field(default_factory=list)
    max_issues: int = 200


@dataclass
class LocalSourceConfig:
    paths: list[str] = field(default_factory=list)


@dataclass
class SourcesConfig:
    confluence: ConfluenceSourceConfig = field(default_factory=ConfluenceSourceConfig)
    github: GitHubSourceConfig = field(default_factory=GitHubSourceConfig)
    jira: JiraSourceConfig = field(default_factory=JiraSourceConfig)
    local: LocalSourceConfig = field(default_factory=LocalSourceConfig)


@dataclass
class RetrievalConfig:
    top_k: int = 5
    max_tokens: int = 1000
    min_score: float = 0.3  # ChromaDB distance threshold — lower = more similar


@dataclass
class LearningPersistentConfig:
    path: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "learned")


@dataclass
class LearningHttpConfig:
    host: str = ""
    port: int = 8000
    ssl: bool = False


@dataclass
class LearningConfig:
    enabled: bool = False
    backend: str = "persistent"  # "persistent" | "http"
    persistent: LearningPersistentConfig = field(default_factory=LearningPersistentConfig)
    http: LearningHttpConfig = field(default_factory=LearningHttpConfig)
    collection: str = "learned"


@dataclass
class BaselineConfig:
    embedding: AbstractEmbeddingConfig
    storage: StorageConfig
    sources: SourcesConfig
    retrieval: RetrievalConfig
    learning: LearningConfig | None = None


def load_baseline_config() -> BaselineConfig:
    raw = load_yaml_config(_BASELINE_CONFIG_PATH)
    return _parse_config(raw)


def _parse_config(raw: dict[str, Any]) -> BaselineConfig:
    embedding = _parse_embedding_config(raw.get("embedding", {}))

    storage_raw = raw.get("storage", {})
    storage_path = Path(storage_raw.get("path", "data/baseline"))
    if not storage_path.is_absolute():
        storage_path = PROJECT_ROOT / storage_path

    sources_raw = raw.get("sources", {})
    confluence_raw = sources_raw.get("confluence", {})
    github_raw = sources_raw.get("github", {})
    jira_raw = sources_raw.get("jira", {})
    local_raw = sources_raw.get("local", {})

    retrieval_raw = raw.get("retrieval", {})

    learning = _parse_learning(raw.get("learning"))

    return BaselineConfig(
        embedding=embedding,
        storage=StorageConfig(path=storage_path),
        sources=SourcesConfig(
            confluence=ConfluenceSourceConfig(
                spaces=confluence_raw.get("spaces", []),
                max_pages=confluence_raw.get("max_pages", 500),
            ),
            github=GitHubSourceConfig(
                repositories=github_raw.get("repositories", []),
                include=github_raw.get("include", ["readme"]),
            ),
            jira=JiraSourceConfig(
                projects=jira_raw.get("projects", []),
                max_issues=jira_raw.get("max_issues", 200),
            ),
            local=LocalSourceConfig(
                paths=local_raw.get("paths", []),
            ),
        ),
        retrieval=RetrievalConfig(
            top_k=retrieval_raw.get("top_k", 5),
            max_tokens=retrieval_raw.get("max_tokens", 1000),
            min_score=retrieval_raw.get("min_score", 0.3),
        ),
        learning=learning,
    )


def _parse_embedding_config(raw: dict[str, Any]) -> AbstractEmbeddingConfig:
    provider_key = raw.get("provider", "openai")
    provider_type = EmbeddingProviderType(provider_key)

    model = os.getenv(raw.get("model_env", ""), "")
    if not model:
        raise ValueError(f"Missing env var: {raw.get('model_env', '')}")

    provider_raw = raw.get(provider_key, {})

    match provider_type:
        case EmbeddingProviderType.OPENAI:
            return OpenAIEmbeddingConfig.from_envs(provider_raw, model)
        case EmbeddingProviderType.BEDROCK:
            return BedrockEmbeddingConfig.from_envs(provider_raw, model)
        case EmbeddingProviderType.VERTEX:
            return VertexEmbeddingConfig.from_envs(provider_raw, model)


def _parse_learning(raw: dict[str, Any] | None) -> LearningConfig | None:
    if not raw or not raw.get("enabled", False):
        return None

    persistent_raw = raw.get("persistent", {})
    persistent_path = Path(persistent_raw.get("path", "data/learned"))
    if not persistent_path.is_absolute():
        persistent_path = PROJECT_ROOT / persistent_path

    http_raw = raw.get("http", {})

    return LearningConfig(
        enabled=True,
        backend=raw.get("backend", "persistent"),
        persistent=LearningPersistentConfig(path=persistent_path),
        http=LearningHttpConfig(
            host=http_raw.get("host", ""),
            port=http_raw.get("port", 8000),
            ssl=http_raw.get("ssl", False),
        ),
        collection=raw.get("collection", "learned"),
    )
