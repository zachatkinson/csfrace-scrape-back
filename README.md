# WordPress to Shopify Content Converter

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/zachatkinson/csfrace-scrape/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/zachatkinson/csfrace-scrape/actions)
[![codecov](https://codecov.io/gh/zachatkinson/csfrace-scrape/branch/master/graph/badge.svg)](https://codecov.io/gh/zachatkinson/csfrace-scrape)

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Docker](https://img.shields.io/badge/docker-supported-blue?logo=docker)](https://github.com/zachatkinson/csfrace-scrape/blob/master/Dockerfile)
[![Async](https://img.shields.io/badge/async-aiohttp-blue.svg)](https://docs.aiohttp.org/)

A modern Python command-line tool that converts WordPress blog content to Shopify-compatible HTML format. Specifically designed for CSFrace website content migration, this tool handles various WordPress blocks, embeds, and formatting while ensuring the output is optimized for Shopify's content management system.

## Features

### Content Conversion Capabilities
- **Font Formatting**: Converts `<b>` to `<strong>` and `<i>` to `<em>` tags
- **Text Alignment**: Transforms WordPress alignment classes to Shopify-compatible formats
- **Kadence Blocks Support**:
  - Row layouts → Media grid layouts (2, 3, 4, or 5 columns)
  - Advanced galleries → Media grid galleries
  - Advanced buttons → Shopify button styles with full-width support
- **Image Handling**:
  - Downloads all images locally for backup
  - Simplifies WordPress image blocks to clean `<img>` tags
  - Preserves alt text and captions
- **Media Embeds**:
  - YouTube videos with responsive 16:9 aspect ratio
  - Instagram embeds with proper container structure
- **Blockquotes**: Converts WordPress pullquotes to testimonial-style quotes
- **External Links**: Automatically adds `target="_blank"` and `rel="noreferrer noopener"` to external links
- **Metadata Extraction**:
  - Page title
  - URL and slug
  - Meta description
  - Published date

### Clean Output
- Removes WordPress-specific classes and inline styles
- Strips out script tags
- Preserves only Shopify-relevant classes
- Generates clean, semantic HTML ready for Shopify

## Installation

### Prerequisites
- Python 3.9 or higher (3.11+ recommended)
- Git (for cloning the repository)

### Install Dependencies
```bash
# Clone the repository (if applicable)
git clone https://github.com/zachatkinson/csfrace-scrape.git
cd csfrace-scrape

# Basic installation (core dependencies only)
python -m pip install -r requirements.txt

# OR install with development tools (recommended for contributors)
python -m pip install -e .[dev,test]

# OR production installation with monitoring
python -m pip install -r requirements/prod.txt
```

### Core Dependencies
- `aiohttp` - Async HTTP client for concurrent requests
- `httpx` - Modern HTTP client with async support
- `beautifulsoup4` - HTML parsing and manipulation
- `lxml` - Fast XML/HTML parser
- `bleach` - HTML sanitization for security
- `pydantic` - Data validation using Python type annotations
- `click` - Command-line interface framework
- `rich` - Rich text and beautiful formatting
- `structlog` - Structured logging
- `tenacity` - Retry library with exponential backoff
- `PyYAML` - YAML configuration file support

## Usage

### Basic Usage
```bash
python main.py <wordpress-url>
```

### Specify Output Directory
```bash
python main.py <wordpress-url> -o <output-directory>
```

### Examples
```bash
# Convert a single blog post
python main.py https://csfrace.com/blog/sample-post

# Convert and save to custom directory
python main.py https://csfrace.com/blog/sample-post -o my-conversions

# URL without protocol (https:// will be added automatically)
python main.py csfrace.com/blog/sample-post
```

### Interactive Mode
If you run the script without arguments, it will prompt for a URL:
```bash
python main.py
# Enter WordPress URL to convert: csfrace.com/blog/sample-post
```

## Output Structure

The converter creates an output directory (default: `converted_content/`) with the following structure:

```
converted_content/
├── metadata.txt              # Extracted page metadata
├── converted_content.html    # Converted HTML only
├── shopify_ready_content.html # Combined metadata + HTML (ready to paste)
└── images/                   # Downloaded images
    ├── image1.jpg
    ├── image2.png
    └── ...
```

### Output Files Description

1. **metadata.txt**: Plain text file containing:
   - Page title
   - Original URL
   - URL slug
   - Meta description
   - Published date

2. **converted_content.html**: Clean HTML content without metadata, ready for Shopify's HTML editor

3. **shopify_ready_content.html**: Complete file with HTML comments containing metadata and the converted content - perfect for copy/paste into Shopify

4. **images/**: Local copies of all images found in the content

## Conversion Rules

### HTML Element Mappings
| WordPress Element | Shopify Output |
|------------------|----------------|
| `<b>` | `<strong>` |
| `<i>` | `<em>` |
| `.has-text-align-center` | `.center` |
| `.wp-block-kadence-rowlayout` | `.media-grid-*` |
| `.wp-block-kadence-advancedgallery` | `.media-grid` |
| `.wp-block-kadence-advancedbtn` | `.button.button--full-width.button--primary` |
| `.wp-block-pullquote` | `.testimonial-quote` |
| `.wp-block-embed-youtube` | Responsive iframe container |

### Special Handling
- **External Links**: Links not pointing to csfrace.com automatically open in new tabs
- **Images**: All images are downloaded locally with proper naming
- **Scripts**: All script tags are removed for security
- **Styles**: Inline styles are removed except for specific media embeds

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `url` | WordPress URL to convert (required) | - |
| `-o, --output` | Output directory for converted files | `converted_content` |
| `-h, --help` | Show help message and exit | - |

## Troubleshooting

### Common Issues

1. **"No entry-content div found"**
   - The script will attempt to process the entire body content
   - Check if the WordPress site structure is standard

2. **Images not downloading**
   - Check internet connection
   - Verify the images are publicly accessible
   - Some sites may block automated downloads

3. **Timeout errors**
   - The script has a 10-second timeout for requests
   - Try again or check if the site is accessible

4. **Encoding issues**
   - Ensure your terminal supports UTF-8
   - Output files are saved with UTF-8 encoding

### Debug Tips
- Check the console output for specific error messages
- Verify the URL is correct and accessible
- Ensure you have write permissions in the output directory
- Review `converted_content.html` to see the raw conversion result

## Best Practices

1. **Review Output**: Always review the converted content before pasting into Shopify
2. **Image Optimization**: Consider optimizing downloaded images before uploading to Shopify
3. **SEO Preservation**: Check that metadata is correctly transferred
4. **Test Links**: Verify all links work correctly after conversion
5. **Backup Original**: Keep the original WordPress content as backup

## Limitations

- Requires the WordPress site to be publicly accessible
- Complex custom WordPress blocks may not convert perfectly
- JavaScript-dependent content won't be captured
- Some WordPress plugins' output may not be recognized
- Rate limiting: 0.5 second delay between image downloads to be respectful to servers

## Contributing

See [CLAUDE.md](CLAUDE.md) for development best practices and coding standards.

### Development Setup
```bash
# Install development dependencies (when available)
pip3 install -r requirements-dev.txt

# Run tests (when implemented)
pytest tests/

# Check code style (when configured)
flake8 src/
```

## Future Enhancements

- Batch processing of multiple URLs
- Configuration file support
- Progress indicators for large conversions
- Dry-run mode to preview without downloading
- Direct Shopify API integration
- Support for additional WordPress page builders
- Markdown output format option
- GUI version for non-technical users

## License

[Specify your license here]

## Support

For issues, questions, or suggestions, please [create an issue](link-to-issues) or contact the maintainers.

## Acknowledgments

Built specifically for migrating CSFrace WordPress content to Shopify, handling their specific use of Kadence blocks and custom formatting requirements.