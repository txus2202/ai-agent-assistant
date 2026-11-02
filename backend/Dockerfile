FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and configure unprivileged system user (UID 1000)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /bin/bash atenea \
    && mkdir -p /app/data /app/obsidian_vault /app/voices \
    && chown -R atenea:atenea /app

# Install uv binary from official pinned image (prevents unpinned tool warnings)
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

# Enable bytecode compilation and copy-based linking for faster, deterministic builds
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency specifications and lockfile
COPY pyproject.toml uv.lock ./

# Install strictly locked dependencies (resolves docker:S8544 and guarantees reproducible builds, prevents setup script execution)
RUN uv sync --frozen --no-install-project --no-dev --no-build

# Copy application files with unprivileged ownership
COPY --chown=atenea:atenea src/ /app/src/
COPY --chown=atenea:atenea pyproject.toml uv.lock requirements.txt /app/

# Ensure virtual environment and application directories are owned by atenea
RUN chown -R atenea:atenea /app

# Switch to non-root user
USER atenea

# Environment defaults (include uv virtualenv on PATH)
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "src.presentation.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
