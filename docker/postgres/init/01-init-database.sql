-- Initialize scraper database for PostgreSQL 17.6
-- This script runs automatically when the container starts for the first time

-- Ensure UTF8 encoding for proper text handling
ALTER DATABASE scraper_db SET client_encoding TO 'utf8';

-- Create extensions for enhanced functionality
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";    -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- Text similarity for search
CREATE EXTENSION IF NOT EXISTS "btree_gin";    -- GIN indexes for better performance

-- Set optimal configurations for scraping workload
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET pg_stat_statements.track = 'all';
ALTER SYSTEM SET track_activities = on;
ALTER SYSTEM SET track_counts = on;
ALTER SYSTEM SET track_io_timing = on;

-- Optimize for OLTP workload (Online Transaction Processing)
ALTER SYSTEM SET random_page_cost = 1.1;  -- Optimized for SSD storage
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET autovacuum_vacuum_scale_factor = 0.1;
ALTER SYSTEM SET autovacuum_analyze_scale_factor = 0.05;

-- Connection and memory settings will be handled by docker compose command args

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE scraper_db TO scraper_user;
GRANT ALL ON SCHEMA public TO scraper_user;

-- Create a monitoring user for observability (optional)
-- CREATE USER scraper_monitor WITH PASSWORD 'monitor_password';
-- GRANT CONNECT ON DATABASE scraper_db TO scraper_monitor;
-- GRANT USAGE ON SCHEMA public TO scraper_monitor;

\echo 'PostgreSQL 17.6 database initialized successfully for CSF Race scraper'