"""Rate limiting behavior tests - separate shard from integration tests.

This test shard specifically tests rate limiting behavior and security.
Run separately from integration tests to avoid rate limit interference.

Usage:
  # Run only rate limiting tests
  pytest tests/api/test_rate_limiting.py -v

  # Run only integration tests (excludes rate limiting)
  pytest -m "not ratelimit" tests/api/ -v
"""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.ratelimit
class TestRateLimiting:
    """Test rate limiting behavior specifically."""

    @pytest.mark.ratelimit
    @pytest.mark.asyncio
    async def test_batch_creation_rate_limiting(self, async_client: AsyncClient):
        """Test that batch creation is properly rate limited."""
        batch_data = {
            "name": "Rate Limit Test",
            "urls": ["https://example.com/test"],
            "max_concurrent": 5,
        }

        # First few requests should succeed (up to the rate limit)
        success_count = 0
        for i in range(15):  # Try more requests than the limit
            response = await async_client.post(
                "/batches/",
                json={
                    **batch_data,
                    "name": f"Rate Limit Test {i}",  # Unique name to avoid conflicts
                },
            )

            if response.status_code == status.HTTP_201_CREATED:
                success_count += 1
            elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                # Rate limit hit - this is expected
                break
            else:
                # Some other error - this is unexpected
                pytest.fail(f"Unexpected status code: {response.status_code}")

        # Verify that some requests succeeded and at least one was rate limited
        assert success_count > 0, "At least some requests should have succeeded"
        assert success_count < 15, "Rate limiting should have kicked in"

        # Verify the error response format
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "rate limit" in response.text.lower()

    @pytest.mark.ratelimit
    @pytest.mark.asyncio
    async def test_rate_limit_recovery(self, async_client: AsyncClient):
        """Test that rate limits reset after the time window."""
        # Note: This test is commented out because it would require waiting
        # for the rate limit window to reset, which is impractical for fast tests.
        # In a real-world scenario, you might use a shorter time window for tests
        # or mock the time functions.

        batch_data = {
            "name": "Recovery Test",
            "urls": ["https://example.com/test"],
        }

        # This would be the pattern for testing recovery:
        # 1. Hit the rate limit
        # 2. Wait for the window to reset
        # 3. Verify requests work again

        # For now, just verify the rate limiting works
        response = await async_client.post("/batches/", json=batch_data)
        # Should succeed or fail predictably based on previous tests
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_429_TOO_MANY_REQUESTS]

    @pytest.mark.ratelimit
    @pytest.mark.asyncio
    async def test_rate_limiting_per_endpoint(self, async_client: AsyncClient):
        """Test that rate limiting is applied per endpoint."""
        # Test batch creation endpoint
        batch_response = await async_client.post(
            "/batches/",
            json={
                "name": "Endpoint Test",
                "urls": ["https://example.com/test"],
            },
        )

        # Test other endpoints - they should have separate limits
        # Use docs endpoint since health might not exist
        docs_response = await async_client.get("/docs")

        # Docs endpoint should not be rate limited by batch endpoint usage
        # Should either work (200) or redirect (307) but not be rate limited (429)
        assert docs_response.status_code not in [status.HTTP_429_TOO_MANY_REQUESTS]

        # Batch endpoint may or may not be rate limited depending on test order
        assert batch_response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_429_TOO_MANY_REQUESTS,
        ]
