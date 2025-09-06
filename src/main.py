#!/usr/bin/env python3
"""
WordPress to Shopify Content Converter - Main Entry Point

Modern async implementation with aiohttp for concurrent processing.

Author: CSFrace Development Team
License: MIT
"""

import argparse
import asyncio
import sys
from pathlib import Path

import structlog
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from .batch.processor import BatchConfig, BatchProcessor
from .config.loader import ConfigLoader, load_config_from_file
from .constants import CLI_CONSTANTS
from .core.converter import AsyncWordPressConverter
from .core.exceptions import ConversionError
from .utils.logging import setup_logging

console = Console()
logger = structlog.get_logger()


# pylint: disable=too-many-arguments,too-many-positional-arguments
async def main_async(
    url: str | None = None,
    urls_file: str | None = None,
    output_dir: str = "converted_content",
    batch_size: int = 3,
    verbose: bool = False,
    converter_config=None,
    batch_config=None,
) -> None:
    """Main async conversion function with batch support."""
    setup_logging(verbose=verbose)

    try:
        # Batch processing mode
        if urls_file or (url and "," in url):
            await run_batch_processing(
                url=url,
                urls_file=urls_file,
                output_dir=output_dir,
                batch_size=batch_size,
                batch_config=batch_config,
            )
        # Single URL mode
        elif url:
            await run_single_conversion(url, output_dir, converter_config)
        else:
            console.print("[red]❌ No URL provided[/red]")
            sys.exit(1)

    except ConversionError as e:
        console.print(f"❌ [red]Conversion failed: {e}[/red]")
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error during conversion", error=str(e))
        console.print(f"💥 [red]Unexpected error: {e}[/red]")
        raise


