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
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .core.converter import AsyncWordPressConverter
from .core.exceptions import ConversionError
from .utils.logging import setup_logging


console = Console()
logger = structlog.get_logger()


async def main_async(url: str, output_dir: str, verbose: bool = False) -> None:
    """Main async conversion function."""
    setup_logging(verbose=verbose)
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            # Create converter
            converter = AsyncWordPressConverter(
                base_url=url,
                output_dir=Path(output_dir)
            )
            
            # Run conversion with progress tracking
            task = progress.add_task("Converting content...", total=100)
            
            await converter.convert(progress_callback=lambda p: progress.update(task, completed=p))
            
        console.print("✅ [green]Conversion completed successfully![/green]")
        console.print(f"📁 Output saved to: [bold]{output_dir}[/bold]")
        
    except ConversionError as e:
        console.print(f"❌ [red]Conversion failed: {e}[/red]")
        raise
    except Exception as e:
        logger.exception("Unexpected error during conversion", error=str(e))
        console.print(f"💥 [red]Unexpected error: {e}[/red]")
        raise


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert WordPress content to Shopify-friendly format (Async)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://csfrace.com/blog/sample-post
  %(prog)s https://csfrace.com/blog/sample-post -o my-output
  %(prog)s csfrace.com/blog/sample-post --verbose
        """
    )
    
    parser.add_argument(
        "url",
        nargs="?",
        help="WordPress URL to convert"
    )
    parser.add_argument(
        "-o", "--output",
        default="converted_content",
        help="Output directory (default: %(default)s)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Interactive mode if no URL provided
    if not args.url:
        console.print("[bold blue]WordPress to Shopify Content Converter[/bold blue]")
        console.print("-" * 40)
        args.url = console.input("Enter WordPress URL to convert: ").strip()
        
        if not args.url:
            console.print("[yellow]No URL provided. Exiting.[/yellow]")
            sys.exit(0)
    
    try:
        # Run async main
        asyncio.run(main_async(args.url, args.output, args.verbose))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Conversion interrupted by user[/yellow]")
        sys.exit(130)
    except (ConversionError, Exception):
        sys.exit(1)


if __name__ == "__main__":
    main()