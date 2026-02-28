# Architecture

Bulldogent uses **Protocol/ABC-based abstractions** with a registry+factory pattern throughout. Each layer follows the same structure:

```
AbstractBase  ->  Adapter implementations  ->  Registry (collects)  ->  Factory (creates from config)
```

Each layer is independently extensible -- add a new platform, provider, or tool by implementing the abstract interface and registering it.

## High-level flow

```
@mention --> Bot orchestrator --> Agentic loop (max 15 steps)
                  |
                  +---------------------+--------------------+--------------------+
                  |                     |                    |                    |
          +---------------+    +--------------+    +--------------+    +-----------------+
          |   Messaging   |    |     LLM      |    |    Tools     |    |    Approval     |
          |   Platforms   |    |   Providers   |    |   Registry   |    |    Manager      |
          +---------------+    +--------------+    +--------------+    +-----------------+
          | Slack         |    | OpenAI       |    | Jira         |    | Per-operation   |
          |               |    | Bedrock      |    | Confluence   |    | Per-project     |
          |               |    | Vertex       |    | GitHub       |    | Reaction-based  |
          |               |    |              |    | Knowledge    |    |                 |
          +---------------+    +--------------+    +--------------+    +-----------------+
                                                         |
                                                 +--------------+
                                                 |   Baseline   |
                                                 |     RAG      |
                                                 +--------------+
                                                 | Crawlers     |
                                                 | Chunker      |
                                                 | Embedding    |
                                                 | Retriever    |
                                                 | Learner      |
                                                 +--------------+
                                                         |
                                                 +--------------+
                                                 |  PostgreSQL  |
                                                 |  + pgvector  |
                                                 +--------------+
```

## Package layout

```
src/bulldogent/
+-- __main__.py                   # Entry point -- wires registries, starts platforms
+-- bot.py                        # Agentic loop orchestrator
+-- approval.py                   # Thread-safe reaction-based approval manager
+-- teams.py                      # Shared team/user identity mapping (loaded from teams.yaml)
+-- messaging/platform/           # Chat platform abstraction
|   +-- platform.py               #   AbstractPlatform interface
|   +-- config.py / registry.py / factory.py
|   +-- adapter/
|       +-- slack.py              #   Slack (Socket Mode)
+-- llm/
|   +-- provider/                 # LLM provider abstraction
|   |   +-- provider.py           #   AbstractProvider.complete()
|   |   +-- types.py              #   Message, Response, TokenUsage
|   |   +-- config.py / registry.py / factory.py
|   |   +-- adapters/
|   |       +-- openai.py         #   OpenAI (+ LiteLLM-compatible endpoints)
|   |       +-- bedrock.py        #   AWS Bedrock (Claude)
|   |       +-- vertex.py         #   Google Vertex (Gemini)
|   +-- tool/                     # Tool abstraction + registry
|       +-- tool.py               #   AbstractTool with YAML-driven operations
|       +-- registry.py           #   Routes execution, resolves approval groups
|       +-- adapters/
|           +-- jira/             #   jira.py + operations.yaml
|           +-- confluence/       #   confluence.py + operations.yaml
|           +-- github/           #   github.py + operations.yaml
|           +-- knowledge/        #   knowledge.py + operations.yaml (auto-registered)
+-- baseline/                     # RAG subsystem
|   +-- __main__.py               #   CLI: python -m bulldogent.baseline index
|   +-- indexer.py                #   Orchestrates crawl -> chunk -> embed -> store
|   +-- retriever.py              #   pgvector cosine similarity search
|   +-- learner.py                #   Stores successful Q&A pairs
|   +-- chunker.py                #   Token-based overlapping chunker (tiktoken)
|   +-- summarizer.py             #   LLM-powered one-line file summaries for better retrieval
|   +-- models.py                 #   SQLAlchemy ORM (Knowledge table)
|   +-- config.py                 #   Dataclass configs for all baseline components
|   +-- crawlers/
|       +-- confluence.py         #   Crawls Confluence spaces
|       +-- github.py             #   Crawls GitHub repos (READMEs, issues, files)
|       +-- jira.py               #   Crawls Jira projects
|       +-- local.py              #   Crawls local markdown/text files
+-- embedding/                    # Provider-agnostic embedding
|   +-- provider.py               #   AbstractEmbeddingProvider.embed()
|   +-- config.py / __init__.py   #   Factory: create_embedding_provider()
|   +-- adapters/
|       +-- openai.py             #   OpenAI (text-embedding-3-small)
|       +-- bedrock.py            #   AWS Bedrock
|       +-- vertex.py             #   Google Vertex
+-- events/                       # Event analytics subsystem
|   +-- __main__.py               #   CLI: python -m bulldogent.events push
|   +-- emitter.py                #   Async queue + background thread for staging events
|   +-- models.py                 #   StagedEvent ORM (staged_events table)
|   +-- types.py                  #   EventType enum
|   +-- config.py                 #   EventStageConfig
+-- util/
    +-- yaml.py                   #   YAML loader with $(VAR) env interpolation
    +-- db.py                     #   SQLAlchemy engine + session context manager
    +-- logging.py                #   Structured logging (JSON in prod, console in dev)
```

## Tools

| Tool | Library | Operations |
|------|---------|------------|
| **Jira** | `atlassian-python-api` | search issues (structured filters + JQL), get issue, list issue types, create, update (with status transitions), delete |
| **Confluence** | `atlassian-python-api` | search pages (CQL), get page content, get child pages, list spaces |
| **GitHub** | `PyGithub` | issues (list, create), PRs (list, get, files, merge), comments, releases (list, get, publish), workflows (list, runs, jobs) |
| **Knowledge** | built-in | semantic search over indexed RAG baseline (auto-registered) |

Tools are YAML-driven -- each adapter has an `operations.yaml` that defines parameters and descriptions. The LLM sees these as callable functions. Adding a new tool operation = add YAML + implement the handler in `run()`.

## Key patterns

- **YAML-driven tool definitions**: Each tool adapter has an `operations.yaml` next to it. The LLM sees these as callable functions.
- **Config is YAML + env vars**: YAML files define structure and env var *names* using `$(VAR)` syntax; `.env` provides actual values. Unconfigured platforms/providers/tools are silently skipped.
- **Thread-aware conversations**: When a message arrives in a thread, `Bot._build_conversation()` fetches thread history and maps messages to USER/ASSISTANT roles by checking `bot_user_id`.
- **User identity injection**: When `teams.yaml` is configured, the bot resolves the asking user's platform ID to their full identity (name, email, team membership, role groups) and injects it as context into the conversation.
- **Bot personality** is defined in `config/prompts.yaml` (system prompt, approval messages, error messages). The bot character is a French Bulldog named "Tokyo".
