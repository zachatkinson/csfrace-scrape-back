"""Pluggable health check system for application monitoring.

This package provides a modular health check framework that allows
easy registration and execution of various health checks.
"""

from .api import APIHealthCheck, DependencyHealthCheck
from .base import FunctionHealthCheck, HealthCheck, HealthCheckResult, HealthStatus
from .cache import CacheHealthCheck, RedisHealthCheck
from .database import DatabaseHealthCheck, DatabaseTableHealthCheck
from .registry import HealthCheckRegistry, health_registry

__all__ = [
    "HealthCheck",
    "HealthCheckResult",
    "HealthStatus",
    "FunctionHealthCheck",
    "DatabaseHealthCheck",
    "DatabaseTableHealthCheck",
    "APIHealthCheck",
    "DependencyHealthCheck",
    "CacheHealthCheck",
    "RedisHealthCheck",
    "HealthCheckRegistry",
    "health_registry",
]
