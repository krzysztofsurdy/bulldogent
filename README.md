# SlackBot

AI-powered Slack bot using LLM providers (Claude via AWS Bedrock) with knowledge from Confluence, Jira, GitHub, and Slack
history.

## Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install package in editable mode with dev dependencies
pip install -e ".[dev]"
```
## Development

```bash
# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/

# Test
pytest
```

## Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Agentic LLM with tool calling design
- **[PROJECT_PLAN.md](./PROJECT_PLAN.md)** — Milestones, tickets, roadmap
- **[PROJECT_PROGRESS.md](./PROJECT_PROGRESS.md)** — Current status and changelog
- **[LEARNING_PROGRESS.md](./LEARNING_PROGRESS.md)** — Learning notes and skills assessment