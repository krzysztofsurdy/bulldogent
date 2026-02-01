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

## Project Status

See [PROJECT_PLAN.md](./PROJECT_PLAN.md) for roadmap and [PROJECT_PROGRESS.md](./PROJECT_PROGRESS.md) for current status.