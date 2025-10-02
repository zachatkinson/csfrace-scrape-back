"""Monitoring-related constants for PERFECT SRP compliance.

ZERO TOLERANCE for mixing domains - only monitoring constants here.
Single source of truth for ALL monitoring-related configuration.
"""

from src.core.environment import EnvironmentLoader

# Logging Configuration
LOG_LEVEL: str = EnvironmentLoader.get_optional("LOG_LEVEL", "INFO")  # Configurable via env
LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Logging level constants
LOG_LEVEL_INFO: int = 20  # INFO logging level

# Browser timeouts for monitoring
BROWSER_TIMEOUT: float = float(EnvironmentLoader.get_optional("BROWSER_TIMEOUT", "30.0"))
PAGE_LOAD_TIMEOUT: float = float(EnvironmentLoader.get_optional("PAGE_LOAD_TIMEOUT", "30.0"))
SCRIPT_TIMEOUT: float = float(EnvironmentLoader.get_optional("SCRIPT_TIMEOUT", "10.0"))

# Rendering timeouts for monitoring
RENDER_TIMEOUT: float = float(EnvironmentLoader.get_optional("RENDER_TIMEOUT", "60.0"))
SCREENSHOT_TIMEOUT: float = float(EnvironmentLoader.get_optional("SCREENSHOT_TIMEOUT", "10.0"))

# Network timeouts for monitoring
DNS_TIMEOUT: float = float(EnvironmentLoader.get_optional("DNS_TIMEOUT", "5.0"))
KEEPALIVE_TIMEOUT: float = float(EnvironmentLoader.get_optional("KEEPALIVE_TIMEOUT", "30.0"))

# Progress tracking constants
PROGRESS_START: int = 0
PROGRESS_SETUP: int = 10
PROGRESS_FETCH: int = 20
PROGRESS_PROCESS: int = 60
PROGRESS_COMPLETE: int = 100

# Progress display
PROGRESS_SEPARATOR: str = "-" * 50

# Exit codes
EXIT_CODE_KEYBOARD_INTERRUPT: int = 130

# SEO and content analysis constants
WORDS_PER_MINUTE_READING: int = 200  # Average reading speed
IFRAME_ASPECT_RATIO: str = "16/9"  # Standard video aspect ratio
