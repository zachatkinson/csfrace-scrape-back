"""merge oauth and user_id branches

Revision ID: cdbc0216f3da
Revises: add_user_id_jobs, 03dd6b4aa3be
Create Date: 2025-09-20 00:25:04.387422

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "cdbc0216f3da"
down_revision: str | Sequence[str] | None = ("add_user_id_jobs", "03dd6b4aa3be")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
