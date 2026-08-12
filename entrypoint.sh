#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

if [ $# -eq 0 ]; then
    echo "Starting Uvicorn..."
    exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
else
    echo "Executing command: $@"
    exec "$@"
fi

