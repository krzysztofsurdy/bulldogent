# SlackBot AI Assistant — Project Plan

## Vision

A Slack bot that responds to @mentions, uses an LLM (Claude via AWS Bedrock) to generate answers, and pulls context from Confluence, Jira, GitHub, and Slack history. The LLM provider sits behind an abstraction layer so it can be swapped (Bedrock today, OpenAI tomorrow, local model next year).

**Architecture:** Agentic LLM with tool calling (MCP-style) — the LLM decides what information to retrieve via tool use, not pre-fetching all sources. See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed design.

---

## Architecture Overview

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Slack API  │────▶│   Bot Core       │────▶│  LLM Provider       │
│  (Events)    │◀────│   (Orchestrator) │◀────│  (Abstraction Layer) │
└─────────────┘     └──────┬───────────┘     └─────────────────────┘
                           │
                    ┌──────┴───────┐
                    │  Knowledge    │
                    │  Sources      │
                    ├──────────────┤
                    │ Confluence   │
                    │ Jira         │
                    │ GitHub       │
                    │ Slack History│
                    └──────────────┘
```

### Key Design Decisions

| Decision | Choice | Why |
|---|---|---|
| Slack library | `slack-bolt` | Official SDK, handles events/reactions/threads natively |
| LLM abstraction | Strategy pattern via Protocol (Python's "interface") | Provider-agnostic, easy to swap |
| **Knowledge retrieval** | **Tool calling / function calling (agentic)** | **LLM decides what to search, not pre-fetching all sources. More efficient, enables multi-step reasoning** |
| HTTP client | `httpx` | Modern async-capable HTTP client (think Guzzle but Python) |
| Config | `pydantic-settings` | Typed config from env vars with validation |
| Testing | `pytest` | The standard — like PHPUnit but more Pythonic |
| Async | Start sync, migrate later | Learn fundamentals first, async is a separate skill |
| Type hints | Everywhere | Good practice, essential for ML/DL later, closest to PHP typed properties |

---

## PHP → Python Concept Map

| PHP | Python | Notes |
|---|---|---|
| `composer.json` | `pyproject.toml` | Modern Python uses this, not `setup.py` |
| `composer install` | `pip install -e ".[dev]"` | `-e` = editable install (like symlink) |
| `vendor/` | `.venv/` | Virtual env = isolated dependency tree |
| `interface Foo {}` | `class Foo(Protocol)` | Structural typing — no need to `implements` |
| `__construct(private readonly X $x)` | `def __init__(self, x: X)` + `self.x = x` | Or use `@dataclass` for DTOs |
| `namespace App\Service` | Module system — file = module, folder = package | `from app.service import MyClass` |
| `private function` | `def _method(self)` | Convention, not enforced (`_` prefix = private) |
| `array` / `Collection` | `list`, `dict`, `dataclass` | Python has powerful built-in data structures |
| `?string` (nullable) | `str \| None` or `Optional[str]` | Union types, same concept |
| `.env` + `vlucas/dotenv` | `.env` + `pydantic-settings` | Typed, validated, with defaults |
| PHPUnit | pytest | Less boilerplate, fixture-based, no class required |
| PHPStan | mypy / pyright | Static type checking — use from day one |
| `php-cs-fixer` | `ruff` | Linter + formatter in one, extremely fast |
| `try/catch` | `try/except` | Same concept, different keyword |
| `throw new Exception()` | `raise Exception()` | `raise` not `throw` |
| Monolog | `structlog` or stdlib `logging` | Structured logging |
| Symfony DI Container | No framework needed — just constructor injection | Python is simpler here, manual DI or `dependency-injector` |

---

## Python Concepts You'll Learn Per Milestone

These are the Python-specific things that will be new coming from PHP:

### Fundamentals (across all milestones)
- **Virtual environments** — isolated dependency spaces (no global `vendor/`)
- **`pyproject.toml`** — the modern `composer.json`
- **Type hints** — optional but we'll use them everywhere
- **f-strings** — `f"Hello {name}"` (like PHP `"Hello {$name}"`)
- **List/dict comprehensions** — `[x for x in items if x.active]` (no equivalent in PHP)
- **Context managers** — `with open(file) as f:` (like try-with-resources)
- **Decorators** — `@app.route("/")` (like PHP attributes but callable)
- **`dataclass`** — auto-generates `__init__`, `__repr__`, `__eq__` (like Symfony's `#[AsDTO]` but built-in)
- **Protocol** — structural typing / duck typing formalized (like interfaces without `implements`)
- **Pattern matching** — `match/case` (PHP 8's `match` but more powerful)

### ML/DL Preparation (habits to build now)
- Use **type hints** religiously — ML libraries are fully typed
- Get comfortable with **list comprehensions** and **generators** — data pipelines use them everywhere
- Learn **dataclasses** well — they map to ML data structures
- Understand **virtual environments** deeply — ML has complex dependency chains
- Write **pure functions** where possible — functional style dominates ML code

---

## Milestones & Tickets

---

### Milestone 0: Project Scaffolding & Python Fundamentals

**Goal:** Working project structure, tooling, and your first Python file that runs.

**Learning focus:** Python project structure, virtual environments, dependency management, type hints, linting.

#### Ticket 0.1 — Project structure & tooling setup
**What:** Create the project skeleton with proper Python packaging.

**Structure to create:**
```
slackbot/
├── pyproject.toml          # Package config + dependencies
├── .python-version         # Pin Python version
├── .env.example            # Required env vars template
├── .gitignore
├── README.md
├── src/
│   └── slackbot/
│       ├── __init__.py     # Makes it a package (like namespace autoloading)
│       ├── config.py       # Settings via pydantic-settings
│       └── main.py         # Entry point
└── tests/
    ├── __init__.py
    ├── conftest.py         # Shared fixtures (like PHPUnit setUp but better)
    └── test_config.py
```

**Acceptance criteria:**
- [ ] `pyproject.toml` with project metadata, dependencies section, and dev dependencies
- [ ] `ruff` configured for linting + formatting (in `pyproject.toml`)
- [ ] `mypy` configured for strict type checking
- [ ] `pytest` runs and finds the test directory
- [ ] `.gitignore` covers Python artifacts (`.pyc`, `__pycache__`, `.venv`, `.env`)
- [ ] `git init` + initial commit

**Key learnings:**
- `__init__.py` files — what they do (package markers, like PSR-4 but explicit)
- `src/` layout — why the `src/` folder exists (prevents import confusion)
- editable installs — `pip install -e ".[dev]"` makes your package importable

**Hints:**
- Look up "Python src layout" — it's the modern recommended structure
- `pyproject.toml` uses TOML format (you may know it from PHP tools)
- Research `ruff` — it replaces `flake8`, `isort`, `black` in one tool

---

#### Ticket 0.2 — Configuration management with pydantic-settings
**What:** Create a typed, validated config system that reads from `.env`.

**Acceptance criteria:**
- [ ] `Settings` class using `pydantic-settings` with fields for: `slack_bot_token`, `slack_app_token`, `slack_signing_secret`, `aws_region`, `aws_bedrock_model_id`
- [ ] Validation: all fields required, no empty strings
- [ ] A test that verifies settings load from env vars
- [ ] `.env.example` file documenting all required vars

**Key learnings:**
- `BaseSettings` from pydantic — auto-reads env vars, validates types
- Python's `@dataclass` vs pydantic's `BaseModel` — when to use which
- Test fixtures with `monkeypatch` (pytest's way to mock env vars — like `putenv` in PHPUnit)

**Hints:**
- In PHP you'd do `$_ENV['SLACK_TOKEN']` or `getenv()`. Pydantic-settings does this + validation in one step.
- `model_config = SettingsConfigDict(env_file=".env")` — that's the magic line

---

### Milestone 1: Slack Connection — Listen & React

**Goal:** Bot connects to Slack, hears @mentions, reacts with emoji, replies in thread.

**Learning focus:** Event-driven programming in Python, decorators, basic async concepts.

#### Ticket 1.1 — Slack app setup (no code)
**What:** Create the Slack app in the Slack API dashboard and configure permissions.

**Acceptance criteria:**
- [ ] Slack App created at api.slack.com
- [ ] Bot Token Scopes: `app_mentions:read`, `chat:write`, `reactions:write`, `reactions:read`, `channels:history`, `channels:read`
- [ ] Event Subscriptions enabled for: `app_mention`
- [ ] Socket Mode enabled (easier for development — no public URL needed)
- [ ] App-Level Token created (for Socket Mode)
- [ ] Bot installed to workspace
- [ ] Tokens stored in `.env`

**Hints:**
- Socket Mode = WebSocket connection from your machine. No ngrok, no public URL.
- You need TWO tokens: Bot Token (`xoxb-`) and App-Level Token (`xapp-`)

---

#### Ticket 1.2 — Basic bot that echoes mentions
**What:** Bot listens for @mentions and replies in the same thread with "I heard you!".

**Acceptance criteria:**
- [ ] Bot starts, connects to Slack via Socket Mode
- [ ] When someone @mentions the bot, it adds a :eyes: reaction (acknowledges it heard)
- [ ] Bot replies in the thread with the original message echoed back
- [ ] After replying, bot adds a :white_check_mark: reaction (done processing)
- [ ] If something fails, bot adds a :x: reaction
- [ ] Graceful shutdown on Ctrl+C

**Key learnings:**
- `slack-bolt` framework — decorators to register event handlers (`@app.event("app_mention")`)
- Decorators in Python — how `@something` works (it's a function wrapping a function)
- `say()` function — slack-bolt's abstraction to reply
- `client.reactions_add()` — Slack API for emoji reactions
- `try/except/finally` — error handling pattern

**Hints:**
- In PHP Symfony you'd register an EventSubscriber. In slack-bolt, you use `@app.event("app_mention")`.
- The event payload gives you `channel`, `ts` (timestamp = message ID), `text`, `user`.
- To reply in a thread, pass `thread_ts=event["ts"]` to `say()`.

---

#### Ticket 1.3 — Structured logging
**What:** Add proper logging so you can debug what's happening.

**Acceptance criteria:**
- [ ] `structlog` configured with JSON output
- [ ] Log: bot startup, every mention received (channel, user, text preview), every reply sent
- [ ] Log level configurable via env var (`LOG_LEVEL=DEBUG`)
- [ ] No secrets in logs (mask tokens)

**Key learnings:**
- Python's `logging` stdlib module — how it differs from Monolog
- `structlog` — structured logging (like Monolog's JSON formatter but more Pythonic)
- Module-level loggers — `logger = structlog.get_logger(__name__)` (like LoggerAwareTrait)

**Hints:**
- `__name__` in Python = fully qualified module name (like `__CLASS__` in PHP)
- `structlog` wraps stdlib `logging` — configure both

---

### Milestone 2: LLM Abstraction Layer

**Goal:** Provider-agnostic LLM interface. Bedrock implementation. Bot uses LLM to answer.

**Learning focus:** Protocols (interfaces), abstract patterns in Python, `boto3` (AWS SDK), dependency injection without a container.

#### Ticket 2.1 — LLM Provider abstraction (Protocol + dataclasses)
**What:** Define the contract for any LLM provider.

**Acceptance criteria:**
- [ ] `LLMProvider` Protocol with method `complete(messages: list[Message]) -> LLMResponse`
- [ ] `Message` dataclass: `role: str`, `content: str`
- [ ] `LLMResponse` dataclass: `content: str`, `model: str`, `usage: TokenUsage`
- [ ] `TokenUsage` dataclass: `input_tokens: int`, `output_tokens: int`
- [ ] All in `src/slackbot/llm/` package
- [ ] Unit tests verifying dataclass creation and validation

**Key learnings:**
- `Protocol` — Python's structural typing (a class satisfies a Protocol if it has the right methods — no `implements` keyword needed!)
- `@dataclass` — auto `__init__`, `__repr__`, `__eq__` (like a PHP DTO with constructor promotion but automatic)
- `__all__` — controls what `from module import *` exports (like `public` visibility for a module)
- Packages — `__init__.py` in a folder makes it a package

**Hints:**
- In PHP: `interface LLMProvider { public function complete(array $messages): LLMResponse; }`
- In Python: `class LLMProvider(Protocol): def complete(self, messages: list[Message]) -> LLMResponse: ...`
- The `...` (Ellipsis) in Protocol = "no implementation" (like abstract method)

---

#### Ticket 2.2 — AWS Bedrock implementation
**What:** Implement `LLMProvider` for Claude via AWS Bedrock.

**Acceptance criteria:**
- [ ] `BedrockProvider` class that satisfies `LLMProvider` Protocol
- [ ] Uses `boto3` to call Bedrock's `converse` API
- [ ] Model ID configurable via settings
- [ ] Handles Bedrock-specific errors (throttling, model not available)
- [ ] System prompt configurable
- [ ] Unit tests with mocked boto3 client

**Key learnings:**
- `boto3` — AWS SDK for Python (like the AWS SDK for PHP)
- Mocking in pytest — `unittest.mock.patch` and `MagicMock` (like Prophecy/Mockery)
- Error handling — `botocore.exceptions.ClientError` (like catching AWS PHP SDK exceptions)

**Hints:**
- `boto3.client("bedrock-runtime")` — creates the client
- `client.converse(modelId=..., messages=...)` — the API call
- For mocking, look into `pytest-mock` (provides a `mocker` fixture) — cleaner than `unittest.mock` directly

---

#### Ticket 2.3 — Wire LLM into the bot
**What:** When mentioned, bot sends the message to the LLM and replies with the response.

**Acceptance criteria:**
- [ ] Bot extracts the user's message (strips the @mention prefix)
- [ ] Sends message to LLM provider
- [ ] Replies in thread with LLM response
- [ ] Reaction flow: :eyes: → (processing) → :white_check_mark: or :x:
- [ ] Token usage logged

**Key learnings:**
- Dependency injection without a container — just pass instances via constructors
- String manipulation — `text.replace(f"<@{bot_id}>", "").strip()`
- Composing objects — building the "app" by wiring dependencies in `main.py`

**Hints:**
- In PHP with Symfony, the DI container auto-wires. In Python, you just... pass things manually in `main.py`. It's simpler than you'd expect.
- Create a factory function: `def create_app(settings: Settings) -> App`

---

### Milestone 3: Knowledge Sources — Confluence

**Goal:** Bot can search and retrieve Confluence pages to provide context to the LLM.

**Learning focus:** HTTP clients, API integration, Protocol for knowledge sources, text processing.

#### Ticket 3.1 — Knowledge Source abstraction
**What:** Define a common interface for all knowledge sources.

**Acceptance criteria:**
- [ ] `KnowledgeSource` Protocol with methods:
  - `search(query: str) -> list[KnowledgeResult]`
  - `source_name` property returning `str`
- [ ] `KnowledgeResult` dataclass: `title: str`, `content: str`, `url: str`, `source: str`, `relevance_score: float`
- [ ] `KnowledgeAggregator` class that queries multiple sources and merges results
- [ ] Tests for aggregator with mock sources

**Key learnings:**
- Properties in Python — `@property` decorator (like PHP's `readonly` getter)
- Iterables and generators — `yield` keyword for lazy evaluation
- `sorted()` with `key=` parameter — functional-style sorting

**Hints:**
- `@property` makes a method behave like a property: `obj.source_name` not `obj.source_name()`
- Generators are huge in ML later — `yield` produces values lazily (like PHP generators but used way more)

---

#### Ticket 3.2 — Confluence integration
**What:** Implement `KnowledgeSource` for Confluence using its REST API.

**Acceptance criteria:**
- [ ] `ConfluenceSource` class satisfying `KnowledgeSource` Protocol
- [ ] Uses `httpx` to call Confluence REST API (`/wiki/rest/api/content/search`)
- [ ] Searches by CQL (Confluence Query Language)
- [ ] Extracts and cleans page content (strips HTML to plain text)
- [ ] Handles pagination (max N results)
- [ ] Rate limiting / retry on 429
- [ ] Tests with mocked HTTP responses

**Key learnings:**
- `httpx` — modern HTTP client (like Guzzle: `httpx.Client()` ≈ `new Client()`)
- HTML parsing — `beautifulsoup4` for stripping HTML (like PHP's `strip_tags` but smarter)
- Retry patterns — `tenacity` library for retry with backoff

**Hints:**
- `httpx.Client(base_url=..., headers=...)` persists config across requests (like Guzzle's base_uri)
- Confluence uses Basic Auth with API token: `httpx.BasicAuth(email, api_token)`

---

#### Ticket 3.3 — Context injection into LLM prompts
**What:** Combine knowledge source results into the LLM prompt.

**Acceptance criteria:**
- [ ] When bot receives a mention, it searches knowledge sources for relevant context
- [ ] Builds a system prompt with retrieved context
- [ ] LLM receives: system prompt (with context) + user's question
- [ ] Response includes source links when knowledge was used
- [ ] Context size is bounded (don't exceed token limits)

**Key learnings:**
- String templating — f-strings and `textwrap.dedent` for multi-line templates
- Token estimation — simple word-count heuristic or `tiktoken` library

---

### Milestone 4: More Knowledge Sources

**Goal:** Add Jira, GitHub, and Slack history as knowledge sources.

**Learning focus:** Working with multiple APIs, reusing abstractions, parallel execution.

#### Ticket 4.1 — Jira integration
**What:** Implement `KnowledgeSource` for Jira.

**Acceptance criteria:**
- [ ] `JiraSource` class satisfying `KnowledgeSource` Protocol
- [ ] Searches issues via JQL
- [ ] Returns issue key, summary, description, status, assignee
- [ ] Handles pagination
- [ ] Tests with mocked responses

**Hints:**
- Jira REST API v3: `/rest/api/3/search?jql=...`
- Auth same pattern as Confluence (both Atlassian)

---

#### Ticket 4.2 — GitHub integration
**What:** Implement `KnowledgeSource` for GitHub.

**Acceptance criteria:**
- [ ] `GitHubSource` class satisfying `KnowledgeSource` Protocol
- [ ] Searches: issues, PRs, code (configurable)
- [ ] Uses GitHub REST API or `PyGithub` library
- [ ] Respects rate limits
- [ ] Tests with mocked responses

**Hints:**
- GitHub has a Search API: `/search/issues?q=...`, `/search/code?q=...`
- `PyGithub` wraps the REST API nicely — evaluate if it's worth the dependency

---

#### Ticket 4.3 — Slack history as knowledge source
**What:** Search past Slack messages for relevant context.

**Acceptance criteria:**
- [ ] `SlackHistorySource` class satisfying `KnowledgeSource` Protocol
- [ ] Uses Slack's `search.messages` API
- [ ] Filters by channels (configurable allowlist)
- [ ] Returns message text, author, channel, permalink
- [ ] Tests with mocked Slack client

**Hints:**
- Needs additional scope: `search:read`
- `client.search_messages(query=...)` — built into slack-bolt's client

---

#### Ticket 4.4 — Parallel knowledge source queries
**What:** Query all knowledge sources concurrently, not sequentially.

**Acceptance criteria:**
- [ ] `KnowledgeAggregator` runs all source queries in parallel
- [ ] Timeout per source (don't let one slow source block everything)
- [ ] Failed sources log a warning but don't break the response
- [ ] Faster perceived response time

**Key learnings:**
- `concurrent.futures.ThreadPoolExecutor` — simple parallelism (like PHP's parallel/pthreads but actually usable)
- `as_completed()` — process results as they arrive
- This pattern is essential for ML data loading later

**Hints:**
- Start with `ThreadPoolExecutor` (thread-based). Async/await is a future milestone.
- `with ThreadPoolExecutor() as executor:` — context manager handles cleanup

---

### Milestone 5: Conversation Memory & Threading

**Goal:** Bot maintains conversation context within a Slack thread.

**Learning focus:** State management, data structures, caching patterns.

#### Ticket 5.1 — Thread-based conversation memory
**What:** Bot remembers previous messages in a Slack thread.

**Acceptance criteria:**
- [ ] When replying in a thread, include previous thread messages as conversation history
- [ ] Send full conversation history to LLM (system prompt + all messages in thread)
- [ ] Limit history to last N messages or T tokens
- [ ] Memory is per-thread (not global)
- [ ] Old threads are cleaned up (TTL-based eviction)

**Key learnings:**
- `dict` as cache — `{thread_ts: [messages]}` (like PHP arrays but typed)
- `collections.defaultdict` — auto-initializing dict
- TTL eviction — simple time-based cleanup

---

#### Ticket 5.2 — Smart context: only fetch knowledge when needed
**What:** Not every message needs a knowledge search. Detect when to search.

**Acceptance criteria:**
- [ ] If the user asks a follow-up (short message in existing thread), skip knowledge search
- [ ] If the user asks a new question (new thread or keywords suggest new topic), search knowledge
- [ ] Simple heuristic first (message length, question marks, keywords)
- [ ] LLM can be used to classify intent later (but start simple)

---

### Milestone 6: Error Handling, Resilience & Polish

**Goal:** Production-ready error handling, rate limiting, graceful degradation.

#### Ticket 6.1 — Retry & circuit breaker patterns
**What:** Handle transient failures gracefully.

**Acceptance criteria:**
- [ ] Retry with exponential backoff for all external API calls
- [ ] Circuit breaker for each knowledge source (skip if repeatedly failing)
- [ ] Timeout on all external calls
- [ ] Use `tenacity` library for retry logic

**Key learnings:**
- `tenacity` — decorator-based retry (`@retry(stop=stop_after_attempt(3))`)
- Decorators that take arguments — advanced decorator pattern

---

#### Ticket 6.2 — Rate limiting for LLM calls
**What:** Don't let the bot burn through your Bedrock quota.

**Acceptance criteria:**
- [ ] Rate limit: max N LLM calls per minute per user
- [ ] Rate limit: max M LLM calls per minute globally
- [ ] Friendly message when rate limited
- [ ] Token tracking (log input/output tokens per call)

---

#### Ticket 6.3 — Health check & monitoring
**What:** Know when the bot is healthy and when it's not.

**Acceptance criteria:**
- [ ] Startup log confirms all connections are valid
- [ ] Periodic health check (can reach Slack, Bedrock, knowledge sources)
- [ ] Metrics: response time, token usage, error rate (logged, not dashboarded yet)

---

### Milestone 7: Testing & Quality (Ongoing)

**Goal:** Solid test coverage, CI-ready.

#### Ticket 7.1 — Unit tests for all components
**What:** Every module has unit tests.

**Acceptance criteria:**
- [ ] All Protocol implementations tested
- [ ] All dataclasses tested for construction and validation
- [ ] Mocked external dependencies (Slack, AWS, HTTP)
- [ ] Coverage target: 80%+

**Key learnings:**
- `pytest` fixtures — like `setUp()` but composable and reusable
- `conftest.py` — shared fixtures across test files (like a base TestCase class)
- `pytest.mark.parametrize` — data providers (like PHPUnit `@dataProvider`)
- `freezegun` — mock time (like `ClockMock` in Symfony)

---

#### Ticket 7.2 — Integration tests
**What:** Test the wiring between components.

**Acceptance criteria:**
- [ ] Test: mention event → knowledge search → LLM call → Slack reply
- [ ] Use fakes/stubs, not mocks (test behavior, not implementation)
- [ ] Test error paths: LLM down, knowledge source timeout, invalid message

---

#### Ticket 7.3 — CI pipeline
**What:** Automated quality checks.

**Acceptance criteria:**
- [ ] GitHub Actions workflow
- [ ] Steps: `ruff check`, `ruff format --check`, `mypy`, `pytest`
- [ ] Runs on every push and PR

---

### Future Milestones (Not Planned in Detail)

#### Milestone 8: Async/Await Migration
- Migrate from sync to async for better concurrency
- `asyncio`, `async def`, `await` — Python's async model
- `httpx.AsyncClient` instead of `httpx.Client`
- Slack bolt async adapter

#### Milestone 9: Persistent Storage
- Store conversation history in a database (SQLite → PostgreSQL)
- `SQLAlchemy` or `sqlmodel` for ORM
- Alembic for migrations (like Doctrine migrations)

#### Milestone 10: RAG (Retrieval Augmented Generation)
- Vector embeddings for knowledge sources
- Vector database (Pinecone, pgvector, ChromaDB)
- Semantic search instead of keyword search
- This is where the project starts touching ML concepts

#### Milestone 11: Observability
- OpenTelemetry for tracing
- Structured logging to a centralized system
- Dashboards for token usage, response quality

---

## Recommended Learning Order

1. **Start here:** Python project structure, `pyproject.toml`, virtual envs (Milestone 0)
2. **Then:** Decorators, type hints, dataclasses (Milestone 1-2)
3. **Then:** Protocols, dependency injection patterns (Milestone 2)
4. **Then:** HTTP clients, API integration, error handling (Milestone 3-4)
5. **Then:** Concurrency with `ThreadPoolExecutor` (Milestone 4)
6. **Then:** Advanced patterns — retry, circuit breaker, rate limiting (Milestone 6)
7. **Then:** Testing ecosystem — pytest fixtures, parametrize, mocking (Milestone 7)
8. **Later:** Async/await, databases, vector search (Milestone 8-10)

---

## Resources

### Python for PHP Devs
- [Python for PHP Developers](https://docs.python.org/3/tutorial/) — official tutorial, skim what you know
- [Real Python](https://realpython.com/) — high quality tutorials
- [Python Type Hints Cheat Sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)

### Libraries You'll Use
- [`slack-bolt`](https://slack.dev/bolt-python/) — Slack bot framework
- [`pydantic`](https://docs.pydantic.dev/) — data validation (used everywhere in ML too)
- [`httpx`](https://www.python-httpx.org/) — HTTP client
- [`boto3`](https://boto3.amazonaws.com/v1/documentation/api/latest/) — AWS SDK
- [`pytest`](https://docs.pytest.org/) — testing
- [`ruff`](https://docs.astral.sh/ruff/) — linting + formatting
- [`mypy`](https://mypy.readthedocs.io/) — static type checking
- [`structlog`](https://www.structlog.org/) — structured logging
- [`tenacity`](https://tenacity.readthedocs.io/) — retry logic

### For Your ML/DL Journey
- `pydantic` and `dataclasses` are used heavily in ML pipelines
- `pytest` is the standard for ML testing too
- Type hints + mypy habits will pay off with `numpy`, `torch`, `tensorflow`
- Understanding `ThreadPoolExecutor` leads naturally to data loading patterns

---

## Working Agreement

- **You write all the code** — I guide, review, explain concepts, and help debug
- **Ask me anything** — no question is too basic, especially about Pythonic patterns
- **Show me your code** — I'll review it like a senior Python dev would
- **I'll point out PHP habits** — things that work in PHP but aren't idiomatic Python
- **Test-first encouraged** — write the test, see it fail, make it pass (you know TDD)
- **One ticket at a time** — finish, commit, move on
