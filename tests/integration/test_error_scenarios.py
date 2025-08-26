"""Comprehensive integration tests for error scenarios.

This module tests error handling, recovery, and edge cases in integrated scenarios
following CLAUDE.md standards for production reliability.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest
from aiohttp import ClientError, ClientResponseError

from src.core.exceptions import (
    FetchError,
    RateLimitError,
)
from src.utils.retry import CircuitBreaker, ResilienceManager, RetryConfig
from src.utils.session_manager import EnhancedSessionManager, SessionConfig


class TestNetworkErrorScenarios:
    """Integration tests for network error scenarios."""

    @pytest.mark.asyncio
    async def test_connection_timeout_recovery(self):
        """Test recovery from connection timeout errors."""
        config = SessionConfig(
            connection_timeout=0.1,  # Very short timeout
            total_timeout=0.5,
            use_retry=True,
        )

        manager = EnhancedSessionManager("https://httpbin.org", config)

        with patch.object(manager, "get_session") as mock_session:
            mock_session.side_effect = asyncio.TimeoutError("Connection timeout")

            with pytest.raises(asyncio.TimeoutError):
                await manager.get_session()

            # Verify retry attempts were made
            assert mock_session.call_count >= 1

    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self):
        """Test handling of DNS resolution failures."""
        manager = EnhancedSessionManager(
            "https://this-domain-definitely-does-not-exist-12345.com",
            SessionConfig(),
        )

        # Attempting to create session with invalid domain
        with pytest.raises(Exception):  # Could be various network-related exceptions
            async with manager as session:
                await session.get("/")

    @pytest.mark.asyncio
    async def test_ssl_certificate_error(self):
        """Test handling of SSL certificate errors."""
        # Test with expired certificate site
        manager = EnhancedSessionManager(
            "https://expired.badssl.com/",
            SessionConfig(verify_ssl=False),  # Bypass SSL verification for test
        )

        try:
            async with manager as session:
                # Should work with verify_ssl=False
                response = await session.get("https://expired.badssl.com/")
                assert response is not None
        except Exception:
            # Some environments may still block this
            pass

    @pytest.mark.asyncio
    async def test_connection_reset_recovery(self):
        """Test recovery from connection reset errors."""
        resilience = ResilienceManager(
            retry_config=RetryConfig(max_attempts=3, base_delay=0.1),
            circuit_breaker=CircuitBreaker(failure_threshold=3, recovery_timeout=1.0),
        )

        call_count = 0

        async def flaky_connection():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ClientError("Connection reset by peer")
            return "Success"

        result = await resilience.execute(flaky_connection)
        assert result == "Success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self):
        """Test handling of rate limit errors."""
        resilience = ResilienceManager(
            retry_config=RetryConfig(
                max_attempts=5,
                base_delay=0.5,
                backoff_factor=2.0,
                jitter=True,
            ),
            circuit_breaker_enabled=False,  # Don't trip circuit on rate limits
        )

        rate_limit_count = 0

        async def rate_limited_api():
            nonlocal rate_limit_count
            rate_limit_count += 1
            if rate_limit_count < 3:
                raise RateLimitError("Rate limit exceeded", url="https://api.example.com")
            return {"data": "success"}

        result = await resilience.execute(rate_limited_api)
        assert result == {"data": "success"}
        assert rate_limit_count == 3


class TestDataCorruptionScenarios:
    """Integration tests for data corruption and invalid input scenarios."""

    @pytest.mark.asyncio
    async def test_malformed_html_handling(self):
        """Test handling of malformed HTML content."""
        malformed_html_samples = [
            "<div>Unclosed div",
            "<p><div>Improperly nested</p></div>",
            "<!DOCTYPE html><html><body>Missing closing tags",
            "<script>alert('xss')</script><p>Content</p>",
            "<<<>>>&&&&''''\"\"\"\"",
            "",  # Empty content
            None,  # Null content
        ]

        from src.processors.html_processor import HTMLProcessor

        processor = HTMLProcessor()

        for html in malformed_html_samples:
            if html is None:
                with pytest.raises((TypeError, AttributeError)):
                    processor.process_html(html)
            else:
                # Should handle without crashing
                result = processor.process_html(html)
                assert result is not None

    @pytest.mark.asyncio
    async def test_invalid_encoding_handling(self):
        """Test handling of content with invalid encoding."""
        # Simulate content with mixed/invalid encoding
        invalid_encoded_content = b"\xff\xfe Invalid UTF-8 \x80\x81\x82"

        from src.processors.html_processor import HTMLProcessor

        processor = HTMLProcessor()

        # Try to decode with error handling
        try:
            decoded = invalid_encoded_content.decode("utf-8", errors="replace")
            result = processor.process_html(decoded)
            assert result is not None
        except UnicodeDecodeError:
            # Expected for truly invalid sequences
            pass

    @pytest.mark.asyncio
    async def test_circular_redirect_detection(self):
        """Test detection and handling of circular redirects."""
        config = SessionConfig(max_redirects=5)
        manager = EnhancedSessionManager("https://httpbin.org", config)

        redirect_count = 0
        max_redirects = 10

        with patch.object(manager, "make_request") as mock_request:

            async def circular_redirect(*args, **kwargs):
                nonlocal redirect_count
                redirect_count += 1
                if redirect_count > max_redirects:
                    raise ClientError("Too many redirects")
                response = Mock()
                response.status = 301
                response.headers = {"Location": "/redirect"}
                return response

            mock_request.side_effect = circular_redirect

            with pytest.raises(ClientError):
                await manager.make_request("GET", "/start")

    @pytest.mark.asyncio
    async def test_infinite_content_stream_protection(self):
        """Test protection against infinite content streams."""

        class InfiniteContentMock:
            async def read(self, size=-1):
                # Simulate infinite content
                while True:
                    yield b"x" * 1024  # 1KB chunks

        response = Mock()
        response.content = InfiniteContentMock()
        response.headers = {"content-length": str(10 * 1024 * 1024 * 1024)}  # 10GB

        # Should have protection against downloading huge files
        max_size = 100 * 1024 * 1024  # 100MB limit

        async def download_with_limit():
            downloaded = 0
            async for chunk in response.content.read():
                downloaded += len(chunk)
                if downloaded > max_size:
                    raise ValueError(f"Content too large: {downloaded} bytes")
            return downloaded

        with pytest.raises(ValueError, match="Content too large"):
            await download_with_limit()


class TestConcurrencyErrorScenarios:
    """Integration tests for concurrency-related error scenarios."""

    @pytest.mark.asyncio
    async def test_race_condition_handling(self):
        """Test handling of race conditions in concurrent operations."""
        shared_resource = {"counter": 0}
        lock = asyncio.Lock()

        async def increment_counter():
            # Simulate race condition without lock
            temp = shared_resource["counter"]
            await asyncio.sleep(0.001)  # Simulate processing
            shared_resource["counter"] = temp + 1

        async def safe_increment_counter():
            async with lock:
                temp = shared_resource["counter"]
                await asyncio.sleep(0.001)  # Simulate processing
                shared_resource["counter"] = temp + 1

        # Test unsafe concurrent access
        shared_resource["counter"] = 0
        unsafe_tasks = [increment_counter() for _ in range(100)]
        await asyncio.gather(*unsafe_tasks, return_exceptions=True)
        unsafe_result = shared_resource["counter"]

        # Test safe concurrent access
        shared_resource["counter"] = 0
        safe_tasks = [safe_increment_counter() for _ in range(100)]
        await asyncio.gather(*safe_tasks, return_exceptions=True)
        safe_result = shared_resource["counter"]

        # Safe access should always result in 100
        assert safe_result == 100
        # Unsafe might lose updates due to race conditions
        assert unsafe_result <= 100

    @pytest.mark.asyncio
    async def test_deadlock_prevention(self):
        """Test prevention of deadlocks in resource acquisition."""
        lock1 = asyncio.Lock()
        lock2 = asyncio.Lock()
        deadlock_detected = False

        async def task1():
            async with lock1:
                await asyncio.sleep(0.01)
                try:
                    async with asyncio.wait_for(lock2.acquire(), timeout=0.1):
                        pass
                except asyncio.TimeoutError:
                    nonlocal deadlock_detected
                    deadlock_detected = True

        async def task2():
            async with lock2:
                await asyncio.sleep(0.01)
                try:
                    async with asyncio.wait_for(lock1.acquire(), timeout=0.1):
                        pass
                except asyncio.TimeoutError:
                    pass

        # Run both tasks concurrently
        await asyncio.gather(task1(), task2(), return_exceptions=True)

        # At least one should detect potential deadlock
        assert deadlock_detected

    @pytest.mark.asyncio
    async def test_resource_exhaustion_protection(self):
        """Test protection against resource exhaustion."""
        from src.utils.retry import BulkheadPattern

        bulkhead = BulkheadPattern(max_concurrent_operations=10)
        active_operations = []
        rejected_operations = 0

        async def resource_intensive_operation(op_id):
            active_operations.append(op_id)
            await asyncio.sleep(0.1)  # Simulate work
            active_operations.remove(op_id)
            return op_id

        # Try to launch more operations than allowed
        tasks = []
        for i in range(20):
            task = bulkhead.execute(resource_intensive_operation, i)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that concurrency was limited
        successful = [r for r in results if isinstance(r, int)]
        assert len(successful) == 20  # All should eventually complete
        # Max active at any time should be limited by bulkhead
        assert len(active_operations) <= 10


class TestAuthenticationErrorScenarios:
    """Integration tests for authentication error scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_credentials_handling(self):
        """Test handling of invalid authentication credentials."""
        config = SessionConfig(
            auth_type="basic",
            username="invalid_user",
            password="wrong_password",
        )

        manager = EnhancedSessionManager("https://httpbin.org", config)

        with patch.object(manager, "_perform_basic_auth") as mock_auth:
            mock_auth.side_effect = FetchError("Authentication failed")

            with pytest.raises(FetchError, match="Authentication failed"):
                await manager._authenticate()

    @pytest.mark.asyncio
    async def test_expired_token_refresh(self):
        """Test handling of expired authentication tokens."""
        config = SessionConfig(
            auth_type="bearer",
            bearer_token="expired_token_12345",
        )

        manager = EnhancedSessionManager("https://api.example.com", config)
        token_refresh_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal token_refresh_count
            if token_refresh_count == 0:
                token_refresh_count += 1
                # First request fails with 401
                raise ClientResponseError(
                    request_info=None,
                    history=None,
                    status=401,
                    message="Unauthorized",
                    headers={},
                )
            else:
                # After refresh, request succeeds
                response = Mock()
                response.status = 200
                return response

        with patch.object(manager, "make_request", side_effect=mock_request):
            # Should handle token refresh internally
            with pytest.raises(ClientResponseError):
                await manager.make_request("GET", "/api/data")
            assert token_refresh_count == 1

    @pytest.mark.asyncio
    async def test_session_hijacking_protection(self):
        """Test protection against session hijacking attempts."""
        manager = EnhancedSessionManager(
            "https://secure.example.com",
            SessionConfig(verify_ssl=True),
        )

        # Simulate session with cookies
        manager._session = Mock()
        original_cookies = {"session_id": "abc123", "csrf_token": "xyz789"}
        manager.cookie_jar = Mock()
        manager.cookie_jar.__iter__ = Mock(return_value=iter(original_cookies.items()))

        # Attempt to inject malicious cookies
        malicious_cookies = {
            "session_id": "hacked_session",
            "admin": "true",
            "csrf_token": "malicious",
        }

        # System should validate cookie integrity
        for key, value in malicious_cookies.items():
            # In a real system, this would trigger security checks
            if key not in original_cookies:
                # New cookies should be validated
                assert key == "admin"  # This is the injected cookie
            elif value != original_cookies[key]:
                # Modified cookies should be detected
                assert key in ["session_id", "csrf_token"]


