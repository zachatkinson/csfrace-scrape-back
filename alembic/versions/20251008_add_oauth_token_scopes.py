"""add oauth token scopes field

Revision ID: 20251008_add_oauth_token_scopes
Revises: (set by orchestrator)
Create Date: 2025-10-08

This migration adds the token_scopes field to linked_accounts table
for tracking OAuth scope grants for proper token revocation.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251008_add_oauth_token_scopes"
down_revision = None  # Will be set by orchestrator based on latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add token_scopes column to linked_accounts table.

    Adds a nullable Text column to store comma-separated OAuth scopes
    granted by the user for proper revocation tracking.
    """
    op.add_column(
        "linked_accounts",
        sa.Column(
            "token_scopes",
            sa.Text(),
            nullable=True,
            comment="Comma-separated OAuth scopes for revocation tracking",
        ),
    )


def downgrade() -> None:
    """Remove token_scopes column from linked_accounts table."""
    op.drop_column("linked_accounts", "token_scopes")
