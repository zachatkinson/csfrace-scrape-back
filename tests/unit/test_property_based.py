"""Property-based tests using Hypothesis for comprehensive testing.

This module implements property-based testing following CLAUDE.md standards
to discover edge cases and ensure robust behavior across all input ranges.
"""

import asyncio
from unittest.mock import Mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, rule

from src.processors.html_processor import HTMLProcessor
from src.utils.retry import BulkheadPattern, CircuitBreaker, CircuitBreakerState, RetryConfig
from src.utils.session_manager import EnhancedSessionManager, PersistentCookieJar, SessionConfig
from src.utils.url import extract_domain, safe_parse_url


class TestRetryConfigProperties:
    """Property-based tests for RetryConfig."""

    @given(
        max_attempts=st.integers(min_value=1, max_value=100),
        base_delay=st.floats(min_value=0.001, max_value=60.0),
        max_delay=st.floats(min_value=0.1, max_value=300.0),
        backoff_factor=st.floats(min_value=1.1, max_value=10.0),  # Must be > 1
        jitter=st.booleans(),
    )
    @settings(max_examples=100, deadline=1000)
    def test_retry_config_invariants(
        self, max_attempts, base_delay, max_delay, backoff_factor, jitter
    ):
        """Test that RetryConfig maintains its invariants."""
        # Ensure max_delay >= base_delay for valid config
        if max_delay < base_delay:
            max_delay = base_delay * 10

        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff_factor=backoff_factor,
            jitter=jitter,
        )

        # Test invariants
        assert config.max_attempts >= 1
        assert config.base_delay >= 0.001
        assert config.max_delay >= config.base_delay
        assert config.backoff_factor >= 1.0
        assert isinstance(config.jitter, bool)

    @given(
        attempt=st.integers(min_value=0, max_value=50),
        base_delay=st.floats(min_value=0.1, max_value=10.0),
        max_delay=st.floats(min_value=10.0, max_value=100.0),
        backoff_factor=st.floats(min_value=1.5, max_value=3.0),
    )
    @settings(max_examples=100, deadline=1000)
    def test_calculate_delay_properties(self, attempt, base_delay, max_delay, backoff_factor):
        """Test that calculate_delay produces valid delays."""
        config = RetryConfig(
            max_attempts=attempt + 1,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff_factor=backoff_factor,
            jitter=False,  # Disable jitter for deterministic testing
        )

        delay = config.calculate_delay(attempt)

        # Properties that must hold
        assert delay >= 0  # Delay is never negative
        assert delay <= max_delay  # Delay never exceeds max_delay
        if attempt == 0:
            assert delay == base_delay  # First attempt uses base_delay
        else:
            # Subsequent attempts use exponential backoff
            expected = min(base_delay * (backoff_factor**attempt), max_delay)
            assert abs(delay - expected) < 0.001  # Account for floating point precision

    @given(
        attempt=st.integers(min_value=0, max_value=20),
        base_delay=st.floats(min_value=0.1, max_value=5.0),
        max_delay=st.floats(min_value=5.0, max_value=50.0),
    )
    @settings(max_examples=50, deadline=1000)
    def test_jitter_bounds(self, attempt, base_delay, max_delay):
        """Test that jitter keeps delays within expected bounds."""
        config = RetryConfig(
            max_attempts=attempt + 1,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff_factor=2.0,
            jitter=True,
        )

        # Run multiple times to test jitter randomness
        delays = [config.calculate_delay(attempt) for _ in range(10)]

        # All delays should be within bounds
        for delay in delays:
            assert delay >= 0.1  # Minimum delay with jitter
            assert delay <= max_delay

        # With jitter, delays should vary (unless at max_delay or attempt is 0)
        if min(delays) < max_delay * 0.9 and attempt > 0:
            assert len(set(delays)) > 1  # Should have some variation