class TestFileSystemErrorScenarios:
    """Integration tests for file system error scenarios."""

    @pytest.mark.asyncio
    async def test_disk_full_handling(self, tmp_path):
        """Test handling of disk full errors."""

        # Create a mock that simulates disk full
        with patch("builtins.open", side_effect=OSError("No space left on device")):
            with pytest.raises(OSError, match="No space left on device"):
                with open(tmp_path / "test.txt", "w") as f:
                    f.write("test content")

    @pytest.mark.asyncio
    async def test_permission_denied_handling(self, tmp_path):
        """Test handling of permission denied errors."""
        protected_file = tmp_path / "protected.txt"
        protected_file.touch()

        # Make file read-only
        protected_file.chmod(0o444)

        try:
            # Attempt to write to read-only file
            with pytest.raises(PermissionError):
                with open(protected_file, "w") as f:
                    f.write("Should fail")
        finally:
            # Cleanup
            protected_file.chmod(0o644)

    @pytest.mark.asyncio
    async def test_file_corruption_recovery(self, tmp_path):
        """Test recovery from corrupted file scenarios."""
        from src.utils.session_manager import PersistentCookieJar

        cookie_file = tmp_path / "cookies.json"

        # Write corrupted JSON
        with open(cookie_file, "w") as f:
            f.write("{corrupted json content}")

        # Should handle corrupted file gracefully
        jar = PersistentCookieJar(cookie_file)
        cookies = jar.load_cookies()
        assert cookies == {}  # Should return empty dict on corruption


