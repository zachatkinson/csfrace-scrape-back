"""create_complete_database_schema

Revision ID: 7d414c5072e9
Revises: 6a017959a425
Create Date: 2025-09-12 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op  # type: ignore[import-untyped]

# revision identifiers, used by Alembic.
revision: str = "7d414c5072e9"
down_revision: str | Sequence[str] | None = "6a017959a425"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all database tables following PostgreSQL best practices."""

    # Create batches table first (no foreign key dependencies)
    op.create_table(
        "batches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("concurrent_limit", sa.Integer(), server_default="5", nullable=False),
        sa.Column("rate_limit_per_second", sa.Integer(), server_default="10", nullable=False),
        sa.Column("options", sa.JSON(), server_default="{}", nullable=True),
        sa.Column("total_jobs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_jobs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_jobs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("statistics", sa.JSON(), server_default="{}", nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_batches_status"), "batches", ["status"], unique=False)

    # Create jobs table with foreign key to batches
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("job_type", sa.String(), server_default="single", nullable=False),
        sa.Column("target_format", sa.String(), server_default="html", nullable=False),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="5", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_retries", sa.Integer(), server_default="3", nullable=False),
        sa.Column("options", sa.JSON(), server_default="{}", nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("download_size_bytes", sa.Integer(), nullable=True),
        sa.Column("output_size_bytes", sa.Integer(), nullable=True),
        sa.Column("batch_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_index(op.f("ix_jobs_batch_id"), "jobs", ["batch_id"], unique=False)

    # Create content_results table with foreign key to jobs
    op.create_table(
        "content_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("original_html", sa.Text(), nullable=True),
        sa.Column("converted_html", sa.Text(), nullable=True),
        sa.Column("shopify_html", sa.Text(), nullable=True),
        sa.Column("html_file_path", sa.String(length=1024), nullable=True),
        sa.Column("metadata_file_path", sa.String(length=1024), nullable=True),
        sa.Column("images_directory", sa.String(length=1024), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("published_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("og_title", sa.String(length=500), nullable=True),
        sa.Column("og_description", sa.Text(), nullable=True),
        sa.Column("og_image", sa.String(length=1024), nullable=True),
        sa.Column("twitter_card", sa.String(length=50), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("image_count", sa.Integer(), nullable=True),
        sa.Column("link_count", sa.Integer(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
        sa.Column("conversion_stats", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_results_job_id"), "content_results", ["job_id"], unique=False)

    # Create job_logs table with foreign key to jobs
    op.create_table(
        "job_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("component", sa.String(length=100), nullable=True),
        sa.Column("operation", sa.String(length=100), nullable=True),
        sa.Column("context_data", sa.JSON(), nullable=True),
        sa.Column("exception_type", sa.String(length=255), nullable=True),
        sa.Column("exception_traceback", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_logs_job_id"), "job_logs", ["job_id"], unique=False)
    op.create_index(op.f("ix_job_logs_level"), "job_logs", ["level"], unique=False)

    # Create system_metrics table
    op.create_table(
        "system_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_type", sa.String(length=100), nullable=False),
        sa.Column("metric_name", sa.String(length=255), nullable=False),
        sa.Column("numeric_value", sa.Float(), nullable=True),
        sa.Column("string_value", sa.String(length=500), nullable=True),
        sa.Column("json_value", sa.JSON(), nullable=True),
        sa.Column("component", sa.String(length=100), nullable=True),
        sa.Column("environment", sa.String(length=50), server_default="production", nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_system_metrics_timestamp"), "system_metrics", ["timestamp"], unique=False
    )
    op.create_index(
        op.f("ix_system_metrics_metric_type"), "system_metrics", ["metric_type"], unique=False
    )
    op.create_index(
        op.f("ix_system_metrics_component"), "system_metrics", ["component"], unique=False
    )

    # Create webauthn_credentials table
    op.create_table(
        "webauthn_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.String(length=1024), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("device_type", sa.String(length=100), nullable=True),
        sa.Column("attestation_object", sa.Text(), nullable=True),
        sa.Column("attestation_format", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("backup_eligible", sa.Boolean(), nullable=True),
        sa.Column("backup_state", sa.Boolean(), nullable=True),
        sa.Column("user_verified", sa.Boolean(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("registration_ip", sa.String(length=45), nullable=True),
        sa.Column("registration_user_agent", sa.Text(), nullable=True),
        sa.Column("last_used_ip", sa.String(length=45), nullable=True),
        sa.Column("last_used_user_agent", sa.Text(), nullable=True),
        sa.Column("security_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_webauthn_credentials_credential_id"),
        "webauthn_credentials",
        ["credential_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_webauthn_credentials_user_id"), "webauthn_credentials", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_webauthn_credentials_is_active"),
        "webauthn_credentials",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webauthn_credentials_last_used_at"),
        "webauthn_credentials",
        ["last_used_at"],
        unique=False,
    )

    # Create webauthn_challenges table
    op.create_table(
        "webauthn_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_key", sa.String(length=255), nullable=False),
        sa.Column("challenge", sa.String(length=1024), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("challenge_type", sa.String(length=50), nullable=False),
        sa.Column("origin", sa.String(length=255), nullable=True),
        sa.Column("rp_id", sa.String(length=255), nullable=True),
        sa.Column("user_verification", sa.String(length=50), nullable=True),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context_data", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_webauthn_challenges_challenge_key"),
        "webauthn_challenges",
        ["challenge_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_webauthn_challenges_user_id"), "webauthn_challenges", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_webauthn_challenges_challenge_type"),
        "webauthn_challenges",
        ["challenge_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webauthn_challenges_created_at"),
        "webauthn_challenges",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webauthn_challenges_expires_at"),
        "webauthn_challenges",
        ["expires_at"],
        unique=False,
    )

    # Create account_lockouts table
    op.create_table(
        "account_lockouts",
        sa.Column("id", sa.Integer(), nullable=False, comment="Unique lockout record identifier"),
        sa.Column(
            "user_id", sa.String(length=50), nullable=False, comment="User ID who is locked out"
        ),
        sa.Column(
            "username",
            sa.String(length=100),
            nullable=False,
            comment="Username for quick lookups and audit trail",
        ),
        sa.Column(
            "failed_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Current number of consecutive failed login attempts",
        ),
        sa.Column(
            "is_locked",
            sa.Boolean(),
            server_default="false",
            nullable=False,
            comment="Current lockout status",
        ),
        sa.Column(
            "lockout_reason",
            sa.String(length=100),
            nullable=True,
            comment="Reason for lockout (failed_attempts, suspicious_activity, admin_action)",
        ),
        sa.Column(
            "first_failed_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of first failed attempt in current sequence",
        ),
        sa.Column(
            "last_failed_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of most recent failed attempt",
        ),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when account was locked",
        ),
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when lockout expires (NULL for permanent)",
        ),
        sa.Column(
            "unlocked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when account was unlocked",
        ),
        sa.Column(
            "client_ip",
            sa.String(length=45),
            nullable=True,
            comment="IP address of failed login attempts",
        ),
        sa.Column(
            "user_agent", sa.Text(), nullable=True, comment="User agent of failed login attempts"
        ),
        sa.Column(
            "unlocked_by",
            sa.String(length=100),
            nullable=True,
            comment="Admin user who unlocked the account manually",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Last update timestamp",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_account_lockouts_user_id"), "account_lockouts", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_account_lockouts_username"), "account_lockouts", ["username"], unique=False
    )
    op.create_index(
        op.f("ix_account_lockouts_is_locked"), "account_lockouts", ["is_locked"], unique=False
    )
    op.create_index(
        op.f("ix_account_lockouts_locked_until"), "account_lockouts", ["locked_until"], unique=False
    )

    # Create revoked_tokens table
    op.create_table(
        "revoked_tokens",
        sa.Column(
            "jti",
            sa.String(length=100),
            nullable=False,
            comment="JWT ID claim - unique identifier for each token",
        ),
        sa.Column(
            "user_id",
            sa.String(length=50),
            nullable=True,
            comment="User who owned the token (for bulk revocation)",
        ),
        sa.Column(
            "token_type",
            sa.String(length=20),
            server_default="access",
            nullable=False,
            comment="Token type: access, refresh, or reset",
        ),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When token was originally issued",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When token naturally expires",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When token was revoked",
        ),
        sa.Column(
            "revocation_reason",
            sa.String(length=100),
            nullable=True,
            comment="Reason for revocation: logout, password_change, admin_action, etc.",
        ),
        sa.Column(
            "revoked_by",
            sa.String(length=50),
            nullable=True,
            comment="Who/what revoked the token (user_id, admin_id, or system)",
        ),
        sa.Column(
            "client_ip",
            sa.String(length=45),
            nullable=True,
            comment="IP address when token was revoked",
        ),
        sa.Column(
            "user_agent",
            sa.String(length=500),
            nullable=True,
            comment="User agent when token was revoked",
        ),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index(op.f("ix_revoked_tokens_user_id"), "revoked_tokens", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_revoked_tokens_expires_at"), "revoked_tokens", ["expires_at"], unique=False
    )


def downgrade() -> None:
    """Drop all database tables following PostgreSQL best practices."""
    # Drop in reverse order to handle foreign key constraints
    op.drop_table("revoked_tokens")
    op.drop_table("account_lockouts")
    op.drop_table("webauthn_challenges")
    op.drop_table("webauthn_credentials")
    op.drop_table("system_metrics")
    op.drop_table("job_logs")
    op.drop_table("content_results")
    op.drop_table("jobs")
    op.drop_table("batches")
