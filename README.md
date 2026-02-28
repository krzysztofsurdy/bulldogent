![Bulldogent](./logo.png)

# Bulldogent

**Agentic AI bot that lives in your team chat and gets things done.**

Bulldogent is an AI assistant that responds to @mentions in Slack. It connects to your team's knowledge sources -- Jira, Confluence, GitHub, and the web -- through an agentic tool-calling loop where the LLM decides what to search and when. Sensitive operations like creating issues or merging PRs go through a configurable approval workflow before execution. A RAG baseline system backed by PostgreSQL + pgvector indexes organizational knowledge and injects relevant context into every conversation.

## Features

- **Slack integration** -- responds to @mentions, threads, DMs, and emoji reactions
- **Provider-agnostic LLM** -- OpenAI, AWS Bedrock (Claude), Google Vertex AI (Gemini)
- **Agentic tool calling** -- LLM autonomously decides which tools to use across multiple reasoning steps (max 15 iterations)
- **Knowledge sources** -- Jira, Confluence, GitHub
- **RAG baseline** -- indexes Confluence, GitHub, Jira, and local docs into PostgreSQL + pgvector for automatic context injection
- **Approval gates** -- configurable per-operation and per-project approval groups with reaction-based voting
- **Thread-aware** -- maintains conversation context across message threads
- **Self-learning** -- optionally stores successful Q&A pairs for future retrieval
- **Event analytics** -- stages conversation events in PostgreSQL for observability
- **Structured logging** -- JSON output to stdout

## Quick start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- PostgreSQL 18 with pgvector (optional -- only needed for RAG baseline)

### Install

```bash
git clone <repo-url> && cd bulldogent
make install
```

### Configure

```bash
cp .env.example .env
cp config/tools.yaml.example config/tools.yaml
cp config/platforms.yaml.example config/platforms.yaml
cp config/providers.yaml.example config/providers.yaml
cp config/teams.yaml.example config/teams.yaml                # optional -- user/team identity mapping
cp config/baseline.yaml.example config/baseline.yaml          # optional -- for RAG
cp config/observability.yaml.example config/observability.yaml # optional -- logging + event sink
```

Edit `.env` with your credentials. You only need to configure the platforms and providers you want to use -- unconfigured ones are silently skipped.

**Minimum viable setup** (Slack + OpenAI):
```env
PLATFORM_SLACK_LLM_PROVIDER=openai
PLATFORM_SLACK_BOT_TOKEN=xoxb-...
PLATFORM_SLACK_APP_TOKEN=xapp-...
PROVIDER_OPENAI_API_KEY=sk-...
PROVIDER_OPENAI_MODEL=gpt-4o
```

### Run

```bash
make run
```

### Docker

```bash
make docker-up       # starts bot + PostgreSQL (pgvector)
make docker-index    # run baseline indexer against configured sources
make docker-down     # stop everything
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System design, package layout, tools, key patterns |
| [Configuration](docs/configuration.md) | Full config reference: env vars, YAML files, approval rules |
| [Baseline RAG](docs/baseline.md) | Knowledge indexing, retrieval, summarization, self-learning |
| [Contributing](CONTRIBUTING.md) | Development setup, code style, adding tools/platforms, testing |