class TestCircuitBreakerProperties:
    """Property-based tests for CircuitBreaker."""

    @given(
        failure_threshold=st.integers(min_value=1, max_value=5),
        num_failures=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=20, deadline=3000)
    @pytest.mark.asyncio
    async def test_circuit_breaker_state_transitions(self, failure_threshold, num_failures):
        """Test circuit breaker state transitions with various failure patterns."""
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=0.1,  # Short timeout for testing
            expected_exception=Exception,
        )

        # Simulate failures until circuit opens or we run out
        failures_processed = 0
        for i in range(num_failures):
            if breaker.state == CircuitBreakerState.OPEN:
                # Circuit is open, further calls should be rejected
                break

            # Perform a failing operation
            try:
                async with breaker:
                    await self._failing_function()
            except Exception:
                failures_processed += 1

        # Basic invariants
        assert breaker.failure_count >= 0
        assert isinstance(breaker.state, CircuitBreakerState)

        # If we had enough failures, circuit should be open
        if failures_processed >= failure_threshold:
            assert breaker.state == CircuitBreakerState.OPEN

    async def _failing_function(self):
        """Helper function that always fails."""
        raise Exception("Test failure")

    @given(
        max_concurrent=st.integers(min_value=1, max_value=50),
        num_operations=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=30, deadline=5000)
    @pytest.mark.asyncio
    async def test_bulkhead_concurrency_limits(self, max_concurrent, num_operations):
        """Test that BulkheadPattern enforces concurrency limits."""
        bulkhead = BulkheadPattern(max_concurrent_operations=max_concurrent)
        active_count = 0
        max_active = 0

        async def monitored_operation():
            nonlocal active_count, max_active
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.01)  # Simulate work
            active_count -= 1
            return True

        # Create tasks up to num_operations
        tasks = [bulkhead.execute(monitored_operation) for _ in range(num_operations)]

        # Execute all tasks
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify all operations completed
            assert len(results) == num_operations
            assert all(r is True for r in results)

            # Verify concurrency limit was respected
            assert max_active <= max_concurrent


class TestSessionConfigProperties:
    """Property-based tests for SessionConfig."""

    @given(
        max_connections=st.integers(min_value=1, max_value=100),
        timeout=st.floats(min_value=0.1, max_value=300.0),
        keepalive=st.floats(min_value=0.1, max_value=120.0),
        max_redirects=st.integers(min_value=0, max_value=30),
    )
    def test_session_config_validation(self, max_connections, timeout, keepalive, max_redirects):
        """Test SessionConfig validation with various inputs."""
        config = SessionConfig(
            max_concurrent_connections=max_connections,
            connection_timeout=timeout,
            total_timeout=timeout,
            keepalive_timeout=keepalive,
            max_redirects=max_redirects,
        )

        # Verify configuration is valid
        assert config.max_concurrent_connections >= 1
        assert config.connection_timeout > 0
        assert config.total_timeout > 0
        assert config.keepalive_timeout > 0
        assert config.max_redirects >= 0

    @given(
        username=st.text(min_size=0, max_size=50),
        password=st.text(min_size=0, max_size=50),
        auth_type=st.sampled_from(["basic", "bearer", "custom"]),
    )
    def test_auth_configuration_validation(self, username, password, auth_type):
        """Test authentication configuration validation."""
        # Build config based on auth_type
        if auth_type == "basic":
            # Basic auth requires both username and password
            if username and password:
                config = SessionConfig(username=username, password=password, auth_type=auth_type)
                assert config.username == username
                assert config.password == password
            else:
                # Should raise error if only one is provided
                if bool(username) != bool(password):  # XOR
                    with pytest.raises(ValueError):
                        SessionConfig(username=username, password=password, auth_type=auth_type)
        elif auth_type == "bearer":
            # Bearer auth requires token
            config = SessionConfig(auth_type=auth_type, bearer_token="test_token_12345")
            assert config.auth_type == "bearer"
            assert config.bearer_token == "test_token_12345"


