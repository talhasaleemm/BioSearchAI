#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

if [ "$RUN_AS_WORKER" = "true" ]; then
    echo "Starting Celery worker..."
    exec celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
elif [ $# -eq 0 ]; then
    echo "Starting Uvicorn..."
    exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
else
    echo "Executing command: $@"
    exec "$@"
fi

