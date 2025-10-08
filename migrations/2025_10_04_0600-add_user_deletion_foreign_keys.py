"""Add foreign key constraints for robust user deletion (GDPR compliance).

Revision ID: add_user_deletion_fks
Revises: add_domain_field
Create Date: 2025-10-04 06:00:00.000000

This migration ensures complete user data deletion following GDPR "right to be forgotten":

1. Adds foreign key constraint: account_lockouts.user_id → users.id ON DELETE CASCADE
2. Adds foreign key constraint: revoked_tokens.user_id → users.id ON DELETE CASCADE
3. Cleans up existing orphaned records
4. Updates existing foreign key constraints to use CASCADE

This implements best practices by:
- Database-level referential integrity (single source of truth - DRY)
- Automatic cascade deletion (prevents orphaned records)
- GDPR compliance (complete user data removal)
- Consistent with SQLAlchemy ORM relationships
"""

import logging

from sqlalchemy import text

from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers
revision = "add_user_deletion_fks"
down_revision = "add_domain_field"
branch_labels = None
depends_on = None


def upgrade():
    """Add foreign key constraints for complete user deletion."""

    connection = op.get_bind()

    # Step 1: Clean up orphaned account_lockouts records
    logger.info("Cleaning up orphaned account_lockouts records...")
    result = connection.execute(
        text("""
            DELETE FROM account_lockouts
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
    )
    orphaned_lockouts = result.rowcount
    if orphaned_lockouts > 0:
        logger.info(f"Removed {orphaned_lockouts} orphaned account_lockouts records")

    # Step 2: Clean up orphaned revoked_tokens records
    logger.info("Cleaning up orphaned revoked_tokens records...")
    result = connection.execute(
        text("""
            DELETE FROM revoked_tokens
            WHERE user_id IS NOT NULL
              AND user_id NOT IN (SELECT id FROM users)
        """)
    )
    orphaned_tokens = result.rowcount
    if orphaned_tokens > 0:
        logger.info(f"Removed {orphaned_tokens} orphaned revoked_tokens records")

    # Step 3: Add foreign key constraint to account_lockouts
    logger.info("Adding foreign key constraint to account_lockouts...")
    op.create_foreign_key(
        "fk_account_lockouts_user_id",
        "account_lockouts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",  # DRY: Database enforces deletion
    )

    # Step 4: Add foreign key constraint to revoked_tokens
    logger.info("Adding foreign key constraint to revoked_tokens...")
    op.create_foreign_key(
        "fk_revoked_tokens_user_id",
        "revoked_tokens",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",  # DRY: Database enforces deletion
    )

    # Step 5: Update existing foreign keys to use CASCADE (for consistency)
    logger.info("Updating existing foreign key constraints to use CASCADE...")

    # Drop old constraints
    op.drop_constraint("linked_accounts_user_id_fkey", "linked_accounts", type_="foreignkey")
    op.drop_constraint("user_settings_user_id_fkey", "user_settings", type_="foreignkey")
    op.drop_constraint(
        "webauthn_credentials_user_id_fkey", "webauthn_credentials", type_="foreignkey"
    )

    # Recreate with CASCADE (DRY: consistent deletion behavior)
    op.create_foreign_key(
        "fk_linked_accounts_user_id",
        "linked_accounts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "fk_user_settings_user_id",
        "user_settings",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "fk_webauthn_credentials_user_id",
        "webauthn_credentials",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    logger.info("User deletion foreign key constraints migration completed successfully")


def downgrade():
    """Remove foreign key constraints (restore original state)."""

    logger.info("Rolling back user deletion foreign key constraints...")

    # Remove new foreign key constraints
    op.drop_constraint("fk_account_lockouts_user_id", "account_lockouts", type_="foreignkey")
    op.drop_constraint("fk_revoked_tokens_user_id", "revoked_tokens", type_="foreignkey")

    # Restore original foreign key constraints (without CASCADE)
    op.drop_constraint("fk_linked_accounts_user_id", "linked_accounts", type_="foreignkey")
    op.drop_constraint("fk_user_settings_user_id", "user_settings", type_="foreignkey")
    op.drop_constraint(
        "fk_webauthn_credentials_user_id", "webauthn_credentials", type_="foreignkey"
    )

    # Recreate original constraints
    op.create_foreign_key(
        "linked_accounts_user_id_fkey",
        "linked_accounts",
        "users",
        ["user_id"],
        ["id"],
    )

    op.create_foreign_key(
        "user_settings_user_id_fkey",
        "user_settings",
        "users",
        ["user_id"],
        ["id"],
    )

    op.create_foreign_key(
        "webauthn_credentials_user_id_fkey",
        "webauthn_credentials",
        "users",
        ["user_id"],
        ["id"],
    )

    logger.info("User deletion foreign key constraints rolled back successfully")