async def run_single_conversion(url: str, output_dir: str, converter_config=None) -> None:
    """Run single URL conversion with progress tracking."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        # Create converter
        converter = AsyncWordPressConverter(
            base_url=url, output_dir=Path(output_dir), config=converter_config
        )

        # Run conversion with progress tracking
        task = progress.add_task("Converting content...", total=100)

        await converter.convert(progress_callback=lambda p: progress.update(task, completed=p))

    console.print("✅ [green]Conversion completed successfully![/green]")
    console.print(f"📁 Output saved to: [bold]{output_dir}[/bold]")


async def run_batch_processing(
    url: str | None = None,
    urls_file: str | None = None,
    output_dir: str = "converted_content",
    batch_size: int = 3,
    batch_config=None,
) -> None:
    """Run batch processing for multiple URLs."""
    console.print("[bold blue]🚀 Starting Batch Processing[/bold blue]")

    # Configure batch processor
    if not batch_config:
        batch_config = BatchConfig(
            max_concurrent=batch_size,
            output_base_dir=Path(output_dir),
            create_summary=True,
            continue_on_error=True,
        )
    else:
        # Override CLI arguments with config values where applicable
        if batch_size != 3:  # CLI override
            batch_config.max_concurrent = batch_size
        if output_dir != "converted_content":  # CLI override
            batch_config.output_base_dir = Path(output_dir)

    processor = BatchProcessor(batch_config)

    # Add jobs from different sources
    if urls_file:
        # Load from file
        jobs_added = processor.add_jobs_from_file(urls_file)
        console.print(f"📄 Loaded {jobs_added} URLs from [bold]{urls_file}[/bold]")
    elif url and "," in url:
        # Comma-separated URLs
        urls = [u.strip() for u in url.split(",") if u.strip()]
        for u in urls:
            processor.add_job(u)
        console.print(f"📝 Added {len(urls)} URLs from command line")

    if not processor.jobs:
        console.print("[red]❌ No valid URLs found to process[/red]")
        return

    # Process all jobs
    summary = await processor.process_all()

    # Final summary
    if summary["successful"] > 0:
        console.print(f"🎉 [green]Successfully processed {summary['successful']} URLs![/green]")
    if summary["failed"] > 0:
        console.print(f"⚠️  [yellow]{summary['failed']} URLs failed processing[/yellow]")

    console.print(
        f"📊 Full summary saved to: [bold]{batch_config.output_base_dir}/batch_summary.json[/bold]"
    )


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert WordPress content to Shopify-friendly format (Async)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Single URL:
    %(prog)s {CLI_CONSTANTS.EXAMPLE_CSFRACE_URL}
    %(prog)s {CLI_CONSTANTS.EXAMPLE_CSFRACE_URL} -o my-output

  Multiple URLs (comma-separated):
    %(prog)s "{CLI_CONSTANTS.EXAMPLE_SITE_URL}/post1,{CLI_CONSTANTS.EXAMPLE_SITE_URL}/post2" --batch-size 5

  Batch from file:
    %(prog)s --urls-file urls.txt --batch-size 3 -o batch_output
        """,
    )

    # URL arguments (mutually exclusive groups)
    url_group = parser.add_mutually_exclusive_group()
    url_group.add_argument(
        "url", nargs="?", help="WordPress URL(s) to convert (comma-separated for multiple)"
    )
    url_group.add_argument("--urls-file", help="File containing URLs to process (one per line)")

    # Output options
    parser.add_argument(
        "-o",
        "--output",
        default="converted_content",
        help="Output directory (default: %(default)s)",
    )

    # Batch processing options
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Maximum concurrent conversions for batch processing (default: %(default)d)",
    )

    # Configuration options
    parser.add_argument("-c", "--config", help="Configuration file (YAML or JSON)")
    parser.add_argument(
        "--generate-config",
        choices=["yaml", "json"],
        help="Generate example configuration file and exit",
    )

    # Logging options
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Handle config generation
    if args.generate_config:
        config_filename = f"wp-shopify-config.{args.generate_config}"
        ConfigLoader.save_example_config(config_filename, args.generate_config)
        console.print(f"📄 Example config saved to: [bold]{config_filename}[/bold]")
        console.print("Edit this file and use with --config flag")
        return

    # Load configuration if provided
    converter_config = None
    batch_config = None

    if args.config:
        try:
            converter_config, batch_config = load_config_from_file(args.config)
            console.print(f"📝 Loaded configuration from: [bold]{args.config}[/bold]")
        except Exception as e:  # pylint: disable=broad-exception-caught
            console.print(f"❌ [red]Failed to load config: {e}[/red]")
            sys.exit(1)

    # Interactive mode if no URL or file provided
    if not args.url and not args.urls_file:
        console.print("[bold blue]WordPress to Shopify Content Converter[/bold blue]")
        console.print(CLI_CONSTANTS.PROGRESS_SEPARATOR)

        mode = console.input(
            "Choose mode:\n"
            "  1. Single URL\n"
            "  2. Multiple URLs (comma-separated)\n"
            "  3. Batch from file\n"
            "Enter choice (1-3): "
        ).strip()

        if mode == "1":
            args.url = console.input("Enter WordPress URL to convert: ").strip()
        elif mode == "2":
            args.url = console.input("Enter URLs (comma-separated): ").strip()
        elif mode == "3":
            args.urls_file = console.input("Enter path to URLs file: ").strip()
        else:
            console.print("[yellow]Invalid choice. Exiting.[/yellow]")
            sys.exit(0)

        if not args.url and not args.urls_file:
            console.print("[yellow]No URL or file provided. Exiting.[/yellow]")
            sys.exit(0)

    try:
        # Run async main
        asyncio.run(
            main_async(
                url=args.url,
                urls_file=args.urls_file,
                output_dir=args.output,
                batch_size=args.batch_size,
                verbose=args.verbose,
                converter_config=converter_config,
                batch_config=batch_config,
            )
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Conversion interrupted by user[/yellow]")
        sys.exit(CLI_CONSTANTS.EXIT_CODE_KEYBOARD_INTERRUPT)
    except (ConversionError, Exception):
        sys.exit(1)


if __name__ == "__main__":
    main()
