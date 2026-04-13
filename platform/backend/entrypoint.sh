#!/bin/sh
set -e

echo "Running migrations..."
uv run alembic upgrade head 2>&1 || echo "WARN: migrations failed (may already be up to date)"

echo "Starting server..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
