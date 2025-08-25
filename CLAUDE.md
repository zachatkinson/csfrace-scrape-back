# Claude Code Best Practices - WordPress to Shopify Converter

## Project Overview
This Python3 application converts WordPress blog content from the CSFrace website to Shopify-compatible HTML format. It handles various WordPress blocks, embeds, and formatting while ensuring the output is optimized for Shopify's content system.

## Python Development Standards

### 1. Code Style & Formatting
- **PEP 8 Compliance**: Follow PEP 8 style guide for Python code
- **Line Length**: Maximum 100 characters (relaxed from PEP 8's 79 for readability)
- **Indentation**: 4 spaces (no tabs)
- **Naming Conventions**:
  - Classes: `PascalCase` (e.g., `WordPressToShopifyConverter`)
  - Functions/Methods: `snake_case` (e.g., `convert_font_formatting`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_OUTPUT_DIR`)
  - Private methods: Leading underscore (e.g., `_internal_method`)

### 2. Type Hints
Implement type hints for better code clarity and IDE support:
```python
from typing import Dict, List, Optional, Tuple

def extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
    """Extract page metadata with type hints."""
    pass

def process_content(self, html_content: str) -> Tuple[Dict[str, str], str]:
    """Process content returning metadata and HTML."""
    pass
```

### 3. Error Handling
- Use specific exception types rather than bare `except:`
- Implement proper logging instead of print statements
- Provide meaningful error messages with context
- Consider creating custom exceptions for domain-specific errors

```python
import logging

logger = logging.getLogger(__name__)

try:
    response = self.session.get(url, timeout=10)
    response.raise_for_status()
except requests.Timeout:
    logger.error(f"Timeout fetching URL: {url}")
    raise
except requests.HTTPError as e:
    logger.error(f"HTTP error {e.response.status_code} for URL: {url}")
    raise
```

### 4. Documentation Standards
- **Docstrings**: Use Google or NumPy style docstrings for all public methods
- **Module docstrings**: Include at the top of each file
- **Inline comments**: Use sparingly, code should be self-documenting
- **Type annotations**: Prefer over docstring type descriptions

```python
def convert_content(self, html: str, options: Dict[str, Any]) -> str:
    """Convert WordPress HTML to Shopify format.
    
    Args:
        html: Raw HTML content from WordPress
        options: Conversion options dictionary
        
    Returns:
        Converted HTML string ready for Shopify
        
    Raises:
        ConversionError: If content cannot be converted
    """
```

### 5. Testing Requirements
- Create unit tests using `pytest` framework
- Aim for >80% code coverage
- Test edge cases and error conditions
- Mock external dependencies (requests, file I/O)

Test file structure:
```
tests/
├── __init__.py
├── test_converter.py
├── test_metadata.py
├── fixtures/
│   └── sample_content.html
└── conftest.py
```

### 6. Security Considerations
- **Input Validation**: Always validate and sanitize URLs
- **HTML Sanitization**: Be cautious with user-provided HTML
- **Request Headers**: Use appropriate User-Agent strings
- **Rate Limiting**: Implement delays between requests
- **Secrets Management**: Never hardcode credentials
- **Path Traversal**: Validate file paths when saving content

### 7. Performance Optimizations
- **Session Reuse**: Use requests.Session() for connection pooling
- **Lazy Loading**: Load large resources only when needed
- **Batch Processing**: Process multiple items efficiently
- **Caching**: Consider caching frequently accessed data
- **Async Operations**: Use `asyncio` for concurrent downloads

### 8. Configuration Management
Consider implementing a configuration system:
```python
# config.py
from dataclasses import dataclass

@dataclass
class ConverterConfig:
    output_dir: str = "converted_content"
    download_images: bool = True
    request_timeout: int = 10
    rate_limit_delay: float = 0.5
    user_agent: str = "Mozilla/5.0..."
```

### 9. Logging Best Practices
```python
import logging
from pathlib import Path

def setup_logging(log_level=logging.INFO):
    """Configure logging for the application."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # File handler
    file_handler = logging.FileHandler("converter.log")
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Root logger configuration
    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler]
    )
```

### 10. CLI Enhancement Suggestions
- Add `--verbose` flag for detailed output
- Implement `--dry-run` mode to preview without downloading
- Support `--config` flag for configuration files
- Add `--batch` mode for processing multiple URLs from a file
- Include `--no-images` flag to skip image downloads
- Provide `--format` option for output formats (HTML, Markdown)

### 11. Project Structure Recommendations
```
csfrace-scrape/
├── src/
│   ├── __init__.py
│   ├── converter.py      # Main converter class
│   ├── parsers.py        # Content parsing logic
│   ├── formatters.py     # Output formatting
│   ├── utils.py          # Utility functions
│   └── config.py         # Configuration
├── tests/
│   └── ...
├── docs/
│   └── examples.md
├── requirements.txt
├── requirements-dev.txt   # Development dependencies
├── setup.py              # For package installation
├── README.md
├── CLAUDE.md
├── .gitignore
└── main.py               # CLI entry point
```

### 12. Dependencies Management
- Pin exact versions in `requirements.txt` for production
- Use `requirements-dev.txt` for development dependencies
- Consider using `pipenv` or `poetry` for dependency management
- Regular security updates with `pip-audit`

### 13. Git Workflow
- Use meaningful commit messages
- Follow conventional commits format
- Create feature branches for new functionality
- Use `.gitignore` to exclude:
  - `__pycache__/`
  - `*.pyc`
  - `.env`
  - `converted_content/`
  - `*.log`

### 14. Running Commands
When working with this project, use these commands:
```bash
# Install dependencies
pip3 install -r requirements.txt

# Run the converter
python3 main.py <wordpress-url>

# Run with custom output directory
python3 main.py <wordpress-url> -o custom_output

# Run tests (when implemented)
pytest tests/

# Check code style
flake8 src/ tests/

# Format code
black src/ tests/
```

## Future Enhancements to Consider
1. **Async/Await**: Convert to async for better performance with multiple URLs
2. **Plugin System**: Make conversion rules pluggable
3. **API Mode**: Add REST API endpoint for web service deployment
4. **Database Support**: Store conversion history and metadata
5. **Shopify API Integration**: Direct upload to Shopify instead of manual copy
6. **Content Validation**: Verify converted content meets Shopify requirements
7. **Rollback Mechanism**: Allow undoing conversions
8. **Progress Tracking**: Add progress bars for long operations
9. **Notification System**: Email/webhook notifications on completion
10. **Docker Support**: Containerize for easy deployment

## Quality Checklist
Before committing code, ensure:
- [ ] Code follows PEP 8 style guide
- [ ] All functions have docstrings
- [ ] Type hints are implemented
- [ ] Error handling is comprehensive
- [ ] Tests are written and passing
- [ ] No hardcoded values or credentials
- [ ] Logging is used instead of print statements
- [ ] Code is DRY (Don't Repeat Yourself)
- [ ] Complex logic is well-commented
- [ ] README is updated if functionality changes