# Test Suite Documentation

## Overview

This comprehensive test suite follows audit_3.md standards with strict adherence to SOLID principles, DRY compliance, and modern testing best practices. The test structure mirrors the source code organization for maintainability and clear test-to-code mapping.

## Test Architecture

### Directory Structure (Mirrored from src/)
```
tests/
├── conftest.py                    # Shared fixtures and configuration
├── README.md                      # This documentation
├── auth/                          # Mirror src/auth/
│   └── services/
│       ├── test_token_service.py
│       └── test_cookie_service.py
├── database/                      # Mirror src/database/
│   └── services/
│       ├── test_job_service.py
│       └── test_cleanup_service.py
├── integration/                   # Cross-service integration tests
│   └── test_database_workflows.py
└── e2e/                          # Minimal end-to-end tests
    └── test_health_checks.py
```

## Test Categories

### Unit Tests (80%+ coverage target)
- **Location**: `tests/{module}/test_*.py`
- **Purpose**: Test individual components in isolation
- **Pattern**: AAA (Arrange-Act-Assert)
- **Coverage**: All business logic, edge cases, error conditions

### Integration Tests
- **Location**: `tests/integration/`
- **Purpose**: Test service interactions and workflows
- **Focus**: Database operations, service coordination
- **Examples**: Job lifecycle, cleanup workflows

### E2E Tests (Minimal for backend)
- **Location**: `tests/e2e/`
- **Purpose**: Critical system health checks
- **Scope**: Essential backend functionality only
- **Note**: Frontend handles user-facing E2E testing

## Test Infrastructure

### Key Features
- **Factory Pattern**: Centralized test data creation
- **Dependency Injection**: Mocked services for isolation
- **Database Testing**: In-memory SQLite with cleanup
- **Security Testing**: Payload validation, injection tests
- **Performance Testing**: Benchmarks for critical paths

### Fixtures (conftest.py)
```python
# Database fixtures
test_engine          # In-memory SQLite engine
test_session         # Database session with cleanup

# Factory classes
UserFactory          # Create test users
JobFactory           # Create test jobs
OAuthFactory         # Create OAuth test data

# Service fixtures
job_service          # JobService with test DB
cleanup_service      # CleanupService with test DB
mock_token_service   # Mocked TokenService

# Security fixtures
security_test_payloads  # Common attack vectors
```

## Running Tests

### Prerequisites
```bash
# Install dependencies (when available)
pip install pytest pytest-cov pytest-asyncio pytest-benchmark
pip install faker sqlalchemy fastapi
```

### Test Commands
```bash
# Run all tests with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Run specific test categories
pytest -m unit                    # Unit tests only
pytest -m integration            # Integration tests only
pytest -m e2e                   # E2E tests only
pytest -m "not slow"            # Exclude slow tests
pytest -m database              # Database-dependent tests

# Run specific test files
pytest tests/auth/services/test_token_service.py
pytest tests/database/services/test_job_service.py

# Run with performance benchmarks
pytest -m performance --benchmark-only

# Run security tests
pytest -m security

# Verbose output for debugging
pytest -v --tb=short
```

### Coverage Targets
- **Overall**: 80% minimum (configured in .codecov.yml)
- **Core services**: 85%+ coverage
- **New code**: 85%+ coverage required in PRs
- **Critical paths**: 90%+ coverage

## Test Patterns and Best Practices

### AAA Pattern (Arrange-Act-Assert)
```python
def test_create_job_success(self, job_service, sample_job_request):
    # Arrange
    initial_count = session.query(ScrapingJob).count()

    # Act
    result = job_service.create_job(sample_job_request)

    # Assert
    assert result.id is not None
    assert result.status == JobStatus.PENDING.value
```

### Test Isolation
- Each test is independent
- Database cleanup between tests
- Mock external dependencies
- No shared state between tests

### Factory Pattern Usage
```python
# Good: Use factories for test data
job_request = JobFactory.create_job_request(priority=JobPriority.HIGH)
user = UserFactory.create_user(is_active=False)

# Good: Customize factory data for specific tests
oauth_info = OAuthFactory.create_oauth_info(provider="github")
```

### Parameterized Testing
```python
@pytest.mark.parametrize("priority_input,expected_int", [
    (JobPriority.LOW, 1),
    (JobPriority.NORMAL, 5),
    ("high", 8),
    (15, 10),  # Clamped to max
])
def test_normalize_priority(self, job_service, priority_input, expected_int):
    result = job_service._normalize_priority(priority_input)
    assert result == expected_int
```

