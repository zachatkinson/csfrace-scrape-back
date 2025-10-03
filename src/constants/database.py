"""Database-related constants for PERFECT SRP compliance.

ZERO TOLERANCE for mixing domains - only database constants here.
Single source of truth for ALL database-related configuration.
"""

from src.core.environment import EnvironmentLoader

# Database connection pool configuration
DATABASE_POOL_SIZE: int = EnvironmentLoader.get_int(
    "DATABASE_POOL_SIZE", 20, min_value=5, max_value=100
)
DATABASE_MAX_OVERFLOW: int = EnvironmentLoader.get_int(
    "DATABASE_MAX_OVERFLOW", 30, min_value=10, max_value=200
)

# Database table names - constants for schema management
PASSKEY_TABLE_NAME: str = "webauthn_credentials"

# Common numerical constants for database operations
BYTES_PER_MB: int = 1024 * 1024  # Byte to MB conversion

# Test Database Configuration
TEST_REDIS_HOST: str = "localhost"
TEST_REDIS_PORT: int = 6379
TEST_REDIS_DB: int = 15  # Use highest DB for tests
TEST_REDIS_KEY_PREFIX: str = "pytest:"

# Test database data
TEST_IMAGE_CONTENT: bytes = b"fake image data"
