FROM python:3.11-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

WORKDIR /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --no-dev --group api

COPY ./scripts/ /app/
COPY ./alembic.ini /app/
COPY ./prestart.sh /app/
COPY ./tests-start.sh /app/
COPY ./app /app/app

RUN mv /app/start.sh /start.sh && \
    mv /app/start-reload.sh /start-reload.sh && \
    chmod +x /start.sh && \
    chmod +x /start-reload.sh

FROM runtime AS dev

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --inexact --only-group dev

FROM runtime
