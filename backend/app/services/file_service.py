"""File service for report and document downloads."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from fastapi.responses import FileResponse


ReportType = Literal["report", "article", "references"]


class FileService:
    """Service for handling file operations."""

    REPORTS_DIR = Path("backend/.data/reports")

    @classmethod
    def get_report_path(cls, task_id: str, report_type: ReportType = "report") -> Path:
        """Get the path to a report file.

        Args:
            task_id: The task ID
            report_type: Type of report (report, article, references)

        Returns:
            Path to the report file
        """
        if report_type == "article":
            return cls.REPORTS_DIR / f"{task_id}_article.md"
        elif report_type == "references":
            return cls.REPORTS_DIR / f"{task_id}_references.md"
        return cls.REPORTS_DIR / f"{task_id}.md"

    @classmethod
    def validate_file_exists(cls, path: Path, detail: str = "File not found") -> None:
        """Validate that a file exists.

        Args:
            path: Path to validate
            detail: Error message detail if file doesn't exist

        Raises:
            HTTPException: If file doesn't exist
        """
        if not path.exists():
            raise HTTPException(status_code=404, detail=detail)

    @classmethod
    def get_file_response(
        cls,
        path: Path,
        filename: str,
        media_type: str = "text/markdown",
    ) -> FileResponse:
        """Create a FileResponse for a validated file.

        Args:
            path: Path to the file
            filename: Filename for the download
            media_type: MIME type of the file

        Returns:
            FileResponse for the file
        """
        return FileResponse(path, media_type=media_type, filename=filename)


file_service = FileService()
