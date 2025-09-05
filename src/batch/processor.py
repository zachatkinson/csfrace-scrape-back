"""Batch processing for multiple URLs with concurrent execution."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn
from rich.table import Table

from ..constants import CONSTANTS
from ..core.converter import AsyncWordPressConverter
from ..utils.path_utils import (
    safe_filename,
    truncate_path_component,
)

logger = structlog.get_logger(__name__)


class JobSummaryData(TypedDict):
    """Type definition for individual job summary data."""

    url: str
    status: str
    output_dir: str
    duration: float | None
    error: str | None


class BatchSummary(TypedDict):
    """Type definition for batch processing summary."""

    total: int
    successful: int
    failed: int
    skipped: int
    jobs: list[JobSummaryData]
    total_duration: float
    average_duration: float


console = Console()


class BatchJobStatus(Enum):
    """Status of a batch job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BatchJob:
    """Individual job in a batch processing operation."""

    url: str
    output_dir: Path
    status: BatchJobStatus = BatchJobStatus.PENDING
    error: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    progress_task: TaskID | None = None
    archive_path: Path | None = None

    @property
    def duration(self) -> float | None:
        """Calculate job duration if completed."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


@dataclass
class BatchConfig:
    """Configuration for batch processing operations."""

    max_concurrent: int = 3
    continue_on_error: bool = True
    output_base_dir: Path = Path("batch_output")
    create_summary: bool = True
    skip_existing: bool = False
    timeout_per_job: int = 300  # 5 minutes per job
    retry_failed: bool = True
    max_retries: int = 2
    create_archives: bool = False  # Create ZIP archives for each job
    archive_format: str = "zip"  # zip, tar, tar.gz
    cleanup_after_archive: bool = False  # Remove directories after zipping


class BatchProcessor:
    """Processes multiple WordPress URLs concurrently."""

    def __init__(self, batch_config: BatchConfig | None = None):
        """Initialize batch processor.

        Args:
            batch_config: Configuration for batch processing
        """
        self.config = batch_config or BatchConfig()
        self.jobs: list[BatchJob] = []
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self.results: dict[str, Any] = {}

        logger.info(
            "Initialized batch processor",
            max_concurrent=self.config.max_concurrent,
            continue_on_error=self.config.continue_on_error,
        )

    def add_job(
        self, url: str, output_dir: Path | None = None, custom_slug: str | None = None
    ) -> BatchJob:
        """Add a job to the batch processing queue with intelligent directory naming.

        BEST PRACTICES IMPLEMENTED:
        1. **Slug-based Organization**: Uses actual WordPress post slug when possible
        2. **Domain Separation**: Groups posts by domain for multi-site batches
        3. **Collision Avoidance**: Handles duplicate slugs with numbering
        4. **Length Limits**: Prevents filesystem path length issues
        5. **Cross-platform**: Safe characters for Windows/Linux/Mac

        Directory structure:
        batch_output/
        ├── csfrace-com_my-blog-post/          # domain_slug format
        │   ├── metadata.txt                   # Post metadata
        │   ├── converted_content.html         # Clean HTML
        │   ├── shopify_ready_content.html     # With metadata comments
        │   └── images/                        # Post-specific images
        │       ├── featured-image.jpg         # Organized by post
        │       └── inline-image.png
        └── csfrace-com_my-blog-post-2/        # Handle duplicates
            └── ...

        Args:
            url: WordPress URL to convert
            output_dir: Optional specific output directory (overrides slug generation)
            custom_slug: Optional custom slug to use instead of URL-derived

        Returns:
            Created BatchJob instance

        Raises:
            ValueError: If URL is invalid or slug generation fails
        """
        if output_dir is None:
            output_dir = self._generate_output_directory(url, custom_slug)

        # Ensure no duplicate output directories
        output_dir = self._ensure_unique_directory(output_dir)

        job = BatchJob(url=url, output_dir=output_dir)
        self.jobs.append(job)

        logger.debug("Added batch job", url=url, output_dir=str(output_dir))
        return job

    def _generate_output_directory(self, url: str, custom_slug: str | None = None) -> Path:
        """Generate intelligent output directory from URL or custom slug.

        Args:
            url: WordPress URL
            custom_slug: Optional custom slug override

        Returns:
            Generated output directory path
        """
        import re
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                raise ValueError(f"Invalid URL: {url}")

            # Clean domain for filesystem
            domain = parsed.netloc.lower()
            domain = re.sub(r"^www\.", "", domain)  # Remove www prefix
            domain = safe_filename(domain, replacement="-", include_dots=True)

            if custom_slug:
                slug = custom_slug
            else:
                # Extract slug from URL path
                path_parts = [p for p in parsed.path.strip("/").split("/") if p]
                if path_parts:
                    # Use last part as slug (WordPress convention)
                    slug = path_parts[-1]
                    # Remove common WordPress artifacts
                    slug = re.sub(r"\.(html|php)$", "", slug)  # Remove extensions
                    slug = re.sub(r"^index$", "homepage", slug)  # Handle index pages
                else:
                    slug = "homepage"

            # Clean slug for filesystem and truncate
            slug = safe_filename(slug)
            slug = truncate_path_component(slug, 50)

            if not slug:  # Fallback if slug is empty after cleaning
                slug = "post"

            # Combine domain and slug
            safe_name = f"{domain}_{slug}"
            return self.config.output_base_dir / safe_name

        except Exception as e:
            logger.warning("Failed to generate directory from URL", url=url, error=str(e))
            # Fallback to hash-based naming
            import hashlib

            url_hash = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:8]
            return self.config.output_base_dir / f"post_{url_hash}"

    def _ensure_unique_directory(self, base_dir: Path) -> Path:
        """Ensure directory name is unique by adding numbering if needed.

        Args:
            base_dir: Base directory path

        Returns:
            Unique directory path
        """
        if not any(job.output_dir == base_dir for job in self.jobs):
            return base_dir

        # Find next available number
        counter = 2
        while True:
            numbered_dir = Path(str(base_dir) + f"-{counter}")
            if not any(job.output_dir == numbered_dir for job in self.jobs):
                return numbered_dir
            counter += 1

    def add_jobs_from_file(self, file_path: str | Path) -> int:
        """Add jobs from a file containing URLs.

        Supports multiple formats:
        1. **Plain text** (.txt): One URL per line, comments with #
        2. **CSV format** (.csv): Structured data with headers

        CSV Format:
        ```csv
        url,slug,output_dir,priority
        https://site.com/post1,custom-slug-1,,high
        https://site.com/post2,,,normal
        # This is a comment
        https://site.com/post3,special-post,/custom/path,low
        ```

        CSV Columns (all optional except url):
        - url: WordPress URL (required)
        - slug: Custom slug override
        - output_dir: Custom output directory
        - priority: Job priority (unused currently)

        Args:
            file_path: Path to file (.txt or .csv)

        Returns:
            Number of jobs added

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If CSV format is invalid
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Jobs file not found: {file_path}")

        # Determine file format
        if file_path.suffix.lower() == ".csv":
            return self._add_jobs_from_csv(file_path)
        else:
            return self._add_jobs_from_txt(file_path)

    def _add_jobs_from_txt(self, file_path: Path) -> int:
        """Add jobs from plain text file (one URL per line).

        Args:
            file_path: Path to text file

        Returns:
            Number of jobs added
        """
        added = 0
        with open(file_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                url = line.strip()
                if url and not url.startswith("#"):  # Skip empty lines and comments
                    try:
                        self.add_job(url)
                        added += 1
                    except Exception as e:
                        logger.warning(
                            "Skipped invalid URL",
                            file_path=str(file_path),
                            line_num=line_num,
                            url=url,
                            error=str(e),
                        )

        logger.info("Loaded jobs from text file", file_path=str(file_path), jobs_added=added)
        return added

    def _add_jobs_from_csv(self, file_path: Path) -> int:
        """Add jobs from CSV file with structured data or simple URL list.

        Supports two formats:
        1. Simple URL list (one URL per line, comma-separated or not)
        2. Structured CSV with columns: url, slug, output_dir, priority

        Args:
            file_path: Path to CSV file

        Returns:
            Number of jobs added
        """

        added = 0
        try:
            with open(file_path, encoding="utf-8") as f:
                # Read first line to detect format
                first_line = f.readline().strip()
                f.seek(0)

                # Check if it looks like a header (contains 'url' column)
                if "url" in first_line.lower() and ("," in first_line or "\t" in first_line):
                    # Structured CSV format
                    added = self._process_structured_csv(f)
                else:
                    # Simple URL list format
                    added = self._process_simple_csv(f)

        except Exception as e:
            logger.error("Failed to parse CSV file", file_path=str(file_path), error=str(e))
            raise ValueError(f"Invalid CSV format in {file_path}: {e}")

        logger.info("Loaded jobs from CSV file", file_path=str(file_path), jobs_added=added)
        return added

    def _process_structured_csv(self, file_handle) -> int:
        """Process structured CSV with columns."""
        import csv

        added = 0
        from ..constants import CONSTANTS

        # Detect delimiter
        sample = file_handle.read(CONSTANTS.FILE_READ_BUFFER_SIZE)
        file_handle.seek(0)
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample).delimiter

        reader = csv.DictReader(file_handle, delimiter=delimiter)

        for row_num, row in enumerate(reader, 2):  # Start at 2 (header is row 1)
            # Skip comment rows
            if row.get("url", "").strip().startswith("#"):
                continue

            url = row.get("url", "").strip()
            if not url:
                continue

            try:
                # Extract optional fields
                custom_slug = row.get("slug", "").strip() or None
                custom_output = row.get("output_dir", "").strip() or None

                if custom_output:
                    custom_output = Path(custom_output)

                self.add_job(url=url, output_dir=custom_output, custom_slug=custom_slug)
                added += 1

                logger.debug(
                    "Added structured CSV job",
                    row_num=row_num,
                    url=url,
                    slug=custom_slug,
                    output_dir=custom_output,
                )

            except Exception as e:
                logger.warning("Skipped invalid CSV row", row_num=row_num, url=url, error=str(e))

        return added

    def _process_simple_csv(self, file_handle) -> int:
        """Process simple CSV/list of URLs."""
        import csv

        added = 0
        file_handle.seek(0)

        # Try to detect if it's comma-separated or line-separated
        content = file_handle.read()
        file_handle.seek(0)

        if "," in content and content.count(",") > content.count("\n"):
            # Comma-separated URLs
            reader = csv.reader(file_handle)
            for row_num, row in enumerate(reader, 1):
                for url in row:
                    url = url.strip()
                    if url and not url.startswith("#"):
                        try:
                            self.add_job(url)
                            added += 1
                            logger.debug("Added simple CSV job", row_num=row_num, url=url)
                        except Exception as e:
                            logger.warning(
                                "Skipped invalid URL", row_num=row_num, url=url, error=str(e)
                            )
        else:
            # Line-separated URLs
            for line_num, line in enumerate(file_handle, 1):
                url = line.strip()
                if url and not url.startswith("#"):
                    try:
                        self.add_job(url)
                        added += 1
                        logger.debug("Added simple list job", line_num=line_num, url=url)
                    except Exception as e:
                        logger.warning(
                            "Skipped invalid URL", line_num=line_num, url=url, error=str(e)
                        )

        return added

    async def process_all(
        self, progress_callback: Callable[[str, int], None] | None = None
    ) -> BatchSummary:
        """Process all jobs in the batch queue.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with processing results and statistics
        """
        if not self.jobs:
            logger.warning("No jobs to process")
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "jobs": [],
                "total_duration": 0.0,
                "average_duration": 0.0,
            }

        logger.info("Starting batch processing", total_jobs=len(self.jobs))

        # Setup progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Create main progress task
            main_task = progress.add_task(
                f"Processing {len(self.jobs)} URLs...", total=len(self.jobs)
            )

            # Create individual job tasks
            for job in self.jobs:
                job.progress_task = progress.add_task(
                    f"Queued: {job.url}", total=100, visible=False
                )

            # Process jobs concurrently
            tasks = [
                self._process_single_job(job, progress, progress_callback) for job in self.jobs
            ]

            # Wait for all jobs to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Update main progress
            progress.update(main_task, completed=len(self.jobs))

        # Compile results
        summary = self._compile_results(results)

        if self.config.create_summary:
            await self._create_summary_report(summary)

        logger.info(
            "Batch processing completed",
            total=summary["total"],
            successful=summary["successful"],
            failed=summary["failed"],
        )

        return summary

    async def _process_single_job(
        self,
        job: BatchJob,
        progress: Progress,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> BatchJob:
        """Process a single job with semaphore control.

        Args:
            job: Job to process
            progress: Rich progress instance
            progress_callback: Optional progress callback

        Returns:
            Updated job with results
        """
        async with self.semaphore:
            job.start_time = asyncio.get_event_loop().time()
            job.status = BatchJobStatus.RUNNING

            # Show job in progress
            if job.progress_task:
                progress.update(
                    job.progress_task, description=f"Processing: {job.url}", visible=True
                )

            try:
                # Check if output already exists and skip if configured
                if (
                    self.config.skip_existing
                    and (job.output_dir / "converted_content.html").exists()
                ):
                    job.status = BatchJobStatus.SKIPPED
                    logger.info("Skipping existing output", url=job.url)
                    return job

                # Create converter and process
                converter = AsyncWordPressConverter(job.url, job.output_dir)

                def job_progress_callback(p: int):
                    if job.progress_task:
                        progress.update(job.progress_task, completed=p)
                    if progress_callback:
                        progress_callback(job.url, p)

                # Process with timeout
                await asyncio.wait_for(
                    converter.convert(progress_callback=job_progress_callback),
                    timeout=self.config.timeout_per_job,
                )

                job.status = BatchJobStatus.COMPLETED
                job.end_time = asyncio.get_event_loop().time()

                if job.progress_task:
                    progress.update(
                        job.progress_task, description=f"✅ Completed: {job.url}", completed=100
                    )

                logger.info("Job completed successfully", url=job.url, duration=job.duration)

                # Create archive if configured
                if self.config.create_archives:
                    try:
                        archive_path = await self._create_archive(job)
                        job.archive_path = archive_path
                        logger.info("Created job archive", url=job.url, archive=str(archive_path))
                    except Exception as e:
                        logger.warning("Failed to create archive", url=job.url, error=str(e))

            except TimeoutError:
                job.status = BatchJobStatus.FAILED
                job.error = f"Timeout after {self.config.timeout_per_job}s"
                job.end_time = asyncio.get_event_loop().time()

                if job.progress_task:
                    progress.update(
                        job.progress_task, description=f"⏰ Timeout: {job.url}", completed=0
                    )

                logger.error("Job timed out", url=job.url, timeout=self.config.timeout_per_job)

            except Exception as e:
                job.status = BatchJobStatus.FAILED
                job.error = str(e)
                job.end_time = asyncio.get_event_loop().time()

                if job.progress_task:
                    progress.update(
                        job.progress_task, description=f"❌ Failed: {job.url}", completed=0
                    )

                logger.error("Job failed", url=job.url, error=str(e))

                if not self.config.continue_on_error:
                    raise

            return job

    def _compile_results(self, results: list[Any]) -> BatchSummary:
        """Compile processing results into a summary.

        Args:
            results: List of job results

        Returns:
            Summary dictionary with statistics
        """
        summary: BatchSummary = {
            "total": len(self.jobs),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "jobs": [],
            "total_duration": 0.0,
            "average_duration": 0.0,
        }

        for job in self.jobs:
            job_data: JobSummaryData = {
                "url": job.url,
                "status": job.status.value,
                "output_dir": str(job.output_dir),
                "duration": job.duration,
                "error": job.error,
            }
            summary["jobs"].append(job_data)

            if job.status == BatchJobStatus.COMPLETED:
                summary["successful"] += 1
                if job.duration:
                    summary["total_duration"] += job.duration
            elif job.status == BatchJobStatus.FAILED:
                summary["failed"] += 1
            elif job.status == BatchJobStatus.SKIPPED:
                summary["skipped"] += 1

        if summary["successful"] > 0:
            summary["average_duration"] = summary["total_duration"] / summary["successful"]

        return summary

    async def _create_summary_report(self, summary: BatchSummary) -> None:
        """Create a summary report of the batch processing.

        Args:
            summary: Processing summary data
        """
        # Create summary table
        table = Table(title="Batch Processing Summary")
        table.add_column("URL", style="cyan", no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Duration", justify="right")
        table.add_column("Output", style="dim")

        for job_data in summary["jobs"]:
            status = job_data["status"]
            status_color = {
                "completed": "green",
                "failed": "red",
                "skipped": "yellow",
                "pending": "dim",
            }.get(status, "white")

            duration_str = f"{job_data['duration']:.1f}s" if job_data["duration"] else "N/A"

            table.add_row(
                job_data["url"][:50] + "..." if len(job_data["url"]) > 50 else job_data["url"],
                f"[{status_color}]{status.upper()}[/{status_color}]",
                duration_str,
                str(Path(job_data["output_dir"]).name),
            )

        # Show summary panel
        stats_text = f"""
Total Jobs: {summary["total"]}
✅ Successful: {summary["successful"]}
❌ Failed: {summary["failed"]}
⏭️  Skipped: {summary["skipped"]}
⏱️  Average Duration: {summary["average_duration"]:.1f}s
        """.strip()

        console.print()
        console.print(Panel(stats_text, title="📊 Batch Results", expand=False))
        console.print()
        console.print(table)

        # Save summary to file
        summary_path = self.config.output_base_dir / "batch_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)

        import json

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)

        logger.info("Summary report saved", path=str(summary_path))

    async def _create_archive(self, job: BatchJob) -> Path:
        """Create a ZIP archive of the job's output directory.

        Args:
            job: Completed batch job

        Returns:
            Path to the created ZIP archive

        Raises:
            Exception: If archive creation fails
        """
        import zipfile

        if not job.output_dir.exists():
            raise ValueError(f"Output directory does not exist: {job.output_dir}")

        # Create archive name based on job slug/URL
        archive_name = f"{job.output_dir.name}.zip"
        archive_path = self.config.output_base_dir / "archives" / archive_name

        # Ensure archives directory exists
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug("Creating archive", job_url=job.url, archive_path=str(archive_path))

        # Create ZIP archive
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add all files from the output directory
            for file_path in job.output_dir.rglob("*"):
                if file_path.is_file():
                    # Calculate relative path within the archive
                    arc_path = file_path.relative_to(job.output_dir)
                    zip_file.write(file_path, arc_path)
                    logger.debug("Added file to archive", file=str(arc_path))

        # Optional: Clean up original directory if configured
        if getattr(self.config, "cleanup_after_archive", False):
            import shutil

            shutil.rmtree(job.output_dir)
            logger.debug("Cleaned up original directory", path=str(job.output_dir))

        archive_size = archive_path.stat().st_size
        logger.info(
            "Archive created successfully",
            job_url=job.url,
            archive_path=str(archive_path),
            size_bytes=archive_size,
            size_mb=round(archive_size / CONSTANTS.BYTES_PER_MB, 2),
        )

        return archive_path
