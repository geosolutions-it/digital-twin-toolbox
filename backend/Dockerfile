FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

WORKDIR /app/

ARG INSTALL_DEV=false

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    if [ "$INSTALL_DEV" = "true" ]; then \
      uv sync --frozen --no-install-workspace --group api --group dev; \
    else \
      uv sync --frozen --no-install-workspace --no-dev --group api; \
    fi

COPY ./scripts/ /app/
COPY ./alembic.ini /app/
COPY ./prestart.sh /app/
COPY ./tests-start.sh /app/
COPY ./app /app/app

RUN mv /app/start.sh /start.sh && \
    mv /app/start-reload.sh /start-reload.sh && \
    chmod +x /start.sh && \
    chmod +x /start-reload.sh
