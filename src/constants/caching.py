"""Caching-related constants for PERFECT SRP compliance.

ZERO TOLERANCE for mixing domains - only caching constants here.
Single source of truth for ALL caching-related configuration.
"""

from src.core.environment import EnvironmentLoader

# Cache Configuration - with validation
DEFAULT_TTL: int = EnvironmentLoader.get_int("DEFAULT_TTL", 1800, min_value=60)  # 30 minutes
CACHE_TTL_HTML: int = EnvironmentLoader.get_int(
    "CACHE_TTL_HTML", 1800, min_value=60
)  # 30 minutes for HTML
CACHE_TTL_IMAGES: int = EnvironmentLoader.get_int(
    "CACHE_TTL_IMAGES", 86400, min_value=300
)  # 24 hours for images
CACHE_TTL_METADATA: int = EnvironmentLoader.get_int(
    "CACHE_TTL_METADATA", 3600, min_value=60
)  # 1 hour for metadata
MAX_CACHE_SIZE_MB: int = EnvironmentLoader.get_int(
    "MAX_CACHE_SIZE_MB", 1000, min_value=100
)  # 1GB max cache

# Cache backend configuration
CACHE_BACKEND: str = EnvironmentLoader.get_optional("CACHE_BACKEND", "file")  # file, redis, memory

# Redis configuration
REDIS_HOST: str = EnvironmentLoader.get_optional("REDIS_HOST", "localhost")
REDIS_PORT: int = EnvironmentLoader.get_int("REDIS_PORT", 6379, min_value=1, max_value=65535)
REDIS_DB: int = EnvironmentLoader.get_int("REDIS_DB", 0, min_value=0, max_value=15)
REDIS_KEY_PREFIX: str = EnvironmentLoader.get_optional("REDIS_KEY_PREFIX", "wp_converter:")

# Redis connection timeouts - configurable for different environments
REDIS_SOCKET_CONNECT_TIMEOUT: float = float(
    EnvironmentLoader.get_optional("REDIS_SOCKET_CONNECT_TIMEOUT", "5.0")
)
REDIS_SOCKET_TIMEOUT: float = float(EnvironmentLoader.get_optional("REDIS_SOCKET_TIMEOUT", "5.0"))

# Robots.txt Configuration
ROBOTS_CACHE_DURATION: int = EnvironmentLoader.get_int(
    "ROBOTS_CACHE_DURATION", 3600, min_value=300
)  # 1 hour
RESPECT_ROBOTS_TXT: bool = EnvironmentLoader.get_bool("RESPECT_ROBOTS_TXT", True)

# Cache cleanup and key management
CACHE_CLEANUP_RATIO: float = 0.8  # Clean to 80% of max size
MAX_KEY_LENGTH: int = EnvironmentLoader.get_int(
    "MAX_KEY_LENGTH", 250, min_value=50, max_value=2000
)  # Maximum cache key length
HASH_LENGTH: int = 16  # Standard hash truncation length
KEY_READABLE_OFFSET: int = 20  # Offset for readable part in long keys
SAMPLE_KEY_COUNT: int = 10  # Number of sample keys for statistics
FILE_READ_BUFFER_SIZE: int = 1024  # Buffer size for file reading
