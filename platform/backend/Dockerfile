FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Deps primeiro (cache layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Codigo + alembic + entrypoint
COPY app/ app/
COPY alembic.ini ./
COPY entrypoint.sh ./
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# Non-root user com home directory (uv precisa de ~/.cache)
RUN addgroup --system app && adduser --system --ingroup app --home /home/app app \
    && chown -R app:app /app
USER app

ENV UV_CACHE_DIR=/home/app/.cache/uv

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["./entrypoint.sh"]
