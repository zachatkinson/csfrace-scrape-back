"""create_database_enums_for_job_management

Revision ID: 6a017959a425
Revises:
Create Date: 2025-09-03 23:24:06.834735

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6a017959a425"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create PostgreSQL enum types for job management."""
    # Create JobStatus enum
    job_status_enum = sa.Enum(
        "pending",
        "running", 
        "completed",
        "failed",
        "skipped",
        "cancelled",
        "partial",
        name="jobstatus",
        create_type=True,
    )
    job_status_enum.create(op.get_bind())
    
    # Create JobPriority enum
    job_priority_enum = sa.Enum(
        "low",
        "normal",
        "high", 
        "urgent",
        name="jobpriority",
        create_type=True,
    )
    job_priority_enum.create(op.get_bind())


def downgrade() -> None:
    """Drop PostgreSQL enum types for job management."""
    # Drop enums in reverse order
    op.execute("DROP TYPE IF EXISTS jobpriority")
    op.execute("DROP TYPE IF EXISTS jobstatus")
