"""Export service for generating citation files in various formats."""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.schemas import Evidence


class ExportService:
    """Service for exporting evidence data to various citation formats."""

    @staticmethod
    def generate_ris(evidences: list[Evidence]) -> str:
        """Generate RIS format citation file from evidences.

        RIS Format Reference:
        - TY: Type of reference (JOUR=Journal, WEB=Website, etc.)
        - TI: Title
        - AU: Author (repeatable)
        - PY: Publication year
        - Y2: Date accessed (for web resources)
        - AB: Abstract
        - UR: URL
        - SN: ISSN/ISBN
        - SP/EP: Start/End page
        - VL: Volume
        - IS: Issue
        - DO: DOI
        - ER: End of reference

        Args:
            evidences: List of evidence items to export

        Returns:
            RIS formatted string
        """
        output = StringIO()

        for evidence in evidences:
            metadata = evidence.metadata

            # Determine reference type based on source type
            if evidence.sourceType.value == "WEB":
                ref_type = "WEB"
            elif evidence.sourceType.value == "PATENT":
                ref_type = "PAT"
            else:
                ref_type = "JOUR"  # Default to journal for papers

            # TY - Reference type
            output.write(f"TY  - {ref_type}\n")

            # TI - Title
            if metadata.title:
                title = metadata.title.strip()
                if title:
                    output.write(f"TI  - {title}\n")

            # AU - Authors (one per line)
            for author in metadata.authors:
                author = author.strip()
                if author:
                    output.write(f"AU  - {author}\n")

            # PY - Publication year
            if metadata.publishDate:
                try:
                    # Try to extract year from various date formats
                    date_str = metadata.publishDate.strip()
                    if date_str:
                        # Handle ISO format (YYYY-MM-DD)
                        if "-" in date_str:
                            year = date_str.split("-")[0]
                            if year.isdigit():
                                output.write(f"PY  - {year}\n")
                        # Handle year only
                        elif date_str.isdigit() and len(date_str) == 4:
                            output.write(f"PY  - {date_str}\n")
                except (ValueError, IndexError):
                    pass

            # AB - Abstract
            if metadata.abstract:
                abstract = metadata.abstract.strip()
                if abstract:
                    output.write(f"AB  - {abstract}\n")

            # UR - URL
            if evidence.url:
                output.write(f"UR  - {evidence.url}\n")

            # Y2 - Date accessed (current date)
            current_date = datetime.now().strftime("%Y/%m/%d")
            output.write(f"Y2  - {current_date}\n")

            # Add score as a custom note
            if evidence.score:
                output.write(f"N1  - Relevance Score: {evidence.score:.2f}\n")

            # ER - End of reference
            output.write("ER  - \n\n")

        return output.getvalue()

    @staticmethod
    def generate_bibtex(evidences: list[Evidence]) -> str:
        """Generate BibTeX format citation file from evidences.

        Args:
            evidences: List of evidence items to export

        Returns:
            BibTeX formatted string
        """
        output = StringIO()
        output.write("% Generated bibliography\n\n")

        for i, evidence in enumerate(evidences, 1):
            metadata = evidence.metadata

            # Generate citation key
            first_author = metadata.authors[0].split()[-1] if metadata.authors else "Unknown"
            year = ""
            if metadata.publishDate:
                try:
                    date_str = metadata.publishDate.strip()
                    if "-" in date_str:
                        year = date_str.split("-")[0]
                    elif date_str.isdigit() and len(date_str) == 4:
                        year = date_str
                except (ValueError, IndexError):
                    pass

            cite_key = f"{first_author.lower()}{year}_{i}"

            # Determine entry type
            if evidence.sourceType.value == "WEB":
                entry_type = "misc"
            elif evidence.sourceType.value == "PATENT":
                entry_type = "misc"
            else:
                entry_type = "article"

            output.write(f"@{entry_type}{{{cite_key},\n")

            # Title
            if metadata.title:
                output.write(f"  title = {{{metadata.title}}},\n")

            # Authors
            if metadata.authors:
                authors = " and ".join(metadata.authors)
                output.write(f"  author = {{{authors}}},\n")

            # Year
            if year:
                output.write(f"  year = {{{year}}},\n")

            # URL
            if evidence.url:
                output.write(f"  url = {{{evidence.url}}},\n")

            # Abstract (in note field)
            if metadata.abstract:
                output.write(f"  note = {{{metadata.abstract}}},\n")

            output.write("}\n\n")

        return output.getvalue()


export_service = ExportService()
