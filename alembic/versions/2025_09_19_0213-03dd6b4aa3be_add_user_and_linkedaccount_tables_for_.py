"""Add User and LinkedAccount tables for OAuth SSO

Revision ID: 03dd6b4aa3be
Revises: 7d414c5072e9
Create Date: 2025-09-19 02:13:27.113455

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "03dd6b4aa3be"
down_revision: Union[str, Sequence[str], None] = "7d414c5072e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    
    # Create linked_accounts table
    op.create_table(
        "linked_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_account_id", sa.String(255), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_linked_accounts_user_id", "linked_accounts", ["user_id"])
    op.create_unique_constraint("uq_linked_accounts_provider_account", "linked_accounts", ["provider", "provider_account_id"])
    
    # Add user_id foreign key to jobs table
    op.add_column("jobs", sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True))
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove user_id from jobs table
    op.drop_index("ix_jobs_user_id", "jobs")
    op.drop_column("jobs", "user_id")
    
    # Drop linked_accounts table
    op.drop_constraint("uq_linked_accounts_provider_account", "linked_accounts")
    op.drop_index("ix_linked_accounts_user_id", "linked_accounts")
    op.drop_table("linked_accounts")
    
    # Drop users table
    op.drop_index("ix_users_email", "users")
    op.drop_index("ix_users_username", "users")
    op.drop_table("users")
