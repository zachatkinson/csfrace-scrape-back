#!/bin/bash
# Development startup script for CSFrace backend
# This script runs database migrations and starts the development server

set -e  # Exit on error

echo "🔧 CSFrace Backend - Development Startup"
echo "========================================"

# Wait for database to be ready
echo "📊 Waiting for database to be ready..."
until uv run python -c "
import os
from sqlalchemy import create_engine, text
database_url = os.environ.get('DATABASE_URL')
# Convert to psycopg3 URL format if needed
if database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://')
print(f'Testing connection to: {database_url.split(\"@\")[0]}@***')
try:
    engine = create_engine(database_url)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    print('✅ Database connection successful!')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    raise
" 2>/dev/null; do
    echo "⏳ Database not ready yet, waiting..."
    sleep 2
done

echo "✅ Database is ready!"

# Run database migrations
echo "🔄 Running database migrations..."
# TEMPORARY: Skip Alembic due to Config object logger attribute error
# Using SchemaManager in application startup as fallback
echo "⚠️  Temporarily skipping Alembic migrations (using SchemaManager fallback)"
echo "✅ Database migrations will be handled by SchemaManager during app startup"

# uv run alembic upgrade head
#
# if [ $? -eq 0 ]; then
#     echo "✅ Database migrations completed successfully"
# else
#     echo "❌ Database migrations failed"
#     exit 1
# fi

# Start the development server
echo "🚀 Starting development server..."
exec uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload