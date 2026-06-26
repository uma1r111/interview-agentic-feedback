# =============================================================================
# Backend Dockerfile
# =============================================================================
# WHY python:3.11-slim NOT alpine:
#   psycopg2-binary ships pre-compiled wheels for Debian/slim.
#   On Alpine it needs to compile from source (needs gcc, musl-dev,
#   postgresql-dev) which makes the image bigger and slower to build.
#   slim gives us a smaller image with zero compilation headache.
#
# WHY PDM NOT uv:
#   The project uses pdm.lock (PDM format). uv cannot read PDM lockfiles.
#   Switching to uv would require re-generating the lock file.
#   PDM is already a project dependency so we keep it consistent.
# =============================================================================

# ── Stage 1: Install dependencies ────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install PDM
RUN pip install --no-cache-dir pdm

# Copy only dependency files first (Docker layer cache — only rebuilds
# when pyproject.toml or pdm.lock changes, not on every code change)
COPY pyproject.toml pdm.lock ./

# Install dependencies into a local venv inside /app/.venv
# --no-self: don't install the project itself yet (we copy source next)
# --no-editable: install as regular packages, not editable installs
RUN pdm install --no-self --no-editable

# ── Stage 2: Runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# ffmpeg: needed if Whisper transcription is added later
# libpq5: runtime PostgreSQL client library (psycopg2-binary needs it)
# Both are Debian packages available on slim — no compilation needed
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY . /app

# Activate the PDM venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
# Prevent Python from writing .pyc files into the container layer
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python output buffering (so logs appear immediately in Docker)
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Use exec form (not shell form) so signals (SIGTERM on docker stop)
# reach uvicorn directly, enabling graceful shutdown
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
