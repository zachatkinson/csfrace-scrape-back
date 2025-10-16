"""Job download operations - Serve ZIP archives of completed jobs.

This module handles downloading job output files as ZIP archives.
Follows Single Responsibility Principle by focusing only on file serving.
"""

import hashlib
import os
import tempfile
import zipfile
from pathlib import Path

import asyncio
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from src.constants.core import DEFAULT_OUTPUT_DIR
from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

from ...crud import JobCRUD
from ...dependencies import DBSession
from ...errors import APIErrorFactory

logger = get_api_logger()

router = APIRouter()


@router.get("/{job_id}/download")
@api_error_handler("download job")
async def download_job(job_id: str, db: DBSession) -> FileResponse:
    """Download completed job output as ZIP file.

    Creates a ZIP archive containing all output files from a completed job:
    - converted_content.html (clean HTML)
    - shopify_ready_content.html (with metadata comments)
    - metadata.txt (page metadata)
    - images/ (downloaded images directory)

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        FileResponse with ZIP archive

    Raises:
        HTTPException 404: If job not found
        HTTPException 400: If job not completed
        HTTPException 500: If files not found or ZIP creation fails
    """
    logger.info("Download requested", job_id=job_id)

    # Validate job exists and is completed
    job = await JobCRUD.get_job(db, job_id)
    if not job:
        logger.warning("Job not found for download", job_id=job_id)
        raise APIErrorFactory.not_found("Job", job_id)

    if job.status != "completed":
        logger.warning("Job not completed", job_id=job_id, status=job.status)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job must be completed to download (current status: {job.status})",
        )

    # Check if job has content_results with file paths
    if not job.content_results or len(job.content_results) == 0:
        logger.error("No content results found for completed job", job_id=job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job output files not found",
        )

    content_result = job.content_results[0]  # Latest result

    # Determine output directory from file paths
    if content_result.html_file_path:
        output_dir = Path(content_result.html_file_path).parent
    elif content_result.images_directory:
        output_dir = Path(content_result.images_directory).parent
    else:
        logger.error("No file paths in content result", job_id=job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job output files not found",
        )

    # Security validation: Sanitize output_dir path (prevent path traversal)
    # Inline validation for CodeQL taint tracking recognition
    output_dir_str = str(output_dir)
    normalized_output = os.path.normpath(output_dir_str)
    normalized_base = os.path.normpath(os.path.abspath(DEFAULT_OUTPUT_DIR))

    # CodeQL-recognized guard: constant string comparison (StringConstCompare pattern)
    # This acts as a sanitizer guard in CodeQL's dataflow analysis
    if (
        not normalized_output.startswith(normalized_base + os.sep)
        and normalized_output != normalized_base
    ):
        logger.error(
            "Security: Path traversal detected in output directory",
            job_id=job_id,
            output_dir=output_dir_str,
            base_dir=normalized_base,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid output directory location",
        )

    # Verify validated path exists and is a directory
    if not os.path.exists(normalized_output) or not os.path.isdir(normalized_output):
        logger.error("Output directory not found", job_id=job_id, output_dir=normalized_output)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job output files no longer exist",
        )

    # Use the validated path
    output_dir = Path(normalized_output)

    logger.info("Creating ZIP archive", job_id=job_id, output_dir=normalized_output)

    # Create ZIP archive in temporary directory
    try:
        zip_path = await _create_job_archive(job_id, output_dir)
        logger.info("ZIP archive created", job_id=job_id, zip_path=str(zip_path))

        # Security validation: Verify ZIP path is within temp directory
        # Inline validation for CodeQL taint tracking recognition
        zip_path_str = str(zip_path)
        normalized_zip = os.path.normpath(zip_path_str)
        normalized_temp = os.path.normpath(os.path.abspath(tempfile.gettempdir()))

        # CodeQL-recognized guard: constant string comparison (StringConstCompare pattern)
        if (
            not normalized_zip.startswith(normalized_temp + os.sep)
            and normalized_zip != normalized_temp
        ):
            logger.error(
                "Security: ZIP path traversal detected",
                job_id=job_id,
                zip_path=zip_path_str,
                temp_dir=normalized_temp,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid archive path",
            )

        # Verify the file exists before serving (use validated string path)
        if not os.path.exists(normalized_zip) or not os.path.isfile(normalized_zip):
            logger.error(
                "ZIP file not found after creation", job_id=job_id, zip_path=normalized_zip
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Archive file not found",
            )

        # Generate safe filename from job data
        domain = getattr(job, "domain", "job")
        title = content_result.title if content_result.title else "output"
        # Sanitize filename (allow only alphanumeric, dash, underscore)
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title[:50])
        filename = f"{domain}_{safe_title}_{job_id[:8]}.zip"

        # Use validated string path directly for FileResponse (CodeQL taint tracking)
        return FileResponse(
            path=normalized_zip,
            media_type="application/zip",
            filename=filename,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache",
            },
        )

    except Exception as e:
        logger.error("Failed to create ZIP archive", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create download archive: {str(e)}",
        ) from e


async def _create_job_archive(job_id: str, output_dir: Path) -> Path:
    """Create ZIP archive of job output directory.

    Args:
        job_id: Job ID (for naming)
        output_dir: Path to job output directory

    Returns:
        Path to created ZIP file in temp directory

    Raises:
        ValueError: If paths are invalid or contain traversal attempts
        Exception: If archive creation fails
    """
    # Validate output_dir to prevent path traversal (inline for CodeQL taint tracking)
    output_dir_str = str(output_dir)
    normalized_output = os.path.normpath(output_dir_str)
    normalized_base = os.path.normpath(os.path.abspath(DEFAULT_OUTPUT_DIR))

    # CodeQL-recognized guard: constant string comparison
    if (
        not normalized_output.startswith(normalized_base + os.sep)
        and normalized_output != normalized_base
    ):
        raise ValueError(
            f"Path traversal detected: {output_dir_str} is outside {DEFAULT_OUTPUT_DIR}"
        )

    # Ensure output_dir exists and is a directory (use os.path for validation)
    if not os.path.exists(normalized_output) or not os.path.isdir(normalized_output):
        raise ValueError(f"Invalid output directory: {normalized_output}")

    output_dir = Path(normalized_output)

    # Create temp file for ZIP archive with strict path validation
    temp_dir = tempfile.gettempdir()
    # Use job_id hash for unique temp filename
    file_hash = hashlib.md5(job_id.encode(), usedforsecurity=False).hexdigest()[:8]
    zip_filename = f"job_{job_id[:8]}_{file_hash}.zip"

    # Security check: Sanitize and validate ZIP path (inline for CodeQL recognition)
    # Construct path using os.path.join for CodeQL taint tracking
    zip_path_str = os.path.join(temp_dir, zip_filename)
    normalized_zip = os.path.normpath(zip_path_str)
    normalized_temp = os.path.normpath(os.path.abspath(temp_dir))

    # CodeQL-recognized guard: constant string comparison
    if (
        not normalized_zip.startswith(normalized_temp + os.sep)
        and normalized_zip != normalized_temp
    ):
        raise ValueError(f"Path traversal detected: {zip_path_str} is outside {temp_dir}")

    zip_path = Path(normalized_zip)

    # Run ZIP creation in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _create_zip_sync, output_dir, zip_path)

    return zip_path


def _create_zip_sync(output_dir: Path, zip_path: Path) -> None:
    """Synchronous ZIP creation (runs in thread pool).

    Args:
        output_dir: Source directory to ZIP
        zip_path: Destination ZIP file path
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Add all files from output directory
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                # Calculate relative path within archive
                arc_path = file_path.relative_to(output_dir)
                zip_file.write(file_path, arc_path)
                logger.debug("Added file to archive", file=str(arc_path))

    logger.debug("ZIP creation completed", zip_path=str(zip_path))
