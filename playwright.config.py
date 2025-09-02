"""
Playwright configuration for optimal CI performance.
Following official Playwright best practices for 2025.
"""

import os

# Playwright configuration optimized for CI
PLAYWRIGHT_CONFIG = {
    # Use single worker in CI for stability, multiple locally for speed
    "workers": 1 if os.environ.get("CI") else os.cpu_count(),
    # Enable full parallelization when using sharding
    "fullyParallel": True,
    # Retry failed tests in CI
    "retries": 2 if os.environ.get("CI") else 0,
    # Fail fast after 10 failures in CI
    "maxFailures": 10 if os.environ.get("CI") else None,
    # Timeout per test
    "timeout": 30000,  # 30 seconds
    # Global timeout for the entire test run
    "globalTimeout": 1800000,  # 30 minutes
    # Reporter configuration
    "reporter": "blob" if os.environ.get("CI") else "html",
    # Browser configuration
    "use": {
        # Only capture on failures to save space
        "trace": "retain-on-failure",
        "screenshot": "only-on-failure",
        "video": "retain-on-failure",
        # Viewport size
        "viewport": {"width": 1280, "height": 720},
        # Ignore HTTPS errors
        "ignoreHTTPSErrors": True,
        # Headless mode in CI
        "headless": bool(os.environ.get("CI")),
    },
    # Projects configuration - only test with Chromium for speed
    "projects": [
        {
            "name": "chromium",
            "use": {
                "browserName": "chromium",
            },
        },
    ],
}


def get_shard_config():
    """Get sharding configuration from environment variables."""
    shard = os.environ.get("SHARD")
    total_shards = os.environ.get("TOTAL_SHARDS")

    if shard and total_shards:
        return {
            "shard": f"{shard}/{total_shards}",
        }
    return {}


# Export configuration
if __name__ == "__main__":
    import json

    config = {**PLAYWRIGHT_CONFIG, **get_shard_config()}
    print(json.dumps(config, indent=2))
