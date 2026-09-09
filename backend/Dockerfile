# CircuitSage backend — production image (API + worker share this image).
# Multi-stage: a builder installs the pinned dependency set into a virtualenv, then a slim
# runtime copies only that venv and the application code and runs as a non-root user.
#
# The pinned base image matches the guide's Python 3.13.14. Dependencies are installed from
# the exact-pinned requirements.lock; the Windows-only pywin32 line is filtered out because
# this image is Linux (it has no effect on the app).

FROM python:3.13.14-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# Build toolchain for any dependency without a manylinux wheel.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.lock ./requirements.lock

# Isolate dependencies in a venv so the runtime stage copies a single directory.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN grep -viE '^pywin32==' requirements.lock > /tmp/requirements.linux.txt \
    && pip install -r /tmp/requirements.linux.txt


FROM python:3.13.14-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production

# Non-root runtime user.
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv

# Entrypoint normalizes a bare postgres:// / postgresql:// DATABASE_URL (as provided by managed
# hosts such as Render) to the +psycopg dialect this app's engine expects, then execs the CMD.
# It is a no-op for an already-correct URL (e.g. the compose value), so it is safe everywhere.
RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -e' \
    'case "${DATABASE_URL:-}" in' \
    '  postgresql+*) : ;;' \
    '  postgresql://*) export DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgresql://}" ;;' \
    '  postgres://*)   export DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgres://}" ;;' \
    'esac' \
    'exec "$@"' \
    > /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /app
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini pyproject.toml ./

USER appuser
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# Overridden by the worker (python -m app.worker) and by the migrate/preDeploy command.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