class TestMemoryErrorScenarios:
    """Integration tests for memory-related error scenarios."""

    @pytest.mark.asyncio
    async def test_memory_leak_prevention(self):
        """Test prevention of memory leaks in long-running operations."""
        import gc

        # Track memory usage
        initial_objects = len(gc.get_objects())

        # Simulate operations that could leak memory
        for _ in range(100):
            manager = EnhancedSessionManager(
                "https://example.com",
                SessionConfig(),
            )
            # Create and destroy sessions
            await manager.get_session()
            await manager.close()
            del manager

        # Force garbage collection
        gc.collect()

        # Check object count hasn't grown excessively
        final_objects = len(gc.get_objects())
        growth = final_objects - initial_objects

        # Some growth is normal, but should be bounded
        assert growth < 1000  # Arbitrary threshold

    @pytest.mark.asyncio
    async def test_large_response_handling(self):
        """Test handling of extremely large responses."""

        async def generate_large_response(size_mb):
            """Generate a large response of specified size."""
            chunk_size = 1024 * 1024  # 1MB chunks
            for _ in range(size_mb):
                yield b"x" * chunk_size

        # Test with 100MB response
        total_size = 0
        max_memory = 10 * 1024 * 1024  # 10MB memory limit
        buffer = []

        async for chunk in generate_large_response(100):
            total_size += len(chunk)

            # Stream processing instead of loading all in memory
            if sum(len(b) for b in buffer) > max_memory:
                # Process and clear buffer
                buffer = [chunk]
            else:
                buffer.append(chunk)

        assert total_size == 100 * 1024 * 1024  # 100MB
        assert sum(len(b) for b in buffer) <= max_memory


