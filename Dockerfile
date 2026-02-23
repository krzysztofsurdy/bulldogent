# Multi-stage Dockerfile for Bulldogent
# Stage 1: Builder - install dependencies with uv
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable

# Copy source and install project
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Strip unnecessary files from venv to reduce image size.
# NOTE: Do NOT delete .dist-info directories — they contain entry_points.txt
# which packages need for plugin discovery at runtime.
RUN find /app/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -name "*.pyc" -delete 2>/dev/null || true && \
    find /app/.venv -name "*.pyo" -delete 2>/dev/null || true && \
    find /app/.venv -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -name "*.so" -exec strip --strip-debug {} + 2>/dev/null || true

# Stage 2: Runtime - minimal production image
FROM python:3.13-slim

# Create non-root user for security
RUN groupadd -r bulldogent && useradd -r -g bulldogent -u 1000 bulldogent

WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source and config
COPY --chown=bulldogent:bulldogent src/ ./src/
COPY --chown=bulldogent:bulldogent config/ ./config/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

# Switch to non-root user
USER bulldogent

# Health check - verify Python process is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD pgrep -f "python -m bulldogent" || exit 1

# Run the application
CMD ["python", "-m", "bulldogent"]
