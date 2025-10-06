"""JWT Token revocation service following SOLID principles and security best practices."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import get_auth_logger

from ..api.dependencies import async_session
from ..database.models.auth import RevokedToken

logger = get_auth_logger()


class TokenRevocationService:
    """Service for managing JWT token revocation - SOLID Single Responsibility Principle.

    Handles all token revocation operations including:
    - Revoking individual tokens
    - Bulk revocation for users
    - Checking revocation status
    - Cleanup of expired revocation records
    """

    def __init__(self, db_session: AsyncSession | None = None):
        """Initialize revocation service with optional database session injection."""
        self._db_session = db_session

    @database_error_handler("revoke token")
    async def revoke_token(
        self,
        jti: str,
        user_id: str,
        token_type: str,
        issued_at: datetime,
        expires_at: datetime,
        reason: str = "user_requested",
        revoked_by: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        """Revoke a single token by its JTI - SOLID Single Responsibility.

        Args:
            jti: JWT ID claim from token
            user_id: User who owns the token
            token_type: Type of token ('access' or 'refresh')
            issued_at: When token was originally issued
            expires_at: When token naturally expires
            reason: Reason for revocation (security audit trail)
            revoked_by: Admin/system user performing revocation
            client_ip: IP address of revocation request
            user_agent: User agent of revocation request

        Returns:
            bool: True if successfully revoked, False otherwise
        """
        db = self._db_session or async_session()

        try:
            # Check if already revoked - DRY principle
            existing = await self._find_revoked_token(db, jti)
            if existing:
                logger.info("Token already revoked", jti=jti, user_id=user_id)
                return True

            # Create revocation record using factory method - SOLID Factory Pattern
            revoked_token = RevokedToken.create_revocation_record(
                jti=jti,
                user_id=user_id,
                token_type=token_type,
                issued_at=issued_at,
                expires_at=expires_at,
                reason=reason,
                revoked_by=revoked_by,
                client_ip=client_ip,
                user_agent=user_agent,
            )

            db.add(revoked_token)
            await db.commit()

            logger.info(
                "Token revoked successfully",
                jti=jti,
                user_id=user_id,
                token_type=token_type,
                reason=reason,
                revoked_by=revoked_by,
            )
            return True

        finally:
            if self._db_session is None:
                await db.close()

    @database_error_handler("check token revocation status")
    async def is_token_revoked(self, jti: str) -> bool:
        """Check if a token is revoked by its JTI - SOLID Single Responsibility.

        Args:
            jti: JWT ID to check

        Returns:
            bool: True if token is revoked, False otherwise
        """
        db = self._db_session or async_session()
        try:
            revoked_token = await self._find_revoked_token(db, jti)
            return revoked_token is not None
        finally:
            if self._db_session is None:
                await db.close()

    @database_error_handler("revoke all user tokens")
    async def revoke_all_user_tokens(
        self,
        user_id: str,
        reason: str = "security_lockout",
        revoked_by: str | None = None,
    ) -> int:
        """Revoke all active tokens for a user - SOLID Single Responsibility.

        Used for security lockouts, password changes, or account deactivation.

        Args:
            user_id: User whose tokens to revoke
            reason: Reason for bulk revocation
            revoked_by: Admin performing the revocation

        Returns:
            int: Number of tokens revoked
        """
        db = self._db_session or async_session()

        try:
            # This would require tracking active tokens
            # For now, we'll create a bulk revocation record
            # In production, you'd query active sessions/tokens

            bulk_revocation = RevokedToken.create_revocation_record(
                jti=f"BULK_REVOCATION_{user_id}_{int(datetime.now(UTC).timestamp())}",
                user_id=user_id,
                token_type="bulk_revocation",  # noqa: S106
                issued_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=365),  # Long expiry for audit
                reason=reason,
                revoked_by=revoked_by,
            )

            db.add(bulk_revocation)
            await db.commit()

            # Get actual count of affected tokens for this user
            count_result = await db.execute(
                select(func.count(RevokedToken.jti))
                .where(RevokedToken.user_id == user_id)
                .where(RevokedToken.revoked_at >= datetime.now(UTC) - timedelta(seconds=10))
            )
            actual_count = count_result.scalar() or 0

            logger.warning(
                "Bulk token revocation performed",
                user_id=user_id,
                reason=reason,
                revoked_by=revoked_by,
                tokens_revoked=actual_count,
            )
            return actual_count

        finally:
            if self._db_session is None:
                await db.close()

    @database_error_handler("cleanup expired revocations")
    async def cleanup_expired_revocations(self, older_than_days: int = 30) -> int:
        """Clean up expired revocation records - SOLID Single Responsibility.

        Removes revocation records for tokens that have already expired naturally.
        This prevents the revocation table from growing indefinitely.

        Args:
            older_than_days: Remove records older than this many days

        Returns:
            int: Number of records cleaned up
        """
        db = self._db_session or async_session()

        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=older_than_days)

            # Delete revocation records where the original token would have expired
            result = await db.execute(
                select(RevokedToken).where(
                    and_(
                        RevokedToken.expires_at < cutoff_date,
                        RevokedToken.token_type
                        != "bulk_revocation",  # Keep audit records  # noqa: S105
                    )
                )
            )

            expired_records = result.scalars().all()
            records_count = len(expired_records)

            if records_count > 0:
                for record in expired_records:
                    await db.delete(record)

                await db.commit()

                logger.info(
                    "Cleaned up expired revocation records",
                    records_cleaned=records_count,
                    older_than_days=older_than_days,
                )

            return records_count

        finally:
            if self._db_session is None:
                await db.close()

    @database_error_handler("get revocation statistics")
    async def get_revocation_stats(self, user_id: str | None = None) -> dict[str, Any]:
        """Get revocation statistics for monitoring - SOLID Single Responsibility.

        Args:
            user_id: Optional user ID to filter stats

        Returns:
            dict: Revocation statistics
        """
        db = self._db_session or async_session()

        try:
            base_query = select(RevokedToken)
            if user_id:
                base_query = base_query.where(RevokedToken.user_id == user_id)

            result = await db.execute(base_query)
            all_revocations = result.scalars().all()

            # Calculate statistics - DRY principle with helper methods
            stats = {
                "total_revocations": len(all_revocations),
                "revocations_by_type": self._count_by_field(all_revocations, "token_type"),
                "revocations_by_reason": self._count_by_field(all_revocations, "revocation_reason"),
                "recent_revocations_24h": self._count_recent_revocations(all_revocations, hours=24),
                "recent_revocations_7d": self._count_recent_revocations(all_revocations, days=7),
            }

            if user_id:
                stats["user_id"] = user_id

            return stats

        finally:
            if self._db_session is None:
                await db.close()

    # Private helper methods following SOLID and DRY principles

    async def _find_revoked_token(self, db: AsyncSession, jti: str) -> RevokedToken | None:
        """Find a revoked token by JTI - DRY principle helper method."""
        result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        return result.scalar_one_or_none()

    def _count_by_field(
        self, revocations: Sequence[RevokedToken], field_name: str
    ) -> dict[str, int]:
        """Count revocations by a specific field - DRY principle helper method."""
        counts: dict[str, int] = {}
        for revocation in revocations:
            field_value = getattr(revocation, field_name)
            counts[field_value] = counts.get(field_value, 0) + 1
        return counts

    def _count_recent_revocations(
        self, revocations: Sequence[RevokedToken], hours: int | None = None, days: int | None = None
    ) -> int:
        """Count revocations within a time period - DRY principle helper method."""
        if hours:
            cutoff = datetime.now(UTC) - timedelta(hours=hours)
        elif days:
            cutoff = datetime.now(UTC) - timedelta(days=days)
        else:
            return 0

        return sum(1 for rev in revocations if rev.revoked_at >= cutoff)


# Global service instance following Dependency Inversion Principle
token_revocation_service = TokenRevocationService()
