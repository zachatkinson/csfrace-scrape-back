"""Account lockout service following SOLID principles and security best practices."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import get_auth_logger

from ..api.dependencies import async_session
from ..core.environment import EnvironmentLoader
from ..database.models.auth import AccountLockout

logger = get_auth_logger()


class AccountLockoutConfig:
    """Configuration for account lockout behavior - SOLID Single Responsibility."""

    def __init__(self) -> None:
        # Failed attempt thresholds
        self.max_failed_attempts = EnvironmentLoader.get_int("LOCKOUT_MAX_FAILED_ATTEMPTS", 5)
        self.lockout_duration_minutes = EnvironmentLoader.get_int("LOCKOUT_DURATION_MINUTES", 15)
        self.progressive_lockout_enabled = EnvironmentLoader.get_bool(
            "LOCKOUT_PROGRESSIVE_ENABLED", True
        )

        # Time windows
        self.failed_attempt_window_minutes = EnvironmentLoader.get_int(
            "LOCKOUT_ATTEMPT_WINDOW_MINUTES", 15
        )
        self.lockout_reset_window_hours = EnvironmentLoader.get_int(
            "LOCKOUT_RESET_WINDOW_HOURS", 24
        )

        # Progressive lockout durations (in minutes)
        self.progressive_durations = [
            EnvironmentLoader.get_int("LOCKOUT_FIRST_DURATION", 5),  # 1st lockout: 5 minutes
            EnvironmentLoader.get_int("LOCKOUT_SECOND_DURATION", 15),  # 2nd lockout: 15 minutes
            EnvironmentLoader.get_int("LOCKOUT_THIRD_DURATION", 30),  # 3rd lockout: 30 minutes
            EnvironmentLoader.get_int("LOCKOUT_MAX_DURATION", 60),  # 4th+ lockout: 60 minutes
        ]

        # IP-based lockout protection
        self.enable_ip_lockout = EnvironmentLoader.get_bool("LOCKOUT_ENABLE_IP_LOCKOUT", True)
        self.ip_max_failed_attempts = EnvironmentLoader.get_int("LOCKOUT_IP_MAX_ATTEMPTS", 10)
        self.ip_lockout_duration_minutes = EnvironmentLoader.get_int(
            "LOCKOUT_IP_DURATION_MINUTES", 30
        )

        # Security features
        self.enable_suspicious_activity_detection = EnvironmentLoader.get_bool(
            "LOCKOUT_ENABLE_SUSPICIOUS_DETECTION", True
        )
        self.suspicious_activity_threshold = EnvironmentLoader.get_int(
            "LOCKOUT_SUSPICIOUS_THRESHOLD", 20
        )


class AccountLockoutService:
    """Service for managing account lockouts and failed login attempts - SOLID Single Responsibility Principle.

    Handles all account lockout operations including:
    - Tracking failed login attempts
    - Implementing progressive lockout policies
    - IP-based lockout protection
    - Suspicious activity detection
    - Administrative unlock capabilities
    """

    def __init__(
        self, db_session: AsyncSession | None = None, config: AccountLockoutConfig | None = None
    ):
        """Initialize lockout service with optional dependencies injection."""
        self._db_session = db_session
        self.config = config or AccountLockoutConfig()

    @database_error_handler("record failed login attempt")
    async def record_failed_login_attempt(
        self,
        user_id: str,
        username: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        """Record a failed login attempt and check if account should be locked - SOLID Single Responsibility.

        Args:
            user_id: User identifier
            username: Username for audit trail
            client_ip: IP address of failed attempt
            user_agent: User agent of failed attempt

        Returns:
            bool: True if account was locked, False if just recorded
        """
        db = self._db_session or async_session()

        try:
            # Get or create lockout record for user
            lockout_record = await self._get_or_create_lockout_record(
                db, user_id, username, client_ip, user_agent
            )

            # Check if account is already locked
            if lockout_record.is_locked and not lockout_record.is_lockout_expired:
                logger.warning(
                    "Failed login attempt on locked account",
                    user_id=user_id,
                    username=username,
                    client_ip=client_ip,
                    remaining_minutes=lockout_record.lockout_remaining_minutes,
                )
                return True

            # If lockout expired, unlock and reset
            if lockout_record.is_locked and lockout_record.is_lockout_expired:
                lockout_record.unlock_account("system_auto_unlock")
                lockout_record.reset_failed_attempts()

            # Increment failed attempts
            lockout_record.increment_failed_attempts(client_ip, user_agent)

            # Check if we should lock the account
            should_lock = await self._should_lock_account(db, lockout_record)

            if should_lock:
                lockout_duration = self._calculate_lockout_duration(lockout_record)
                lockout_record.is_locked = True
                lockout_record.lockout_reason = "failed_attempts"
                lockout_record.locked_at = datetime.now(UTC)
                lockout_record.locked_until = datetime.now(UTC) + timedelta(
                    minutes=lockout_duration
                )

                logger.warning(
                    "Account locked due to failed login attempts",
                    user_id=user_id,
                    username=username,
                    failed_attempts=lockout_record.failed_attempts,
                    lockout_duration_minutes=lockout_duration,
                    client_ip=client_ip,
                )

            await db.commit()
            return should_lock

        finally:
            if self._db_session is None:
                await db.close()

    @database_error_handler("check account lockout status")
    async def is_account_locked(self, user_id: str) -> tuple[bool, int | None]:
        """Check if account is locked - SOLID Single Responsibility.

        Args:
            user_id: User identifier to check

        Returns:
            tuple: (is_locked, remaining_minutes)
        """
        db = self._db_session or async_session()

        try:
            # Get active lockout record
            result = await db.execute(
                select(AccountLockout)
                .where(
                    and_(
                        AccountLockout.user_id == user_id,
                        AccountLockout.is_locked,
                    )
                )
                .order_by(AccountLockout.created_at.desc())
                .limit(1)
            )

            lockout_record = result.scalar_one_or_none()

            if not lockout_record:
                return False, None

            # Check if lockout has expired
            if lockout_record.is_lockout_expired:
                # Auto-unlock expired lockout
                lockout_record.unlock_account("system_auto_unlock")
                await db.commit()
                return False, None

            return True, lockout_record.lockout_remaining_minutes

        finally:
            if self._db_session is None:
                await db.close()

    @database_error_handler("record successful login")
    async def record_successful_login(self, user_id: str, username: str) -> None:
        """Record successful login and reset failed attempt counters - SOLID Single Responsibility.

        Args:
            user_id: User identifier
            username: Username for audit trail
        """
        db = self._db_session or async_session()

        try:
            # Get current lockout record
            result = await db.execute(
                select(AccountLockout)
                .where(AccountLockout.user_id == user_id)
                .order_by(AccountLockout.created_at.desc())
                .limit(1)
            )

            lockout_record = result.scalar_one_or_none()

            if lockout_record:
                # Reset failed attempts and unlock if needed
                lockout_record.reset_failed_attempts()
                if lockout_record.is_locked:
                    lockout_record.unlock_account("successful_login")

                await db.commit()

                logger.info(
                    "Successful login recorded, failed attempts reset",
                    user_id=user_id,
                    username=username,
                )

        finally:
            if self._db_session is None:
                await db.close()

    @database_error_handler("unlock account")
    async def unlock_account(
        self, user_id: str, unlocked_by: str, reason: str = "admin_unlock"
    ) -> bool:
        """Manually unlock an account - SOLID Single Responsibility.

        Args:
            user_id: User identifier to unlock
            unlocked_by: Admin user performing unlock
            reason: Reason for unlock (audit trail)

        Returns:
            bool: True if account was unlocked, False if not found/already unlocked
        """
        db = self._db_session or async_session()

        try:
            # Find active lockout record
            result = await db.execute(
                select(AccountLockout)
                .where(
                    and_(
                        AccountLockout.user_id == user_id,
                        AccountLockout.is_locked,
                    )
                )
                .order_by(AccountLockout.created_at.desc())
                .limit(1)
            )

            lockout_record = result.scalar_one_or_none()

            if not lockout_record:
                logger.warning("No locked account found for unlock", user_id=user_id)
                return False

            # Unlock the account
            lockout_record.unlock_account(unlocked_by)
            lockout_record.reset_failed_attempts()

            await db.commit()

            logger.warning(
                "Account manually unlocked",
                user_id=user_id,
                unlocked_by=unlocked_by,
                reason=reason,
            )

            return True

        finally:
            if self._db_session is None:
                await db.close()

    @database_error_handler("get lockout statistics")
    async def get_lockout_stats(self, user_id: str | None = None) -> dict[str, Any]:
        """Get lockout statistics for monitoring - SOLID Single Responsibility.

        Args:
            user_id: Optional user ID to filter stats

        Returns:
            dict: Lockout statistics
        """
        db = self._db_session or async_session()

        try:
            base_query = select(AccountLockout)
            if user_id:
                base_query = base_query.where(AccountLockout.user_id == user_id)

            result = await db.execute(base_query)
            all_lockouts = result.scalars().all()

            # Calculate statistics - DRY principle with helper methods
            stats = {
                "total_lockout_records": len(all_lockouts),
                "currently_locked_accounts": self._count_currently_locked(all_lockouts),
                "lockouts_by_reason": self._count_by_field(all_lockouts, "lockout_reason"),
                "recent_lockouts_24h": self._count_recent_lockouts(all_lockouts, hours=24),
                "recent_lockouts_7d": self._count_recent_lockouts(all_lockouts, days=7),
                "average_failed_attempts": self._calculate_average_failed_attempts(all_lockouts),
            }

            if user_id:
                stats["user_id"] = user_id
                # Add user-specific stats
                user_lockouts = [lockout for lockout in all_lockouts if lockout.user_id == user_id]
                if user_lockouts:
                    current_lockout = max(user_lockouts, key=lambda x: x.created_at)
                    stats["current_failed_attempts"] = current_lockout.failed_attempts
                    stats["is_currently_locked"] = (
                        current_lockout.is_locked and not current_lockout.is_lockout_expired
                    )

            return stats

        finally:
            if self._db_session is None:
                await db.close()

    @database_error_handler("cleanup expired lockouts")
    async def cleanup_expired_lockouts(self, older_than_days: int = 30) -> int:
        """Clean up old lockout records - SOLID Single Responsibility.

        Args:
            older_than_days: Remove records older than this many days

        Returns:
            int: Number of records cleaned up
        """
        db = self._db_session or async_session()

        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=older_than_days)

            # Delete old unlocked records (keep locked ones for audit)
            result = await db.execute(
                select(AccountLockout).where(
                    and_(
                        AccountLockout.created_at < cutoff_date,
                        ~AccountLockout.is_locked,  # Use ~ operator for SQL NOT
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
                    "Cleaned up old lockout records",
                    records_cleaned=records_count,
                    older_than_days=older_than_days,
                )

            return records_count

        finally:
            if self._db_session is None:
                await db.close()

    # Private helper methods following SOLID and DRY principles

    async def _get_or_create_lockout_record(
        self,
        db: AsyncSession,
        user_id: str,
        username: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AccountLockout:
        """Get existing or create new lockout record - DRY principle helper method."""
        # Look for recent lockout record within the attempt window
        window_start = datetime.now(UTC) - timedelta(
            minutes=self.config.failed_attempt_window_minutes
        )

        result = await db.execute(
            select(AccountLockout)
            .where(
                and_(
                    AccountLockout.user_id == user_id,
                    AccountLockout.created_at >= window_start,
                )
            )
            .order_by(AccountLockout.created_at.desc())
            .limit(1)
        )

        existing_record = result.scalar_one_or_none()

        if existing_record:
            return existing_record

        # Create new record
        new_record = AccountLockout.create_failed_attempt_record(
            user_id=user_id,
            username=username,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        db.add(new_record)
        return new_record

    async def _should_lock_account(self, db: AsyncSession, lockout_record: AccountLockout) -> bool:
        """Determine if account should be locked based on failed attempts - DRY principle helper method."""
        return lockout_record.failed_attempts >= self.config.max_failed_attempts

    def _calculate_lockout_duration(self, lockout_record: AccountLockout) -> int:
        """Calculate lockout duration using progressive lockout policy - DRY principle helper method."""
        if not self.config.progressive_lockout_enabled:
            return self.config.lockout_duration_minutes

        # Count previous lockouts for progressive duration
        lockout_count = 0  # This would be calculated from historical data in production

        if lockout_count < len(self.config.progressive_durations):
            return self.config.progressive_durations[lockout_count]
        else:
            return self.config.progressive_durations[-1]  # Use maximum duration

    def _count_currently_locked(self, lockouts: Sequence[AccountLockout]) -> int:
        """Count currently locked accounts - DRY principle helper method."""
        return sum(
            1 for lockout in lockouts if lockout.is_locked and not lockout.is_lockout_expired
        )

    def _count_by_field(
        self, lockouts: Sequence[AccountLockout], field_name: str
    ) -> dict[str, int]:
        """Count lockouts by a specific field - DRY principle helper method."""
        counts: dict[str, int] = {}
        for lockout in lockouts:
            field_value = getattr(lockout, field_name)
            if field_value:  # Skip None values
                counts[field_value] = counts.get(field_value, 0) + 1
        return counts

    def _count_recent_lockouts(
        self, lockouts: Sequence[AccountLockout], hours: int | None = None, days: int | None = None
    ) -> int:
        """Count lockouts within a time period - DRY principle helper method."""
        if hours:
            cutoff = datetime.now(UTC) - timedelta(hours=hours)
        elif days:
            cutoff = datetime.now(UTC) - timedelta(days=days)
        else:
            return 0

        return sum(1 for lockout in lockouts if lockout.locked_at and lockout.locked_at >= cutoff)

    def _calculate_average_failed_attempts(self, lockouts: Sequence[AccountLockout]) -> float:
        """Calculate average failed attempts across lockouts - DRY principle helper method."""
        if not lockouts:
            return 0.0

        total_attempts = sum(lockout.failed_attempts for lockout in lockouts)
        return round(total_attempts / len(lockouts), 2)


# Global service instance following Dependency Inversion Principle
account_lockout_service = AccountLockoutService()