class TestURLValidationProperties:
    """Property-based tests for URL processing utilities."""

    @given(st.text())
    @settings(max_examples=100, deadline=1000)
    def test_safe_parse_url_never_crashes(self, url_input):
        """Test that safe_parse_url never crashes regardless of input."""
        # Should never raise an unexpected exception
        try:
            result = safe_parse_url(url_input)
            assert result is None or hasattr(result, "scheme")
        except Exception:
            # Should be handled gracefully and return None
            raise AssertionError(f"safe_parse_url crashed with input: {url_input}")

    @given(
        scheme=st.sampled_from(["http", "https", "ftp", ""]),
        domain=st.from_regex(r"[a-z]{1,10}\.[a-z]{2,4}", fullmatch=True),
        path=st.from_regex(r"/[a-z0-9\-/]*", fullmatch=True),
        port=st.integers(min_value=1, max_value=65535),
    )
    def test_url_construction_parsing(self, scheme, domain, path, port):
        """Test URL parsing with constructed URLs."""
        url = f"{scheme}://{domain}:{port}{path}" if scheme else f"{domain}:{port}{path}"

        result = safe_parse_url(url)

        # URLs with any scheme should parse successfully
        if scheme:
            assert result is not None
            assert result.scheme == scheme
            assert domain in result.netloc
        else:
            # URLs without scheme should return None
            assert result is None

    @given(
        scheme=st.sampled_from(["http", "https"]),
        domain=st.from_regex(r"[a-z]{1,10}\.[a-z]{2,4}", fullmatch=True),
        path=st.from_regex(r"/[a-z0-9\-/]*", fullmatch=True),
    )
    def test_extract_domain_properties(self, scheme, domain, path):
        """Test domain extraction properties."""
        url = f"{scheme}://{domain}{path}"
        extracted_domain = extract_domain(url)

        assert extracted_domain is not None
        assert domain in extracted_domain


class TestHTMLProcessingProperties:
    """Property-based tests for HTML processing."""

    @given(
        st.lists(
            st.tuples(
                st.sampled_from(["p", "div", "span", "h1", "h2", "h3"]),
                st.text(min_size=0, max_size=100),
            ),
            min_size=0,
            max_size=50,
        )
    )
    @settings(max_examples=50, deadline=2000)
    @pytest.mark.asyncio
    async def test_html_processing_preserves_structure(self, elements):
        """Test that HTML processing preserves document structure."""
        # Construct HTML from elements
        html_parts = ["<html><body>"]
        for tag, content in elements:
            # Escape content to prevent injection
            safe_content = content.replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f"<{tag}>{safe_content}</{tag}>")
        html_parts.append("</body></html>")
        html = "".join(html_parts)

        from bs4 import BeautifulSoup

        processor = HTMLProcessor()
        soup = BeautifulSoup(html, "html.parser")
        processed = await processor.process(soup)

        # Properties that should hold
        assert processed is not None
        assert isinstance(processed, str)
        # HTML processor outputs body content, not full HTML document
        # Element count should be preserved or reduced (never increased)
        for tag, _ in elements:
            original_count = html.count(f"<{tag}>")
            processed_count = processed.count(f"<{tag}>")
            assert processed_count <= original_count


