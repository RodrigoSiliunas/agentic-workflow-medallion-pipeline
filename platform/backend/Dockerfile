FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Preserva layout repo pra `[tool.uv.sources] observer = { path =
# "../../observer-framework" }` resolver igual em host + container.
WORKDIR /app/platform/backend

# observer-framework copiado antes do uv sync (editable dep)
COPY observer-framework/ /app/observer-framework/

# Deps (cache layer). Paths relativos ao build context (repo root).
COPY platform/backend/pyproject.toml platform/backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Codigo + alembic + entrypoint + scripts (ops/diag)
COPY platform/backend/app/ app/
COPY platform/backend/alembic.ini ./
COPY platform/backend/entrypoint.sh ./
COPY platform/backend/scripts/ scripts/

# Sample parquet (~8.7MB) usado pelo s3.py:_upload_sample_data — saga
# bronze depende dele pra popular S3. Sem isso, bronze_ingestion falha
# com UNABLE_TO_INFER_SCHEMA (bucket vazio).
COPY pipelines/pipeline-seguradora-whatsapp/data/ /app/pipelines/pipeline-seguradora-whatsapp/data/

# observer_config.yaml usado por scripts/vps_upload_workspace_file.py
# pra hotpatch do config no workspace Databricks sem redeploy completo
# da saga. Tambem util pra scripts de diag lerem defaults do pipeline.
COPY pipelines/pipeline-seguradora-whatsapp/observer_config.yaml /app/pipelines/pipeline-seguradora-whatsapp/observer_config.yaml
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
