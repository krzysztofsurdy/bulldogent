# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Is This

Bulldogent is an agentic AI chatbot that lives in Slack. It responds to @mentions, connects to knowledge sources (Jira, Confluence, GitHub) through an agentic tool-calling loop, and gates sensitive operations behind reaction-based approval workflows. It also has a RAG baseline system (PostgreSQL + pgvector) for indexing and retrieving organizational knowledge.

## Commands

```bash
make install        # uv sync --dev
make run            # source .env && run the bot
make test           # pytest with coverage
make lint           # ruff check src/ tests/
make format         # ruff format src/ tests/
make typecheck      # mypy --strict src/
make check          # lint + typecheck + test (all three)
make fix            # ruff --fix + format

# RAG indexing
make index          # index all sources into ChromaDB
make index-jira     # index only Jira
make index-confluence
make index-github
make index-local

# Run a single test
uv run pytest tests/test_foo.py::TestClass::test_method -v
```

Pre-commit hooks run ruff, ruff-format, mypy (strict, src/ only), and pytest on every commit.

## Architecture

The codebase uses **Protocol/ABC-based abstractions** with a registry+factory pattern throughout. Each layer (messaging, LLM, tools, embedding) follows the same structure:

```
AbstractBase -> adapter implementations -> registry (collects) -> factory (creates from config)
```

### Package layout (`src/bulldogent/`)

- **`__main__.py`** -- Entry point. Wires together all registries, registers tools from `config/tools.yaml`, creates a `Bot` per platform, starts listening.
- **`bot.py`** -- Core orchestrator. Runs the agentic loop (max 15 iterations): builds conversation from thread history, calls LLM, executes tool calls, feeds results back, repeats until text response. Injects RAG baseline context before the first LLM call.
- **`approval.py`** -- Thread-safe approval manager. Tool operations flagged in the approvals section of `config/platforms.yaml` block until a member of the approval group reacts with the configured emoji (5min timeout).
- **`messaging/platform/`** -- Chat platform abstraction. `AbstractPlatform` defines `send_message`, `add_reaction`, `get_thread_messages`, `on_message`, `on_reaction`, `start`. Adapter: Slack (Socket Mode).
- **`llm/provider/`** -- LLM provider abstraction. `AbstractProvider.complete()` takes conversation messages + optional tool operations, returns `TextResponse` or `ToolUseResponse`. Adapters: OpenAI, Bedrock (Claude), Vertex (Gemini).
- **`llm/tool/`** -- Tool abstraction. `AbstractTool` loads operations from a co-located `operations.yaml` that defines parameters as JSON Schema. `ToolRegistry` collects tools, exposes flat operation list to LLM, routes execution, resolves approval groups with two-level hierarchy (project override -> operation default).
- **`baseline/`** -- RAG subsystem. `Indexer` pulls from Jira/Confluence/GitHub/local files, chunks with `Chunker`, stores in ChromaDB. `BaselineRetriever` queries by embedding similarity. `Learner` stores successful Q&A pairs into a separate "learned" collection. `CompositeRetriever` merges results from both collections.
- **`embedding/`** -- Provider-agnostic embedding. `AbstractEmbeddingProvider.embed()` returns vectors. Adapters: OpenAI, Bedrock, Vertex.

### Key patterns

- **YAML-driven tool definitions**: Each tool adapter has an `operations.yaml` next to it. The LLM sees these as callable functions. Adding a new tool operation = add YAML + implement the handler in `run()`.
- **Config is YAML + env vars**: YAML files define structure and env var *names*; `.env` provides actual values. Unconfigured platforms/providers/tools are silently skipped.
- **Thread-aware conversations**: When a message arrives in a thread, `Bot._build_conversation()` fetches thread history and maps messages to USER/ASSISTANT roles by checking `bot_user_id`.
- **Bot personality** is defined in `config/prompts.yaml` (system prompt, approval messages, error messages). The bot character is a French Bulldog named "Tokyo".

## Code Style

- Python 3.12+, managed with `uv`
- Ruff for linting (rules: E, W, F, I, N, UP) and formatting (double quotes, 100 char line length)
- mypy strict mode -- all functions must have type annotations
- structlog for logging throughout
- Slack-flavored markdown in bot output (`*bold*` not `**bold**`, no `#` headers)

## Key Documentation Files

@README.md
@CONTRIBUTING.md
@.env.example
@config/tools.yaml.example
@config/platforms.yaml.example
@config/providers.yaml.example
@config/baseline.yaml.example
@config/observability.yaml.example
@config/prompts.yaml
