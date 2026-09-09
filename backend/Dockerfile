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

WORKDIR /app
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini pyproject.toml ./

USER appuser
EXPOSE 8000

# Overridden by the worker service in compose (python -m app.worker).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
