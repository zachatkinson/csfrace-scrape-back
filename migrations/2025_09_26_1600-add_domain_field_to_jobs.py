"""Add domain field to jobs table for efficient analytics and querying.

Revision ID: add_domain_field
Revises: f21b6337b3fe
Create Date: 2025-09-26 16:00:00.000000

This migration:
1. Adds domain column to jobs table
2. Populates existing records with extracted domains
3. Adds database index for performance
4. Ensures data integrity with proper constraints

This follows best practices by:
- Using proper domain extraction from source_url
- Adding database constraints and indexing
- Handling existing data gracefully
- Following RFC 2181 domain length limits
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

# revision identifiers
revision = 'add_domain_field'
down_revision = 'f21b6337b3fe'  # Last migration from user settings table
branch_labels = None
depends_on = None


def extract_domain_from_url(url: str) -> str:
    """Extract domain from URL for migration purposes.

    Args:
        url: The URL to extract domain from

    Returns:
        The domain name or 'unknown' if extraction fails
    """
    try:
        if not url or not isinstance(url, str):
            return 'unknown'

        # Normalize URL - add https if no scheme
        if not url.startswith(('http://', 'https://', 'ftp://')):
            url = f"https://{url}"

        parsed = urlparse(url)
        if not parsed.netloc:
            return 'unknown'

        domain = parsed.netloc.lower()

        # Remove userinfo if present
        if '@' in domain:
            domain = domain.split('@')[-1]

        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]

        # Remove www. prefix for normalization
        if domain.startswith('www.'):
            domain = domain[4:]

        return domain if domain else 'unknown'

    except Exception as e:
        logger.warning(f"Failed to extract domain from '{url}': {e}")
        return 'unknown'


def upgrade():
    """Add domain field and populate existing data."""

    # Step 1: Add domain column as nullable initially
    op.add_column('jobs', sa.Column(
        'domain',
        sa.String(253),  # RFC 2181 compliant max domain length
        nullable=True,
        comment='Extracted domain from source_url for efficient statistics and filtering'
    ))

    # Step 2: Get database connection for data population
    connection = op.get_bind()

    # Step 3: Populate domain field for existing records
    logger.info("Populating domain field for existing jobs...")

    # First, try using database functions for better performance
    try:
        # Use database-specific domain extraction for better performance
        # This works for PostgreSQL, MySQL, and SQLite with different approaches

        # For PostgreSQL/MySQL - use sophisticated string functions
        result = connection.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'jobs' AND table_schema = DATABASE()
        """))

        if result.scalar() > 0:
            # Use portable SQL that works across database types
            connection.execute(text("""
                UPDATE jobs
                SET domain = CASE
                    WHEN source_url LIKE 'https://www.%' THEN
                        LOWER(SUBSTR(source_url, 13,
                            CASE WHEN INSTR(SUBSTR(source_url, 13), '/') > 0
                                 THEN INSTR(SUBSTR(source_url, 13), '/') - 1
                                 ELSE LENGTH(SUBSTR(source_url, 13))
                            END))
                    WHEN source_url LIKE 'https://%' THEN
                        LOWER(SUBSTR(source_url, 9,
                            CASE WHEN INSTR(SUBSTR(source_url, 9), '/') > 0
                                 THEN INSTR(SUBSTR(source_url, 9), '/') - 1
                                 ELSE LENGTH(SUBSTR(source_url, 9))
                            END))
                    WHEN source_url LIKE 'http://www.%' THEN
                        LOWER(SUBSTR(source_url, 12,
                            CASE WHEN INSTR(SUBSTR(source_url, 12), '/') > 0
                                 THEN INSTR(SUBSTR(source_url, 12), '/') - 1
                                 ELSE LENGTH(SUBSTR(source_url, 12))
                            END))
                    WHEN source_url LIKE 'http://%' THEN
                        LOWER(SUBSTR(source_url, 8,
                            CASE WHEN INSTR(SUBSTR(source_url, 8), '/') > 0
                                 THEN INSTR(SUBSTR(source_url, 8), '/') - 1
                                 ELSE LENGTH(SUBSTR(source_url, 8))
                            END))
                    ELSE 'unknown'
                END
                WHERE domain IS NULL
            """))

            # Clean up any empty domains or domains with ports/userinfo
            connection.execute(text("""
                UPDATE jobs
                SET domain = 'unknown'
                WHERE domain IS NULL OR domain = '' OR LENGTH(domain) > 253
            """))

    except Exception as e:
        logger.warning(f"Database-specific domain extraction failed: {e}")
        logger.info("Falling back to Python-based domain extraction...")

        # Fallback: Use Python extraction for more complex cases
        try:
            # Fetch all jobs that need domain extraction
            result = connection.execute(text("SELECT id, source_url FROM jobs WHERE domain IS NULL"))
            jobs = result.fetchall()

            logger.info(f"Processing {len(jobs)} jobs for domain extraction...")

            # Process in batches for better performance
            batch_size = 1000
            for i in range(0, len(jobs), batch_size):
                batch = jobs[i:i + batch_size]

                # Prepare batch update
                updates = []
                for job_id, source_url in batch:
                    domain = extract_domain_from_url(source_url)
                    updates.append({'job_id': job_id, 'domain': domain})

                # Execute batch update
                if updates:
                    connection.execute(
                        text("UPDATE jobs SET domain = :domain WHERE id = :job_id"),
                        updates
                    )

                logger.info(f"Processed batch {i//batch_size + 1}/{(len(jobs)-1)//batch_size + 1}")

        except Exception as fallback_error:
            logger.error(f"Python fallback also failed: {fallback_error}")
            # Set all remaining NULL domains to 'unknown' as last resort
            connection.execute(text("UPDATE jobs SET domain = 'unknown' WHERE domain IS NULL"))

    # Step 4: Make domain column non-nullable after population
    op.alter_column('jobs', 'domain', nullable=False)

    # Step 5: Add database index for query performance
    op.create_index('ix_jobs_domain', 'jobs', ['domain'])

    # Step 6: Add composite index for common query patterns
    op.create_index('ix_jobs_domain_status', 'jobs', ['domain', 'status'])
    op.create_index('ix_jobs_domain_created_at', 'jobs', ['domain', 'created_at'])

    logger.info("Domain field migration completed successfully")


def downgrade():
    """Remove domain field and associated indexes."""

    # Remove indexes first
    op.drop_index('ix_jobs_domain_created_at', table_name='jobs')
    op.drop_index('ix_jobs_domain_status', table_name='jobs')
    op.drop_index('ix_jobs_domain', table_name='jobs')

    # Remove domain column
    op.drop_column('jobs', 'domain')

    logger.info("Domain field migration rolled back successfully")