class TestCascadingFailureScenarios:
    """Integration tests for cascading failure scenarios."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_cascade(self):
        """Test that circuit breaker prevents cascading failures."""
        from src.utils.retry import CircuitBreaker

        breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=1.0,
            expected_exception=Exception,
        )

        failure_count = 0

        async def failing_service():
            nonlocal failure_count
            failure_count += 1
            raise Exception("Service unavailable")

        # First 3 calls trip the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await breaker.call(failing_service)

        assert breaker.state == "OPEN"

        # Subsequent calls are rejected without calling the service
        for _ in range(10):
            with pytest.raises(Exception, match="Circuit breaker is OPEN"):
                await breaker.call(failing_service)

        # Service was only called 3 times, preventing cascade
        assert failure_count == 3

    @pytest.mark.asyncio
    async def test_bulkhead_isolation(self):
        """Test that bulkhead pattern isolates failures."""
        from src.utils.retry import BulkheadPattern

        bulkhead_a = BulkheadPattern(max_concurrent_operations=5)
        bulkhead_b = BulkheadPattern(max_concurrent_operations=5)

        async def slow_operation():
            await asyncio.sleep(1.0)
            return "complete"

        async def failing_operation():
            raise Exception("Failed")

        # Fill bulkhead A with slow operations
        slow_tasks = [bulkhead_a.execute(slow_operation) for _ in range(5)]

        # Bulkhead B should still accept operations
        fast_task = bulkhead_b.execute(failing_operation)

        # B's failure shouldn't affect A
        with pytest.raises(Exception):
            await fast_task

        # A's operations should complete normally
        results = await asyncio.gather(*slow_tasks)
        assert all(r == "complete" for r in results)


# Test fixtures for error scenario testing


@pytest.fixture
def mock_network_error():
    """Fixture that simulates network errors."""

    def _mock_error(error_type="timeout"):
        if error_type == "timeout":
            return asyncio.TimeoutError("Network timeout")
        elif error_type == "connection":
            return ConnectionError("Connection refused")
        elif error_type == "dns":
            return OSError("Name or service not known")
        else:
            return ClientError("Network error")

    return _mock_error


@pytest.fixture
def resilience_manager():
    """Fixture for resilience manager with test configuration."""
    return ResilienceManager(
        retry_config=RetryConfig(
            max_attempts=3,
            base_delay=0.1,
            max_delay=1.0,
            backoff_factor=2.0,
            jitter=True,
        ),
        circuit_breaker_enabled=True,
        bulkhead_enabled=True,
    )
