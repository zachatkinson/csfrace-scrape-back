"""Centralized SQL query patterns for PERFECT DRY compliance.

ZERO TOLERANCE for duplicate SQL patterns.
Single source of truth for ALL common SQL operations across the entire system.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from sqlalchemy import Select, and_, delete, desc, func, or_, select, update
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.elements import ColumnElement

from src.core.logging_hierarchy import get_database_logger

logger = get_database_logger()

# Type variable for SQLAlchemy models
ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class QueryBuilder:
    """Perfect SQL query centralization - zero duplication allowed."""

    @staticmethod
    def paginated_select(
        table: type[ModelType],
        where_clause: ColumnElement[Any] | None = None,
        order_by: ColumnElement[Any] | None = None,
        skip: int = 0,
        limit: int = 100,
        order_desc: bool = True,
    ) -> Select[Any]:
        """Perfect pagination pattern - used everywhere."""
        stmt: Select[Any] = select(table)

        if where_clause is not None:
            stmt = stmt.where(where_clause)

        if order_by is not None:
            stmt = stmt.order_by(desc(order_by)) if order_desc else stmt.order_by(order_by)
        else:
            # Default ordering by created_at if available
            if hasattr(table, "created_at"):
                stmt = stmt.order_by(desc(table.created_at))  # type: ignore[attr-defined]

        return stmt.offset(skip).limit(limit)

    @staticmethod
    def count_query(
        table: type[ModelType], where_clause: ColumnElement[Any] | None = None
    ) -> Select[Any]:
        """Perfect count pattern - used everywhere."""
        stmt: Select[Any] = select(func.count(table.id))  # type: ignore[attr-defined]

        if where_clause is not None:
            stmt = stmt.where(where_clause)

        return stmt

    @staticmethod
    def soft_delete(
        table: type[ModelType],
        id_field: ColumnElement[Any],
        id_value: Any,
        deleted_at_field: str | None = "deleted_at",
        is_deleted_field: str | None = "is_deleted",
    ) -> Any:
        """Perfect soft delete pattern - used everywhere."""
        update_values: dict[str, Any] = {}

        if deleted_at_field and hasattr(table, deleted_at_field):
            update_values[deleted_at_field] = datetime.now(UTC)

        if is_deleted_field and hasattr(table, is_deleted_field):
            update_values[is_deleted_field] = True

        if hasattr(table, "updated_at"):
            update_values["updated_at"] = datetime.now(UTC)

        return update(table).where(id_field == id_value).values(**update_values)

    @staticmethod
    def restore_soft_deleted(
        table: type[ModelType],
        id_field: ColumnElement[Any],
        id_value: Any,
        deleted_at_field: str | None = "deleted_at",
        is_deleted_field: str | None = "is_deleted",
    ) -> Any:
        """Perfect soft delete restore pattern - used everywhere."""
        update_values: dict[str, Any] = {}

        if deleted_at_field and hasattr(table, deleted_at_field):
            update_values[deleted_at_field] = None

        if is_deleted_field and hasattr(table, is_deleted_field):
            update_values[is_deleted_field] = False

        if hasattr(table, "updated_at"):
            update_values["updated_at"] = datetime.now(UTC)

        return update(table).where(id_field == id_value).values(**update_values)

    @staticmethod
    def find_by_id(table: type[ModelType], id_value: Any) -> Select[Any]:
        """Perfect find by ID pattern - used everywhere."""
        return select(table).where(table.id == id_value)  # type: ignore[attr-defined]

    @staticmethod
    def find_by_field(
        table: type[ModelType], field: ColumnElement[Any], value: Any, include_deleted: bool = False
    ) -> Select[Any]:
        """Perfect find by field pattern - used everywhere."""
        stmt: Select[Any] = select(table).where(field == value)

        # Exclude soft-deleted records by default
        if not include_deleted and hasattr(table, "is_deleted"):
            stmt = stmt.where(table.is_deleted.is_(False))  # type: ignore[attr-defined]

        return stmt

    @staticmethod
    def find_by_multiple_fields(
        table: type[ModelType],
        filters: dict[str, Any],
        include_deleted: bool = False,
        use_or: bool = False,
    ) -> Select[Any]:
        """Perfect multi-field search pattern - used everywhere."""
        stmt: Select[Any] = select(table)

        if filters:
            conditions = []
            for field_name, value in filters.items():
                if hasattr(table, field_name):
                    field = getattr(table, field_name)
                    if isinstance(value, list):
                        conditions.append(field.in_(value))
                    else:
                        conditions.append(field == value)

            if conditions:
                stmt = stmt.where(or_(*conditions)) if use_or else stmt.where(and_(*conditions))

        # Exclude soft-deleted records by default
        if not include_deleted and hasattr(table, "is_deleted"):
            stmt = stmt.where(table.is_deleted.is_(False))  # type: ignore[attr-defined]

        return stmt

    @staticmethod
    def update_by_id(
        table: type[ModelType],
        id_value: Any,
        update_data: dict[str, Any],
        update_timestamp: bool = True,
    ) -> Any:
        """Perfect update by ID pattern - used everywhere."""
        if update_timestamp and hasattr(table, "updated_at"):
            update_data = update_data.copy()  # Don't mutate original
            update_data["updated_at"] = datetime.now(UTC)

        return update(table).where(table.id == id_value).values(**update_data)  # type: ignore[attr-defined]

    @staticmethod
    def delete_by_id(table: type[ModelType], id_value: Any) -> Any:
        """Perfect hard delete by ID pattern - used everywhere."""
        return delete(table).where(table.id == id_value)  # type: ignore[attr-defined]

    @staticmethod
    def bulk_update(
        table: type[ModelType],
        where_clause: ColumnElement[Any],
        update_data: dict[str, Any],
        update_timestamp: bool = True,
    ) -> Any:
        """Perfect bulk update pattern - used everywhere."""
        if update_timestamp and hasattr(table, "updated_at"):
            update_data = update_data.copy()  # Don't mutate original
            update_data["updated_at"] = datetime.now(UTC)

        return update(table).where(where_clause).values(**update_data)

    @staticmethod
    def bulk_delete(table: type[ModelType], where_clause: ColumnElement[Any]) -> Any:
        """Perfect bulk delete pattern - used everywhere."""
        return delete(table).where(where_clause)

    @staticmethod
    def exists_query(table: type[ModelType], where_clause: ColumnElement[Any]) -> Select[Any]:
        """Perfect exists check pattern - used everywhere."""
        return select(func.count(table.id) > 0).where(where_clause)  # type: ignore[attr-defined]

    @staticmethod
    def search_text(
        table: type[ModelType],
        search_fields: list[ColumnElement[Any]],
        search_term: str,
        include_deleted: bool = False,
    ) -> Select[Any]:
        """Perfect text search pattern - used everywhere."""
        if not search_term.strip():
            return select(table).where(func.false())  # No results for empty search

        search_conditions = []
        search_pattern = f"%{search_term.strip()}%"

        for field in search_fields:
            search_conditions.append(field.ilike(search_pattern))

        stmt: Select[Any] = select(table).where(or_(*search_conditions))

        # Exclude soft-deleted records by default
        if not include_deleted and hasattr(table, "is_deleted"):
            stmt = stmt.where(table.is_deleted.is_(False))  # type: ignore[attr-defined]

        return stmt

    @staticmethod
    def date_range_query(
        table: type[ModelType],
        date_field: ColumnElement[Any],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        include_deleted: bool = False,
    ) -> Select[Any]:
        """Perfect date range query pattern - used everywhere."""
        stmt: Select[Any] = select(table)

        conditions = []
        if start_date:
            conditions.append(date_field >= start_date)
        if end_date:
            conditions.append(date_field <= end_date)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Exclude soft-deleted records by default
        if not include_deleted and hasattr(table, "is_deleted"):
            stmt = stmt.where(table.is_deleted.is_(False))  # type: ignore[attr-defined]

        return stmt

    @staticmethod
    def active_records_only(stmt: Select[Any], table: type[ModelType]) -> Select[Any]:
        """Perfect active records filter - used everywhere."""
        if hasattr(table, "is_active"):
            stmt = stmt.where(table.is_active.is_(True))  # type: ignore[attr-defined]
        if hasattr(table, "is_deleted"):
            stmt = stmt.where(table.is_deleted.is_(False))  # type: ignore[attr-defined]
        return stmt


class UserQueries:
    """Perfect user-specific query patterns - OAuth/SSO focused."""

    @staticmethod
    def find_by_email(user_table: type[ModelType], email: str) -> Select[Any]:
        """Perfect user by email query - used everywhere."""
        return QueryBuilder.find_by_field(user_table, user_table.email, email)  # type: ignore[attr-defined]

    @staticmethod
    def find_by_username(user_table: type[ModelType], username: str) -> Select[Any]:
        """Perfect user by username query - used everywhere."""
        return QueryBuilder.find_by_field(user_table, user_table.username, username)  # type: ignore[attr-defined]

    @staticmethod
    def find_active_users(
        user_table: type[ModelType], skip: int = 0, limit: int = 100
    ) -> Select[Any]:
        """Perfect active users query - used everywhere."""
        where_clause = user_table.is_active.is_(True)  # type: ignore[attr-defined]
        return QueryBuilder.paginated_select(
            user_table,
            where_clause=where_clause,
            order_by=user_table.created_at,  # type: ignore[attr-defined]
            skip=skip,
            limit=limit,
        )

    @staticmethod
    def find_users_by_provider(
        user_table: type[ModelType], linked_account_table: type[ModelType], provider: str
    ) -> Select[Any]:
        """Perfect users by OAuth provider query - used everywhere."""
        return (
            select(user_table)
            .join(linked_account_table, user_table.id == linked_account_table.user_id)  # type: ignore[attr-defined]
            .where(linked_account_table.provider == provider)  # type: ignore[attr-defined]
            .where(user_table.is_active.is_(True))  # type: ignore[attr-defined]
        )

    @staticmethod
    def count_active_users(user_table: type[ModelType]) -> Select[Any]:
        """Perfect active users count - used everywhere."""
        return QueryBuilder.count_query(user_table, where_clause=user_table.is_active.is_(True))  # type: ignore[attr-defined]


class JobQueries:
    """Perfect job-specific query patterns."""

    @staticmethod
    def find_user_jobs(
        job_table: type[ModelType],
        user_id: str,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Select[Any]:
        """Perfect user jobs query - used everywhere."""
        conditions = [job_table.user_id == user_id]  # type: ignore[attr-defined]

        if status:
            conditions.append(job_table.status == status)  # type: ignore[attr-defined]

        where_clause = and_(*conditions)
        return QueryBuilder.paginated_select(
            job_table,
            where_clause=where_clause,
            order_by=job_table.created_at,  # type: ignore[attr-defined]
            skip=skip,
            limit=limit,
        )

    @staticmethod
    def find_jobs_by_status(
        job_table: type[ModelType], status: str, skip: int = 0, limit: int = 100
    ) -> Select[Any]:
        """Perfect jobs by status query - used everywhere."""
        return QueryBuilder.paginated_select(
            job_table,
            where_clause=job_table.status == status,  # type: ignore[attr-defined]
            order_by=job_table.created_at,  # type: ignore[attr-defined]
            skip=skip,
            limit=limit,
        )

    @staticmethod
    def find_pending_jobs(job_table: type[ModelType]) -> Select[Any]:
        """Perfect pending jobs query - used everywhere."""
        where_clause = job_table.status == "pending"  # type: ignore[attr-defined]

        return (
            select(job_table)
            .where(where_clause)
            .order_by(
                job_table.created_at.asc(),  # type: ignore[attr-defined]  # Oldest first
            )
        )

    @staticmethod
    def cleanup_jobs(
        job_table: type[ModelType], older_than: datetime, status_filter: list[str] | None = None
    ) -> Any:
        """Perfect jobs cleanup - used everywhere."""
        conditions = [job_table.created_at < older_than]  # type: ignore[attr-defined]

        if status_filter:
            conditions.append(job_table.status.in_(status_filter))  # type: ignore[attr-defined]

        where_clause = and_(*conditions)
        return QueryBuilder.bulk_delete(job_table, where_clause)


class AuthQueries:
    """Perfect authentication-specific query patterns."""

    @staticmethod
    def find_revoked_token(revoked_token_table: type[ModelType], jti: str) -> Select[Any]:
        """Perfect revoked token check - used everywhere."""
        return QueryBuilder.find_by_field(revoked_token_table, revoked_token_table.jti, jti)  # type: ignore[attr-defined]

    @staticmethod
    def find_user_tokens(
        revoked_token_table: type[ModelType], user_id: str, token_type: str | None = None
    ) -> Select[Any]:
        """Perfect user tokens query - used everywhere."""
        conditions = [revoked_token_table.user_id == user_id]  # type: ignore[attr-defined]

        if token_type:
            conditions.append(revoked_token_table.token_type == token_type)  # type: ignore[attr-defined]

        where_clause = and_(*conditions)
        return select(revoked_token_table).where(where_clause)

    @staticmethod
    def cleanup_expired_tokens(revoked_token_table: type[ModelType], cutoff_date: datetime) -> Any:
        """Perfect expired tokens cleanup - used everywhere."""
        where_clause = and_(
            revoked_token_table.expires_at < cutoff_date,  # type: ignore[attr-defined]
            revoked_token_table.token_type != "bulk_revocation",  # type: ignore[attr-defined]  # Keep audit records  # noqa: S105
        )
        return QueryBuilder.bulk_delete(revoked_token_table, where_clause)

    @staticmethod
    def find_failed_attempts(
        lockout_table: type[ModelType], user_id: str, time_window: datetime
    ) -> Select[Any]:
        """Perfect failed login attempts query - used everywhere."""
        where_clause = and_(
            lockout_table.user_id == user_id,  # type: ignore[attr-defined]
            lockout_table.last_failed_attempt_at >= time_window,  # type: ignore[attr-defined]
        )
        return select(lockout_table).where(where_clause)

    @staticmethod
    def find_locked_account(lockout_table: type[ModelType], user_id: str) -> Select[Any]:
        """Perfect locked account check - used everywhere."""
        where_clause = and_(lockout_table.user_id == user_id, lockout_table.is_locked.is_(True))  # type: ignore[attr-defined]
        return select(lockout_table).where(where_clause)


class MonitoringQueries:
    """Perfect monitoring and metrics query patterns."""

    @staticmethod
    def aggregate_by_time_window(
        _table: type[ModelType],
        date_field: ColumnElement[Any],
        aggregation_field: ColumnElement[Any],
        aggregation_func: str,
        start_time: datetime,
        end_time: datetime,
        group_by_hour: bool = False,
    ) -> Select[Any]:
        """Perfect time-based aggregation - used everywhere."""
        if aggregation_func.lower() == "count":
            agg_expr = func.count(aggregation_field)
        elif aggregation_func.lower() == "sum":
            agg_expr = func.sum(aggregation_field)  # type: ignore[assignment]
        elif aggregation_func.lower() == "avg":
            agg_expr = func.avg(aggregation_field)  # type: ignore[assignment]
        elif aggregation_func.lower() == "max":
            agg_expr = func.max(aggregation_field)  # type: ignore[assignment]
        elif aggregation_func.lower() == "min":
            agg_expr = func.min(aggregation_field)  # type: ignore[assignment]
        else:
            agg_expr = func.count(aggregation_field)

        if group_by_hour:
            time_bucket = func.date_trunc("hour", date_field)
        else:
            time_bucket = func.date_trunc("day", date_field)

        return (
            select(time_bucket.label("time_bucket"), agg_expr.label("value"))
            .where(and_(date_field >= start_time, date_field <= end_time))
            .group_by(time_bucket)
            .order_by(time_bucket)
        )

    @staticmethod
    def get_recent_activity(
        table: type[ModelType],
        date_field: ColumnElement[Any],
        hours_back: int = 24,
        limit: int = 100,
    ) -> Select[Any]:
        """Perfect recent activity query - used everywhere."""
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours_back)
        return (
            select(table).where(date_field >= cutoff_time).order_by(desc(date_field)).limit(limit)
        )


# Convenience aliases for perfect DRY usage
paginated_query = QueryBuilder.paginated_select
count_query = QueryBuilder.count_query
soft_delete_query = QueryBuilder.soft_delete
find_by_id_query = QueryBuilder.find_by_id
update_by_id_query = QueryBuilder.update_by_id
delete_by_id_query = QueryBuilder.delete_by_id
search_text_query = QueryBuilder.search_text
date_range_query = QueryBuilder.date_range_query
user_by_email_query = UserQueries.find_by_email
user_jobs_query = JobQueries.find_user_jobs
revoked_token_query = AuthQueries.find_revoked_token
time_aggregation_query = MonitoringQueries.aggregate_by_time_window
