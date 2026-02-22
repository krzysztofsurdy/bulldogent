from dataclasses import dataclass, field


@dataclass
class Chunk:
    content: str
    source: str  # confluence | github | jira | local
    title: str
    url: str  # URL or file path
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    content: str
    source: str
    title: str
    url: str
    score: float  # ChromaDB distance — lower is more similar
