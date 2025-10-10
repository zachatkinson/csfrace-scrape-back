"""Job download operations - Serve ZIP archives of completed jobs.

This module handles downloading job output files as ZIP archives.
Follows Single Responsibility Principle by focusing only on file serving.
"""

import hashlib
import tempfile
import zipfile
from pathlib import Path

import asyncio
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

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

    if not output_dir.exists():
        logger.error("Output directory not found", job_id=job_id, output_dir=str(output_dir))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job output files no longer exist",
        )

    logger.info("Creating ZIP archive", job_id=job_id, output_dir=str(output_dir))

    # Create ZIP archive in temporary directory
    try:
        zip_path = await _create_job_archive(job_id, output_dir)
        logger.info("ZIP archive created", job_id=job_id, zip_path=str(zip_path))

        # Generate safe filename from job data
        domain = getattr(job, "domain", "job")
        title = content_result.title if content_result.title else "output"
        # Sanitize filename
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title[:50])
        filename = f"{domain}_{safe_title}_{job_id[:8]}.zip"

        return FileResponse(
            path=zip_path,
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
        Exception: If archive creation fails
    """
    # Create temp file for ZIP archive
    temp_dir = Path(tempfile.gettempdir())
    # Use job_id hash for unique temp filename
    file_hash = hashlib.md5(job_id.encode(), usedforsecurity=False).hexdigest()[:8]
    zip_path = temp_dir / f"job_{job_id[:8]}_{file_hash}.zip"

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
