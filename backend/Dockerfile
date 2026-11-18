FROM python:3.11-slim AS builder

WORKDIR /app

# Install C/C++ build toolchain only in builder stage (never shipped in runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv binary from official pinned image (prevents unpinned tool warnings)
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

# Enable bytecode compilation and copy-based linking for faster, deterministic builds
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency specifications and lockfile
COPY pyproject.toml uv.lock ./

# Install strictly locked dependencies (resolves docker:S8544; --no-build is omitted because srt==3.5.3 is sdist-only, uv.lock guarantees integrity via sha256 hashes)
RUN uv sync --frozen --no-install-project --no-dev --no-cache


FROM python:3.11-slim AS runtime

WORKDIR /app

# Install minimal runtime OS libraries only and configure unprivileged user (UID 1000)
# Directory ownership is set before copying .venv so chown never duplicates .venv layers
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /bin/bash atenea \
    && mkdir -p /app/data /app/obsidian_vault /app/voices /app/models \
    && chown -R atenea:atenea /app

# Copy pre-built virtualenv directly with target ownership (avoids OverlayFS layer duplication)
COPY --from=builder --chown=atenea:atenea /app/.venv /app/.venv

# Copy application source directly with unprivileged ownership (no build manifests needed in runtime)
COPY --chown=atenea:atenea src/ /app/src/

# Switch to non-root user
USER atenea

# Environment defaults (include uv virtualenv on PATH and externalized Vosk model path)
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV VOSK_MODEL_PATH=/app/models/vosk-model-small-es-0.42

EXPOSE 8000

CMD ["uvicorn", "src.presentation.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
