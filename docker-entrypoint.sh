#!/bin/bash
# Docker entrypoint script - Run migrations before starting the app
# This ensures the database schema is always up-to-date on container start

set -e  # Exit immediately if a command exits with a non-zero status

echo "=== CSFrace Backend Startup ==="
echo "Environment: ${ENVIRONMENT:-production}"
echo "Running database migrations..."

# Run Alembic migrations
python -m alembic upgrade head

echo "Migrations complete!"
echo "Starting application..."

# Execute the main command (uvicorn)
exec "$@"
