# Contributing to Bulldogent

Thanks for your interest in contributing to Bulldogent! This guide covers everything you need to get started.

## Prerequisites

- **Python 3.12+** (check with `python --version`)
- **[uv](https://docs.astral.sh/uv/)** -- fast Python package manager
- **Docker & Docker Compose** -- for running PostgreSQL locally
- **pre-commit** -- installed automatically with dev dependencies

## Getting Started

1. **Clone the repository:**

   ```bash
   git clone <repo-url> && cd bulldogent
   ```

2. **Install dependencies:**

   ```bash
   make install
   ```

   This runs `uv sync --dev`, which installs all runtime and development dependencies.

3. **Set up environment variables:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and fill in the credentials for the platforms and tools you need. Variables follow a naming convention:
   - `PLATFORM_<NAME>_*` -- messaging platform credentials
   - `PROVIDER_<NAME>_*` -- LLM provider credentials
   - `TOOL_<NAME>_*` -- tool integration credentials
   - `EMBEDDING_*` -- embedding provider credentials

   Unconfigured platforms, providers, and tools are silently skipped at startup.

4. **Start PostgreSQL (for RAG/baseline features):**

   ```bash
   docker compose up -d postgres
   ```

5. **Install pre-commit hooks:**

   ```bash
   uv run pre-commit install
   ```

6. **Run the bot:**

   ```bash
   make run
   ```

## Development Workflow

### Running Quality Checks

```bash
make check       # Run all three: lint + typecheck + test
make lint        # Ruff linter only
make typecheck   # mypy strict mode only
make test        # pytest with coverage only
make format      # Auto-format code
make fix         # Auto-fix lint issues + format
```

Run a single test:

```bash
uv run pytest tests/test_foo.py::TestClass::test_method -v
```

### Pre-commit Hooks

Every commit automatically runs:

1. **ruff check --fix** -- linting with auto-fix
2. **ruff format** -- code formatting
3. **mypy --strict** -- type checking (src/ only)
4. **pytest** -- full test suite with coverage

If a hook fails, the commit is rejected. Fix the issue and commit again.

## Code Style

### Formatting and Linting

- **Ruff** handles both linting and formatting
- Double quotes, spaces for indentation, 100-character line length
- Lint rules: `E`, `W`, `F`, `I` (isort), `N` (naming), `UP` (pyupgrade), `B` (bugbear), `S` (security), `C4` (comprehensions), `SIM` (simplification)

### Type Annotations

- **mypy strict mode** is enforced -- every function must have complete type annotations
- Third-party libraries without stubs are allowlisted in `pyproject.toml`
- Use `Union` types via `|` syntax (e.g., `str | None`) -- Python 3.12+ style

### Logging

- Use **structlog** for all logging -- never use `print()` or stdlib `logging` directly
- Import: `import structlog` then `logger = structlog.get_logger()`

### Bot Output

- Slack-flavored markdown in bot messages: `*bold*` not `**bold**`, no `#` headers

## Architecture Overview

The codebase uses **Protocol/ABC-based abstractions** with a registry+factory pattern. Each layer follows the same structure:

```
AbstractBase  ->  Adapter implementations  ->  Registry (collects)  ->  Factory (creates from config)
```

### Package Layout (`src/bulldogent/`)

| Package | Purpose |
|---|---|
| `__main__.py` | Entry point -- wires registries, registers tools, starts bots |
| `bot.py` | Agentic loop orchestrator (max 15 iterations) |
| `approval.py` | Thread-safe reaction-based approval manager |
| `messaging/platform/` | Chat platform abstraction + Slack adapter |
| `llm/provider/` | LLM provider abstraction + adapters (OpenAI, Bedrock, Vertex) |
| `llm/tool/` | Tool abstraction + YAML-driven operations + registry |
| `baseline/` | RAG subsystem (indexer, retriever, learner, chunker, crawlers) |
| `embedding/` | Embedding provider abstraction + adapters |
| `events/` | Event analytics (emitter, models, types) |
| `util/` | YAML loader (with env var interpolation), DB session, logging config |

### Configuration

All configuration is YAML + environment variables:

- **YAML files** (`config/`) define structure and reference env var *names* using `$(VAR)` syntax
- **`.env`** provides actual secret values
- Example files (`*.example`) are committed; actual config files are gitignored

## Adding a New Tool

Tools are the most common extension point. Each tool is an adapter with a co-located `operations.yaml`.

1. **Create the adapter directory:**

   ```
   src/bulldogent/llm/tool/adapters/your_tool/
       __init__.py
       your_tool.py
       operations.yaml
   ```

2. **Define operations in `operations.yaml`:**

   ```yaml
   your_tool_do_something:
     description: "Short description the LLM sees when choosing tools"
     parameters:
       query:
         type: string
         description: "What to search for"
       limit:
         type: integer
         description: "Max results"
         optional: true
   ```

   Operation names must be globally unique (prefixed with the tool name by convention).

3. **Implement the adapter:**

   ```python
   from pathlib import Path
   from bulldogent.llm.tool.tool import AbstractTool
   from bulldogent.llm.tool.types import ToolOperationResult

   class YourTool(AbstractTool):
       _operations_path = Path(__file__).parent / "operations.yaml"

       @property
       def name(self) -> str:
           return "your_tool"

       @property
       def description(self) -> str:
           return "Does something useful"

       def run(self, operation: str, **kwargs: object) -> ToolOperationResult:
           if operation == "your_tool_do_something":
               # implementation here
               return ToolOperationResult(content="result text")
           return ToolOperationResult(content=f"Unknown operation: {operation}", is_error=True)
   ```

4. **Register the tool in `__main__.py`:**

   The tool is instantiated from config values in `config/tools.yaml` and registered with the `ToolRegistry`.

5. **Add config to `config/tools.yaml`:**

   ```yaml
   your_tool:
     api_key_env: TOOL_YOUR_TOOL_API_KEY
   ```

6. **(Optional) Add approval rules in the `approvals` section of `config/platforms.yaml`:**

   ```yaml
   approvals:
     your_tool:
       your_tool_do_something:
         approval_group: tool_admins
   ```

## Adding a New Platform, LLM Provider, or Embedding Provider

Follow the same pattern:

1. Create an adapter implementing the abstract base class
2. Add a config dataclass if the adapter needs configuration
3. Register the adapter in the corresponding registry
4. Wire it up in `__main__.py` with config from the appropriate YAML file

Look at existing adapters for reference -- they are intentionally consistent.

## Testing

### Conventions

- Test files: `tests/test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`
- Coverage is measured automatically on every run (`--cov=bulldogent`)

### Running Tests

```bash
make test                              # All tests with coverage
uv run pytest tests/test_bot.py -v     # Single file
uv run pytest tests/test_bot.py::TestBot::test_method -v  # Single test
```

### Docker-based Tests

For a CI-like environment with PostgreSQL + pgvector:

```bash
make docker-test
```

### Writing Tests

- Mock external services (Slack API, Jira API, LLM providers) -- never make real API calls in tests
- Use `unittest.mock.patch` or `unittest.mock.MagicMock` for dependencies
- Keep tests focused and independent

## Commit Guidelines

- Write clear, concise commit messages that describe *why* the change was made
- Keep commits atomic -- one logical change per commit
- Pre-commit hooks must pass before committing (linting, formatting, type checking, tests)

## Useful Make Targets

| Command | Description |
|---|---|
| `make install` | Install all dependencies |
| `make run` | Start the bot |
| `make check` | Run lint + typecheck + test |
| `make fix` | Auto-fix lint issues and format |
| `make index` | Index all knowledge sources into the RAG database |
| `make index-jira` | Index only Jira |
| `make index-confluence` | Index only Confluence |
| `make index-github` | Index only GitHub |
| `make index-local` | Index only local files |
| `make docker-build` | Build Docker images |
| `make docker-up` | Start all services |
| `make docker-down` | Stop all services |
| `make docker-test` | Run tests in Docker |
| `make clean` | Remove Python cache files |

## Questions?

Open an issue in the repository if something is unclear or you run into trouble.
