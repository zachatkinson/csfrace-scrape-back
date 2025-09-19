"""add_user_id_to_jobs

Revision ID: add_user_id_jobs
Revises: 7d414c5072e9
Create Date: 2025-01-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision: str = "add_user_id_jobs"
down_revision: str | Sequence[str] | None = "7d414c5072e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add user_id column to jobs table."""
    # Add user_id column as VARCHAR(255) to match User.id type
    op.add_column("jobs", sa.Column("user_id", sa.String(length=255), nullable=True))

    # Add index for performance
    op.create_index(op.f("ix_jobs_user_id"), "jobs", ["user_id"], unique=False)


def downgrade() -> None:
    """Remove user_id column from jobs table."""
    # Drop index first
    op.drop_index(op.f("ix_jobs_user_id"), table_name="jobs")

    # Drop column
    op.drop_column("jobs", "user_id")
