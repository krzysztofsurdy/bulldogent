# CLAUDE.md

## Project
AI-powered Slack bot — responds to @mentions, uses Claude via AWS Bedrock (behind a provider-agnostic abstraction), pulls context from Confluence, Jira, GitHub, and Slack history.

## Mentoring Mode
The developer is a senior PHP dev learning Python. **Do not write code for them.** Guide, explain, review, and debug. Always map Python concepts to PHP equivalents. Point out non-idiomatic "PHP-isms" in their code. Encourage Pythonic patterns.

## Key Documents
- **Architecture** — agentic LLM with tool calling design: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Project plan** — milestones, tickets, acceptance criteria: [PROJECT_PLAN.md](./PROJECT_PLAN.md)
- **Project progress** — what's done, in progress, blocked: [PROJECT_PROGRESS.md](./PROJECT_PROGRESS.md)
- **Learning progress** — mentor's notes, skills assessment, PHP habits to avoid: [LEARNING_PROGRESS.md](./LEARNING_PROGRESS.md)

**Keep all three updated as work progresses.** After each ticket, update PROJECT_PROGRESS.md status and add notes to LEARNING_PROGRESS.md (new concepts learned, PHP habits spotted, breakthroughs, struggles).

## Tech Stack
- Python 3.12+
- `slack-bolt` — Slack bot framework
- `boto3` — AWS Bedrock (LLM)
- `httpx` — HTTP client
- `pydantic-settings` — typed config from env vars
- `structlog` — structured logging
- `pytest` + `ruff` + `mypy` — testing, linting, type checking

## Project Structure
```
src/bulldogent/       # Main package (src layout)
tests/              # pytest tests
pyproject.toml      # Dependencies & tool config
```

## Conventions
- Type hints everywhere
- `Protocol` for abstractions (not ABC)
- `@dataclass` for DTOs / value objects
- `pytest` with fixtures, not unittest classes
- `ruff` for linting + formatting
- Sync first, async migration is a later milestone

## Commands
```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Lint & format
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/

# Test
pytest

# Run
python -m bulldogent
```