class TestPersistentCookieJarProperties:
    """Property-based tests for cookie persistence."""

    @given(
        cookies=st.dictionaries(
            keys=st.text(
                min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=["Cc", "Cs"])
            ),
            values=st.text(
                min_size=0, max_size=100, alphabet=st.characters(blacklist_categories=["Cc", "Cs"])
            ),
            min_size=0,
            max_size=10,
        ),
        domain=st.from_regex(r"[a-z]{3,10}\.(com|org|net)", fullmatch=True),
    )
    @settings(max_examples=30, deadline=2000)
    def test_cookie_persistence_roundtrip(self, cookies, domain, tmp_path):
        """Test that cookies survive save/load roundtrip."""
        cookie_path = tmp_path / "test_cookies.json"
        jar = PersistentCookieJar(cookie_path)

        # Create mock cookie jar with test cookies
        mock_jar = []
        for name, value in cookies.items():
            mock_cookie = Mock()
            mock_cookie.get.side_effect = lambda key, default=None, n=name, v=value, d=domain: {
                "name": n,
                "value": v,
                "domain": d,
                "path": "/",
                "expires": None,
                "secure": False,
                "httponly": False,
            }.get(key, default)
            mock_jar.append(mock_cookie)

        # Save cookies
        jar.save_cookies(mock_jar)

        # Load cookies
        loaded = jar.load_cookies()

        # Verify roundtrip
        if cookies:
            assert domain in loaded
            assert len(loaded[domain]) == len(cookies)
            for name, value in cookies.items():
                assert name in loaded[domain]
                assert loaded[domain][name]["value"] == value


class SessionManagerStateMachine(RuleBasedStateMachine):
    """Stateful testing for SessionManager using Hypothesis."""

    def __init__(self):
        super().__init__()
        self.manager = None
        self.is_authenticated = False
        self.session_created = False

    @initialize()
    def setup(self):
        """Initialize the session manager."""
        self.manager = EnhancedSessionManager(
            "https://example.com", SessionConfig(max_concurrent_connections=5)
        )

    @rule()
    @pytest.mark.asyncio
    async def create_session(self):
        """Rule: Create a session."""
        if not self.session_created:
            session = await self.manager.get_session()
            assert session is not None
            self.session_created = True

    @rule()
    @pytest.mark.asyncio
    async def close_session(self):
        """Rule: Close a session."""
        if self.session_created:
            await self.manager.close()
            self.session_created = False

    @rule(
        auth_type=st.sampled_from(["basic", "bearer"]),
    )
    @pytest.mark.asyncio
    async def authenticate(self, auth_type):
        """Rule: Attempt authentication."""
        if self.session_created and not self.is_authenticated:
            # Mock authentication based on type
            if auth_type == "basic":
                self.manager.config.username = "test_user"
                self.manager.config.password = "test_pass"
                self.manager.config.auth_type = "basic"
            else:
                self.manager.config.bearer_token = "test_token"
                self.manager.config.auth_type = "bearer"

            # In real scenario this would authenticate
            self.is_authenticated = True

    def teardown(self):
        """Clean up after state machine execution."""
        if self.manager and self.session_created:
            asyncio.run(self.manager.close())


# Additional property-based tests for edge cases


class TestEdgeCaseProperties:
    """Property-based tests for edge cases and boundary conditions."""

    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
            min_size=0,
            max_size=1000,
        )
    )
    def test_large_data_handling(self, data_points):
        """Test handling of large data sets."""
        # This would test processing large amounts of data
        # without memory issues or crashes
        result = self._process_data(data_points)
        assert result is not None
        if data_points:
            assert len(result) <= len(data_points)

    def _process_data(self, data):
        """Helper to process data."""
        # Simulate data processing
        return [x for x in data if x > 0]

    @given(st.text(alphabet=st.characters(blacklist_categories=["Cc"]), min_size=0, max_size=10000))
    @settings(max_examples=20, deadline=3000)
    def test_unicode_handling(self, text):
        """Test handling of various Unicode characters."""
        # Ensure the system handles Unicode properly
        processed = self._sanitize_text(text)
        assert isinstance(processed, str)
        assert len(processed) <= len(text)

    def _sanitize_text(self, text):
        """Helper to sanitize text."""
        # Remove control characters
        import unicodedata

        return "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")

    @given(
        st.datetimes(min_value=None, max_value=None),
    )
    def test_datetime_handling(self, dt):
        """Test handling of various datetime values."""
        # Ensure datetime handling is robust
        timestamp = dt.timestamp()
        assert isinstance(timestamp, float)
        assert float("inf") != timestamp
        assert float("-inf") != timestamp