## Security Testing

### Test Categories
- **Input Validation**: SQL injection, XSS, path traversal
- **Authentication**: Token validation, session security
- **Authorization**: Permission checks, access controls
- **Data Sanitization**: Content cleaning, output encoding

### Security Test Fixtures
```python
@pytest.fixture
def security_test_payloads():
    return {
        "sql_injection": ["' OR '1'='1", "'; DROP TABLE users; --"],
        "xss": ["<script>alert('XSS')</script>"],
        "path_traversal": ["../../../etc/passwd"],
        "command_injection": ["; ls -la", "| whoami"],
    }
```

## Performance Testing

### Benchmarks
- Job creation performance
- Database query optimization
- Memory usage monitoring
- Concurrent operation handling

### Performance Fixtures
```python
@pytest.fixture
def performance_timer():
    class Timer:
        def start(self): self.start_time = time.perf_counter()
        def stop(self): self.end_time = time.perf_counter()
        @property
        def elapsed(self): return self.end_time - self.start_time
    return Timer()
```

## Database Testing

### In-Memory Testing
- SQLite in-memory database for speed
- Full schema creation/teardown
- Transaction isolation
- Foreign key constraint testing

### Test Data Management
```python
# Create test job with specific attributes
job = JobFactory.create_scraping_job(
    session=test_session,
    status=JobStatus.COMPLETED,
    priority=8
)

# Verify database state
assert session.query(ScrapingJob).count() == 1
```

## Continuous Integration

### CodeCov Integration
- Configured in `.codecov.yml`
- 80% coverage threshold
- PR comments with coverage changes
- Branch coverage enabled

### GitHub Actions (when configured)
```yaml
- name: Run tests with coverage
  run: |
    pytest --cov=src --cov-report=xml

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure PYTHONPATH includes src/
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
   ```

2. **Database Connection Issues**
   ```python
   # Check test_session fixture
   # Verify Base.metadata.create_all() call
   ```

3. **Mock Failures**
   ```python
   # Verify mock specifications match actual services
   service = Mock(spec=TokenService)
   ```

4. **Async Test Issues**
   ```python
   # Use pytest-asyncio for async tests
   @pytest.mark.asyncio
   async def test_async_function():
       pass
   ```

### Test Debugging
```bash
# Run with debugging output
pytest -v -s --tb=long

# Run single test with full output
pytest tests/auth/services/test_token_service.py::TestTokenService::test_create_tokens_for_user_success -v -s

# Use pytest debugger
pytest --pdb tests/path/to/test.py
```

## Contributing to Tests

### Guidelines
1. **Follow audit_3.md standards** - No exceptions
2. **Mirror source structure** - Test files must match src structure
3. **Use AAA pattern** - Arrange, Act, Assert consistently
4. **Test edge cases** - Include error conditions and boundaries
5. **Use factories** - Leverage existing factories for test data
6. **Document complex tests** - Add comments for complex test logic
7. **Maintain isolation** - Tests must be independent

### Adding New Tests
1. Create test file in mirrored directory structure
2. Import required fixtures from conftest.py
3. Use appropriate test markers (@pytest.mark.unit, etc.)
4. Follow naming convention: `test_*.py`
5. Include edge cases and error scenarios
6. Add performance tests for critical paths

### Test Markers
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.database` - Requires database
- `@pytest.mark.performance` - Performance benchmarks
- `@pytest.mark.security` - Security-focused tests
- `@pytest.mark.slow` - Tests taking >5 seconds

## Coverage Reports

### Viewing Coverage
```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Open in browser
open htmlcov/index.html

# Terminal coverage report
pytest --cov=src --cov-report=term-missing
```

### Coverage Analysis
- **Green**: Well-tested code (>90%)
- **Yellow**: Adequately tested (80-90%)
- **Red**: Under-tested (<80%)

## Maintenance

### Regular Tasks
1. **Update fixtures** - Keep test data current with schema changes
2. **Review coverage** - Ensure new code has adequate tests
3. **Performance monitoring** - Watch for test suite slowdown
4. **Security updates** - Update security test payloads
5. **Dependency updates** - Keep test dependencies current

### Test Suite Health
- Monitor test execution time
- Review flaky tests
- Maintain high coverage
- Update documentation

---

This test suite provides comprehensive coverage while following enterprise-grade testing standards. All tests are designed for maintainability, reliability, and clear failure reporting.