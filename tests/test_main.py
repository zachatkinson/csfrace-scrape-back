"""Comprehensive tests for src.main CLI entry point."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.main import main, main_async, run_batch_processing, run_single_conversion


class TestMainAsync:
    """Test the main_async function."""

    @pytest.mark.asyncio
    async def test_main_async_single_url_mode(self):
        """Test main_async with single URL."""
        with patch("src.main.run_single_conversion", new_callable=AsyncMock) as mock_single:
            await main_async(url="https://example.com", output_dir="test_output", verbose=True)

            mock_single.assert_called_once_with("https://example.com", "test_output", None)

    @pytest.mark.asyncio
    async def test_main_async_batch_mode_comma_separated(self):
        """Test main_async with comma-separated URLs."""
        with patch("src.main.run_batch_processing", new_callable=AsyncMock) as mock_batch:
            await main_async(
                url="https://example.com,https://test.com", output_dir="test_output", batch_size=5
            )

            mock_batch.assert_called_once_with(
                url="https://example.com,https://test.com",
                urls_file=None,
                output_dir="test_output",
                batch_size=5,
                batch_config=None,
            )

    @pytest.mark.asyncio
    async def test_main_async_batch_mode_file(self):
        """Test main_async with URLs file."""
        with patch("src.main.run_batch_processing", new_callable=AsyncMock) as mock_batch:
            await main_async(urls_file="urls.txt", output_dir="batch_output", batch_size=10)

            mock_batch.assert_called_once_with(
                url=None,
                urls_file="urls.txt",
                output_dir="batch_output",
                batch_size=10,
                batch_config=None,
            )

    @pytest.mark.asyncio
    async def test_main_async_no_url_provided(self):
        """Test main_async with no URL exits with error."""
        with patch("src.main.console") as mock_console, pytest.raises(SystemExit) as exc_info:
            await main_async()

        mock_console.print.assert_called_with("[red]❌ No URL provided[/red]")
        assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_main_async_conversion_error(self):
        """Test main_async handles ConversionError."""
        from src.core.exceptions import ConversionError

        with (
            patch("src.main.run_single_conversion", new_callable=AsyncMock) as mock_single,
            patch("src.main.console") as mock_console,
        ):
            mock_single.side_effect = ConversionError("Test conversion error")

            with pytest.raises(ConversionError):
                await main_async(url="https://example.com")

            mock_console.print.assert_called_with(
                "❌ [red]Conversion failed: Test conversion error[/red]"
            )

    @pytest.mark.asyncio
    async def test_main_async_unexpected_error(self):
        """Test main_async handles unexpected errors."""
        with (
            patch("src.main.run_single_conversion", new_callable=AsyncMock) as mock_single,
            patch("src.main.console") as mock_console,
            patch("src.main.logger") as mock_logger,
        ):
            mock_single.side_effect = RuntimeError("Unexpected error")

            with pytest.raises(RuntimeError):
                await main_async(url="https://example.com")

            mock_logger.exception.assert_called_once_with(
                "Unexpected error during conversion", error="Unexpected error"
            )
            mock_console.print.assert_called_with(
                "💥 [red]Unexpected error: Unexpected error[/red]"
            )

    @pytest.mark.asyncio
    async def test_main_async_with_configs(self):
        """Test main_async with converter and batch configs."""
        mock_converter_config = MagicMock()
        mock_batch_config = MagicMock()

        with patch("src.main.run_single_conversion", new_callable=AsyncMock) as mock_single:
            await main_async(
                url="https://example.com",
                converter_config=mock_converter_config,
                batch_config=mock_batch_config,
            )

            mock_single.assert_called_once_with(
                "https://example.com", "converted_content", mock_converter_config
            )


class TestRunSingleConversion:
    """Test the run_single_conversion function."""

    @pytest.mark.asyncio
    async def test_run_single_conversion_success(self):
        """Test successful single URL conversion."""
        mock_converter = AsyncMock()

        with (
            patch("src.main.AsyncWordPressConverter") as mock_converter_class,
            patch("src.main.Progress") as mock_progress_class,
            patch("src.main.console") as mock_console,
        ):
            # Setup mocks
            mock_converter_class.return_value = mock_converter
            mock_progress = MagicMock()
            mock_task = MagicMock()
            mock_progress.add_task.return_value = mock_task
            mock_progress_class.return_value.__enter__.return_value = mock_progress

            await run_single_conversion("https://example.com", "test_output")

            # Verify converter creation
            mock_converter_class.assert_called_once_with(
                base_url="https://example.com", output_dir=Path("test_output"), config=None
            )

            # Verify conversion call
            mock_converter.convert.assert_called_once()

            # Verify progress tracking
            mock_progress.add_task.assert_called_once_with("Converting content...", total=100)

            # Verify success messages
            mock_console.print.assert_has_calls(
                [
                    call("✅ [green]Conversion completed successfully![/green]"),
                    call("📁 Output saved to: [bold]test_output[/bold]"),
                ]
            )

    @pytest.mark.asyncio
    async def test_run_single_conversion_with_config(self):
        """Test single conversion with custom config."""
        mock_converter = AsyncMock()
        mock_config = MagicMock()

        with (
            patch("src.main.AsyncWordPressConverter") as mock_converter_class,
            patch("src.main.Progress"),
            patch("src.main.console"),
        ):
            mock_converter_class.return_value = mock_converter

            await run_single_conversion("https://test.com", "custom_output", mock_config)

            mock_converter_class.assert_called_once_with(
                base_url="https://test.com", output_dir=Path("custom_output"), config=mock_config
            )

    @pytest.mark.asyncio
    async def test_run_single_conversion_progress_callback(self):
        """Test that progress callback works correctly."""
        mock_converter = AsyncMock()

        # Simulate progress callback being called
        def mock_convert(progress_callback):
            if progress_callback:
                progress_callback(50)  # Call with 50% progress

        mock_converter.convert.side_effect = mock_convert

        with (
            patch("src.main.AsyncWordPressConverter") as mock_converter_class,
            patch("src.main.Progress") as mock_progress_class,
            patch("src.main.console"),
        ):
            mock_progress = MagicMock()
            mock_task = "test_task"
            mock_progress.add_task.return_value = mock_task
            mock_progress_class.return_value.__enter__.return_value = mock_progress
            mock_converter_class.return_value = mock_converter

            await run_single_conversion("https://example.com", "test_output")

            # Verify progress was updated
            mock_progress.update.assert_called_once_with(mock_task, completed=50)


class TestRunBatchProcessing:
    """Test the run_batch_processing function."""

    @pytest.mark.asyncio
    async def test_run_batch_processing_with_file(self):
        """Test batch processing with URLs file."""
        mock_processor = MagicMock()
        mock_processor.jobs = [MagicMock(), MagicMock()]  # Simulate jobs
        mock_processor.add_jobs_from_file.return_value = 5
        mock_processor.process_all = AsyncMock(
            return_value={"successful": 4, "failed": 1, "total": 5}
        )

        with (
            patch("src.main.BatchProcessor") as mock_processor_class,
            patch("src.main.BatchConfig") as mock_config_class,
            patch("src.main.console") as mock_console,
        ):
            mock_processor_class.return_value = mock_processor
            mock_config = MagicMock()
            mock_config.output_base_dir = Path("batch_output")
            mock_config_class.return_value = mock_config

            await run_batch_processing(urls_file="test_urls.txt", output_dir="batch_output")

            # Verify configuration
            mock_config_class.assert_called_once_with(
                max_concurrent=3,
                output_base_dir=Path("batch_output"),
                create_summary=True,
                continue_on_error=True,
            )

            # Verify file loading
            mock_processor.add_jobs_from_file.assert_called_once_with("test_urls.txt")

            # Verify processing
            mock_processor.process_all.assert_called_once()

            # Verify console output
            mock_console.print.assert_has_calls(
                [
                    call("[bold blue]🚀 Starting Batch Processing[/bold blue]"),
                    call("📄 Loaded 5 URLs from [bold]test_urls.txt[/bold]"),
                    call("🎉 [green]Successfully processed 4 URLs![/green]"),
                    call("⚠️  [yellow]1 URLs failed processing[/yellow]"),
                    call("📊 Full summary saved to: [bold]batch_output/batch_summary.json[/bold]"),
                ]
            )

    @pytest.mark.asyncio
    async def test_run_batch_processing_with_comma_separated_urls(self):
        """Test batch processing with comma-separated URLs."""
        mock_processor = MagicMock()
        mock_processor.jobs = [MagicMock(), MagicMock(), MagicMock()]
        mock_processor.process_all = AsyncMock(
            return_value={"successful": 3, "failed": 0, "total": 3}
        )

        with (
            patch("src.main.BatchProcessor") as mock_processor_class,
            patch("src.main.BatchConfig") as mock_config_class,
            patch("src.main.console") as mock_console,
        ):
            mock_processor_class.return_value = mock_processor
            mock_config = MagicMock()
            mock_config.output_base_dir = Path("test_output")
            mock_config_class.return_value = mock_config

            await run_batch_processing(
                url="https://site1.com, https://site2.com,https://site3.com ", batch_size=5
            )

            # Verify URLs were added
            expected_urls = ["https://site1.com", "https://site2.com", "https://site3.com"]
            assert mock_processor.add_job.call_count == 3
            for expected_url in expected_urls:
                mock_processor.add_job.assert_any_call(expected_url)

            # Verify console output
            mock_console.print.assert_any_call("📝 Added 3 URLs from command line")
            mock_console.print.assert_any_call("🎉 [green]Successfully processed 3 URLs![/green]")

    @pytest.mark.asyncio
    async def test_run_batch_processing_no_jobs(self):
        """Test batch processing with no valid URLs."""
        mock_processor = MagicMock()
        mock_processor.jobs = []  # No jobs

        with (
            patch("src.main.BatchProcessor") as mock_processor_class,
            patch("src.main.BatchConfig"),
            patch("src.main.console") as mock_console,
        ):
            mock_processor_class.return_value = mock_processor

            await run_batch_processing(url="")

            mock_console.print.assert_any_call("[red]❌ No valid URLs found to process[/red]")
            mock_processor.process_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_batch_processing_with_custom_config(self):
        """Test batch processing with custom batch config."""
        mock_batch_config = MagicMock()
        mock_batch_config.output_base_dir = Path("custom_output")
        mock_processor = MagicMock()
        mock_processor.jobs = [MagicMock()]
        mock_processor.add_jobs_from_file.return_value = 1
        mock_processor.process_all = AsyncMock(
            return_value={"successful": 1, "failed": 0, "total": 1}
        )

        with patch("src.main.BatchProcessor") as mock_processor_class, patch("src.main.console"):
            mock_processor_class.return_value = mock_processor

            # Test with custom batch_config - should not create new BatchConfig
            await run_batch_processing(urls_file="test.txt", batch_config=mock_batch_config)

            # Should use provided config, not create new one
            mock_processor_class.assert_called_once_with(mock_batch_config)

    @pytest.mark.asyncio
    async def test_run_batch_processing_config_overrides(self):
        """Test batch processing with CLI parameter overrides."""
        mock_batch_config = MagicMock()
        mock_batch_config.max_concurrent = 3
        mock_batch_config.output_base_dir = Path("original")
        mock_processor = MagicMock()
        mock_processor.jobs = [MagicMock()]
        mock_processor.add_jobs_from_file.return_value = 1
        mock_processor.process_all = AsyncMock(return_value={"successful": 1, "failed": 0})

        with patch("src.main.BatchProcessor") as mock_processor_class, patch("src.main.console"):
            mock_processor_class.return_value = mock_processor

            # CLI overrides should modify the config
            await run_batch_processing(
                urls_file="test.txt",
                batch_size=10,  # Override default 3
                output_dir="cli_override",  # Override default
                batch_config=mock_batch_config,
            )

            # Verify config was modified
            assert mock_batch_config.max_concurrent == 10
            assert mock_batch_config.output_base_dir == Path("cli_override")


class TestMainCLI:
    """Test the main CLI execution flow without async complexity."""

    def test_main_with_single_url(self):
        """Test CLI execution with single URL."""
        test_args = ["prog", "https://example.com"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.asyncio.run") as mock_run,
        ):
            main()
            assert mock_run.called

    def test_main_with_output_directory(self):
        """Test CLI execution with output directory."""
        test_args = ["prog", "https://example.com", "-o", "custom_output"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.main_async", new_callable=lambda: MagicMock()) as mock_main_async,
            patch("src.main.asyncio.run") as mock_run,
        ):
            mock_main_async.return_value = "mock_coro"
            main()
            mock_run.assert_called_once_with("mock_coro")

    def test_main_with_config_generation(self):
        """Test config generation without async complexity."""
        test_args = ["prog", "--generate-config", "yaml"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.ConfigLoader") as mock_loader,
            patch("src.main.console") as mock_console,
            # Add asyncio.run mock to prevent any coroutine creation
            patch("src.main.asyncio.run") as mock_run,
        ):
            main()

            mock_loader.save_example_config.assert_called_once_with(
                "wp-shopify-config.yaml", "yaml"
            )
            # Config generation should exit early, not call asyncio.run
            mock_run.assert_not_called()

    def test_main_with_urls_file(self):
        """Test main function with URLs file."""
        test_args = ["prog", "--urls-file", "test_urls.txt", "--batch-size", "5"]

        # Create a mock coroutine that doesn't need awaiting
        mock_coro = MagicMock()

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.main_async", return_value=mock_coro) as mock_main_async,
            patch("src.main.asyncio.run") as mock_run,
        ):
            main()

            mock_main_async.assert_called_once_with(
                url=None,
                urls_file="test_urls.txt",
                output_dir="converted_content",
                batch_size=5,
                verbose=False,
                converter_config=None,
                batch_config=None,
            )

    def test_main_with_verbose_flag(self):
        """Test main function with verbose logging."""
        test_args = ["prog", "https://example.com", "-v"]

        # Create a mock coroutine that doesn't need awaiting
        mock_coro = MagicMock()

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.main_async", return_value=mock_coro) as mock_main_async,
            patch("src.main.asyncio.run") as mock_run,
        ):
            main()

            mock_main_async.assert_called_once_with(
                url="https://example.com",
                urls_file=None,
                output_dir="converted_content",
                batch_size=3,
                verbose=True,
                converter_config=None,
                batch_config=None,
            )

    def test_main_generate_yaml_config(self):
        """Test generating YAML config file."""
        test_args = ["prog", "--generate-config", "yaml"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.ConfigLoader") as mock_loader,
            patch("src.main.console") as mock_console,
        ):
            main()

            mock_loader.save_example_config.assert_called_once_with(
                "wp-shopify-config.yaml", "yaml"
            )
            mock_console.print.assert_has_calls(
                [
                    call("📄 Example config saved to: [bold]wp-shopify-config.yaml[/bold]"),
                    call("Edit this file and use with --config flag"),
                ]
            )

    def test_main_generate_json_config(self):
        """Test generating JSON config file."""
        test_args = ["prog", "--generate-config", "json"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.ConfigLoader") as mock_loader,
            patch("src.main.console") as mock_console,
        ):
            main()

            mock_loader.save_example_config.assert_called_once_with(
                "wp-shopify-config.json", "json"
            )

    def test_main_load_config_file_success(self):
        """Test loading config file successfully."""
        test_args = ["prog", "https://example.com", "--config", "test_config.yaml"]

        mock_converter_config = MagicMock()
        mock_batch_config = MagicMock()

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.load_config_from_file") as mock_load_config,
            patch("src.main.console") as mock_console,
            patch("src.main.asyncio.run") as mock_run,
        ):
            mock_load_config.return_value = (mock_converter_config, mock_batch_config)

            main()

            mock_load_config.assert_called_once_with("test_config.yaml")
            mock_console.print.assert_any_call(
                "📝 Loaded configuration from: [bold]test_config.yaml[/bold]"
            )
            # Just verify asyncio.run was called (config loading worked)
            mock_run.assert_called_once()

    def test_main_load_config_file_failure(self):
        """Test config file loading failure."""
        test_args = ["prog", "https://example.com", "--config", "invalid_config.yaml"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.load_config_from_file") as mock_load_config,
            patch("src.main.console") as mock_console,
            patch("src.main.main_async", new_callable=lambda: MagicMock()) as mock_main_async,
            patch("src.main.asyncio.run") as mock_run,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_load_config.side_effect = Exception("Config file not found")
            mock_main_async.return_value = "mock_coro"

            main()

            mock_console.print.assert_any_call(
                "❌ [red]Failed to load config: Config file not found[/red]"
            )
            assert exc_info.value.code == 1
            # Should not reach asyncio.run due to early exit on config error
            mock_run.assert_not_called()

    def test_main_interactive_mode_single_url(self):
        """Test interactive mode - single URL choice."""
        test_args = ["prog"]  # No URL provided

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.console") as mock_console,
            patch("src.main.asyncio.run") as mock_run,
        ):
            # Mock user input
            mock_console.input.side_effect = ["1", "https://interactive.com"]

            main()

            # Verify interactive prompts
            assert mock_console.input.call_count == 2
            mock_console.print.assert_any_call(
                "[bold blue]WordPress to Shopify Content Converter[/bold blue]"
            )
            # Just verify asyncio.run was called (interactive mode worked)
            mock_run.assert_called_once()

    def test_main_interactive_mode_multiple_urls(self):
        """Test interactive mode - multiple URLs choice."""
        test_args = ["prog"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.console") as mock_console,
            patch("src.main.asyncio.run") as mock_run,
        ):
            mock_console.input.side_effect = ["2", "https://site1.com,https://site2.com"]

            main()

            assert mock_console.input.call_count == 2
            # Just verify asyncio.run was called (multiple URL mode worked)
            mock_run.assert_called_once()

    def test_main_interactive_mode_batch_file(self):
        """Test interactive mode - batch file choice."""
        test_args = ["prog"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.console") as mock_console,
            patch("src.main.asyncio.run") as mock_run,
        ):
            mock_console.input.side_effect = ["3", "batch_urls.txt"]

            main()

            assert mock_console.input.call_count == 2
            # Just verify asyncio.run was called (batch file mode worked)
            mock_run.assert_called_once()

    def test_main_interactive_mode_invalid_choice(self):
        """Test interactive mode - invalid choice."""
        test_args = ["prog"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.console") as mock_console,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_console.input.return_value = "4"  # Invalid choice

            main()

            mock_console.print.assert_any_call("[yellow]Invalid choice. Exiting.[/yellow]")
            assert exc_info.value.code == 0

    def test_main_interactive_mode_no_url_provided(self):
        """Test interactive mode - no URL after prompt."""
        test_args = ["prog"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.console") as mock_console,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_console.input.side_effect = ["1", ""]  # Choose single URL but provide empty string

            main()

            mock_console.print.assert_any_call("[yellow]No URL or file provided. Exiting.[/yellow]")
            assert exc_info.value.code == 0

    def test_main_keyboard_interrupt(self):
        """Test main function handles KeyboardInterrupt."""
        test_args = ["prog", "https://example.com"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.asyncio.run") as mock_run,
            patch("src.main.console") as mock_console,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_run.side_effect = KeyboardInterrupt()

            main()

            mock_console.print.assert_called_with(
                "\n[yellow]Conversion interrupted by user[/yellow]"
            )
            assert exc_info.value.code == 130

    def test_main_conversion_error_exit_code(self):
        """Test main function exits with code 1 on ConversionError."""
        test_args = ["prog", "https://example.com"]

        from src.core.exceptions import ConversionError

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.asyncio.run") as mock_run,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_run.side_effect = ConversionError("Test error")

            main()

            assert exc_info.value.code == 1

    def test_main_unexpected_error_exit_code(self):
        """Test main function exits with code 1 on unexpected error."""
        test_args = ["prog", "https://example.com"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.asyncio.run") as mock_run,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_run.side_effect = RuntimeError("Unexpected error")

            main()

            assert exc_info.value.code == 1


class TestMainArgumentParsing:
    """Test specific argument parsing scenarios."""

    def test_mutually_exclusive_url_arguments(self):
        """Test that URL and urls-file are mutually exclusive."""
        test_args = ["prog", "https://example.com", "--urls-file", "test.txt"]

        with (
            patch.object(sys, "argv", test_args),
            pytest.raises(SystemExit),
        ):  # argparse should exit with error
            main()

    def test_batch_size_argument(self):
        """Test batch size argument parsing."""
        test_args = ["prog", "--urls-file", "test.txt", "--batch-size", "10"]

        # Create a mock coroutine that doesn't need awaiting
        mock_coro = MagicMock()

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.main_async", return_value=mock_coro) as mock_main_async,
            patch("src.main.asyncio.run") as mock_run,
        ):
            main()

            # Verify batch_size was passed correctly
            mock_main_async.assert_called_once_with(
                url=None,
                urls_file="test.txt",
                output_dir="converted_content",
                batch_size=10,
                verbose=False,
                converter_config=None,
                batch_config=None,
            )

    def test_config_file_argument(self):
        """Test config file argument."""
        test_args = ["prog", "https://example.com", "-c", "my_config.yaml"]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.load_config_from_file") as mock_load,
            patch("src.main.asyncio.run") as mock_run,
        ):
            mock_load.return_value = (None, None)

            main()

            mock_load.assert_called_once_with("my_config.yaml")
            # Just verify asyncio.run was called (config file loading worked)
            mock_run.assert_called_once()

    def test_help_argument(self):
        """Test help argument shows usage."""
        test_args = ["prog", "--help"]

        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            main()

        # Help should exit with code 0
        assert exc_info.value.code == 0


class TestMainEdgeCases:
    """Test edge cases and error conditions."""

    def test_main_empty_url_string(self):
        """Test main with empty URL string triggers interactive mode."""
        test_args = ["prog", ""]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.console") as mock_console,
            patch("src.main.asyncio.run") as mock_run,
        ):
            # Mock interactive mode - user selects single URL
            mock_console.input.side_effect = ["1", "https://interactive.com"]

            main()

            # Should still call asyncio.run after interactive input
            mock_run.assert_called_once()
            # Should show interactive prompts
            assert mock_console.input.call_count == 2

    def test_main_whitespace_only_url(self):
        """Test main with whitespace-only URL."""
        test_args = ["prog", "   "]

        with patch.object(sys, "argv", test_args), patch("src.main.asyncio.run") as mock_run:
            main()

            mock_run.assert_called_once()

    def test_main_with_all_optional_arguments(self):
        """Test main with all optional arguments."""
        test_args = [
            "prog",
            "https://example.com",
            "-o",
            "custom_output",
            "--batch-size",
            "7",
            "-c",
            "config.yaml",
            "-v",
        ]

        with (
            patch.object(sys, "argv", test_args),
            patch("src.main.load_config_from_file") as mock_load,
            patch("src.main.main_async", new_callable=lambda: MagicMock()) as mock_main_async,
            patch("src.main.asyncio.run") as mock_run,
        ):
            mock_load.return_value = (None, None)
            mock_main_async.return_value = "mock_coro"

            main()

            mock_run.assert_called_once_with("mock_coro")
            mock_load.assert_called_once_with("config.yaml")
