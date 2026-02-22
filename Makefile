.PHONY: help install run test lint format fix typecheck check clean clean-learned index index-confluence index-github index-jira index-local

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (editable mode with dev deps)
	uv sync --dev

run: ## Run the bot
	set -a && source .env && set +a && uv run python -m bulldogent

test: ## Run pytest with coverage
	uv run pytest

lint: ## Run ruff linter
	uv run ruff check src/ tests/

format: ## Run ruff formatter
	uv run ruff format src/ tests/

fix: ## Auto-fix linting issues and format code
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

typecheck: ## Run mypy type checker
	uv run mypy src/

check: lint typecheck test ## Run all quality checks (lint + typecheck + test)

index: ## Build baseline knowledge database from all sources
	set -a && source .env && set +a && uv run python -m bulldogent.baseline index

index-confluence: ## Index only Confluence pages
	set -a && source .env && set +a && uv run python -m bulldogent.baseline index --source confluence

index-github: ## Index only GitHub repositories
	set -a && source .env && set +a && uv run python -m bulldogent.baseline index --source github

index-jira: ## Index only Jira issues
	set -a && source .env && set +a && uv run python -m bulldogent.baseline index --source jira

index-local: ## Index only local markdown/text files
	set -a && source .env && set +a && uv run python -m bulldogent.baseline index --source local

clean-learned: ## Remove learned knowledge database (keeps .gitkeep)
	find data/learned -mindepth 1 ! -name '.gitkeep' -delete 2>/dev/null || true

clean: ## Remove Python cache files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
