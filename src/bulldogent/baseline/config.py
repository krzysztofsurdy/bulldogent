from dataclasses import dataclass, field
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
class ConfluenceSourceConfig:
    spaces: list[str] = field(default_factory=list)
    max_pages: int = 500


@dataclass
class GitHubRepoConfig:
    name: str
    include: list[str] = field(default_factory=lambda: [])
    summarize: bool = True


@dataclass
class GitHubSourceConfig:
    repositories: list[GitHubRepoConfig] = field(default_factory=list)
    include: list[str] = field(default_factory=lambda: ["readme"])
    exclude_patterns: list[str] = field(default_factory=list)


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
    min_score: float = 0.3  # similarity threshold (1 - cosine distance)


@dataclass
class ChunkingConfig:
    chunk_size: int = 500
    overlap: int = 50


@dataclass
class LearningConfig:
    enabled: bool = False


@dataclass
class SummarizerConfig:
    model: str
    api_key: str
    api_url: str | None = None


@dataclass
class BaselineConfig:
    database_url: str
    embedding: AbstractEmbeddingConfig
    dimensions: int
    sources: SourcesConfig
    retrieval: RetrievalConfig
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    learning: LearningConfig | None = None
    summarizer: SummarizerConfig | None = None


def load_baseline_config() -> BaselineConfig:
    raw = load_yaml_config(
        _BASELINE_CONFIG_PATH,
        required_vars={"DATABASE_URL"},
    )
    return _parse_config(raw)


def _parse_config(raw: dict[str, Any]) -> BaselineConfig:
    database_url = raw.get("database_url", "")
    if not database_url:
        raise ValueError("Missing 'database_url' in baseline config")

    if "embedding" not in raw:
        raise ValueError("Missing 'embedding' section in baseline config")

    embedding_raw = raw.get("embedding", {})
    if "provider" not in embedding_raw:
        raise ValueError("Missing 'embedding.provider' in baseline config")

    embedding = _parse_embedding_config(embedding_raw)
    dimensions = int(embedding_raw.get("dimensions", 1536))

    sources_raw = raw.get("sources", {})
    confluence_raw = sources_raw.get("confluence", {})
    github_raw = sources_raw.get("github", {})
    jira_raw = sources_raw.get("jira", {})
    local_raw = sources_raw.get("local", {})

    retrieval_raw = raw.get("retrieval", {})

    chunking_raw = raw.get("chunking", {})
    learning = _parse_learning(raw.get("learning"))
    summarizer = _parse_summarizer(raw.get("summarizer"))

    return BaselineConfig(
        database_url=database_url,
        embedding=embedding,
        dimensions=dimensions,
        sources=SourcesConfig(
            confluence=ConfluenceSourceConfig(
                spaces=confluence_raw.get("spaces", []),
                max_pages=confluence_raw.get("max_pages", 500),
            ),
            github=_parse_github_config(github_raw),
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
        chunking=ChunkingConfig(
            chunk_size=chunking_raw.get("chunk_size", 500),
            overlap=chunking_raw.get("overlap", 50),
        ),
        learning=learning,
        summarizer=summarizer,
    )


def _parse_github_config(raw: dict[str, Any]) -> GitHubSourceConfig:
    global_include = raw.get("include", ["readme"])
    exclude_patterns = raw.get("exclude_patterns", [])
    repos: list[GitHubRepoConfig] = []
    for entry in raw.get("repositories", []):
        if isinstance(entry, str):
            repos.append(GitHubRepoConfig(name=entry))
        elif isinstance(entry, dict):
            name = next(iter(entry))
            repo_raw = entry[name]
            repo_include = repo_raw.get("include", [])
            repo_summarize = repo_raw.get("summarize", True)
            repos.append(
                GitHubRepoConfig(name=name, include=repo_include, summarize=repo_summarize)
            )
    return GitHubSourceConfig(
        repositories=repos,
        include=global_include,
        exclude_patterns=exclude_patterns,
    )


def _parse_embedding_config(raw: dict[str, Any]) -> AbstractEmbeddingConfig:
    provider_key = raw.get("provider", "openai")
    provider_type = EmbeddingProviderType(provider_key)

    model = raw.get("model", "")
    if not model:
        raise ValueError("Missing 'embedding.model' in baseline config")

    provider_raw = raw.get(provider_key, {})

    match provider_type:
        case EmbeddingProviderType.OPENAI:
            return OpenAIEmbeddingConfig.from_yaml(provider_raw, model)
        case EmbeddingProviderType.BEDROCK:
            return BedrockEmbeddingConfig.from_yaml(provider_raw, model)
        case EmbeddingProviderType.VERTEX:
            return VertexEmbeddingConfig.from_yaml(provider_raw, model)


def _parse_learning(raw: dict[str, Any] | None) -> LearningConfig | None:
    if not raw or not raw.get("enabled", False):
        return None

    return LearningConfig(enabled=True)


def _parse_summarizer(raw: dict[str, Any] | None) -> SummarizerConfig | None:
    if not raw or not raw.get("enabled", False):
        return None

    model = raw.get("model", "")
    api_key = raw.get("api_key", "")
    if not model or not api_key:
        return None

    return SummarizerConfig(
        model=model,
        api_key=api_key,
        api_url=raw.get("api_url"),
    )
