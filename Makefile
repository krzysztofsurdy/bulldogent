.PHONY: help install run test lint format fix typecheck check clean

help:
	@echo "Available targets:"
	@echo "  make install    - Install dependencies (editable mode with dev deps)"
	@echo "  make run        - Run the Slack bot"
	@echo "  make test       - Run pytest"
	@echo "  make lint       - Run ruff linter"
	@echo "  make format     - Run ruff formatter"
	@echo "  make fix        - Auto-fix linting issues and format code"
	@echo "  make typecheck  - Run mypy type checker"
	@echo "  make check      - Run all quality checks (lint + typecheck + test)"
	@echo "  make clean      - Remove Python cache files"

install:
	pip install -e ".[dev]"

run:
	set -a && source .env && set +a && python src/slackbot/__main__.py

test:
	pytest

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

fix:
	ruff check --fix src/ tests/
	ruff format src/ tests/

typecheck:
	mypy src/

check: lint typecheck test

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
