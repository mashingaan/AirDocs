# AirDocs - Path Builder
# ==============================

import logging
from datetime import date, datetime
from pathlib import Path

from core.app_context import get_context

logger = logging.getLogger("airdocs.utils")


class PathBuilder:
    """
    Builder for standardized file and directory paths.

    Standard structure:
    Data/
    └── AWB-{awb_number}/
        ├── {date}_{action}/
        │   ├── AWB-{awb_number}.pdf
        │   ├── Счет_{awb_number}.docx
        │   └── ...
        ├── Комплект_{client_type}/
        │   └── ...
        └── Письма/
            └── ...
    """

    def __init__(self):
        self._context = get_context()

    @property
    def output_dir(self) -> Path:
        """Get base output directory."""
        return self._context.get_path("output_dir")

    def build_shipment_path(
        self,
        awb_number: str,
        action: str | None = None,
        create: bool = True,
    ) -> Path:
        """
        Build path to shipment directory.

        Args:
            awb_number: AWB number
            action: Optional action name for subdirectory (e.g., "Создание")
            create: Whether to create directory if it doesn't exist

        Returns:
            Path to shipment directory
        """
        # Clean AWB number for directory name
        clean_awb = self._clean_for_path(awb_number)

        path = self.output_dir / f"AWB-{clean_awb}"

        if action:
            today = date.today().strftime("%Y-%m-%d")
            action_clean = self._clean_for_path(action)
            path = path / f"{today}_{action_clean}"

        if create:
            path.mkdir(parents=True, exist_ok=True)

        return path

    def build_document_path(
        self,
        awb_number: str,
        document_type: str,
        extension: str,
        version: int = 1,
        action: str | None = None,
    ) -> Path:
        """
        Build path for a document file.

        Args:
            awb_number: AWB number
            document_type: Type of document (e.g., "Счет", "УПД")
            extension: File extension (with or without dot)
            version: Document version (1 = first version)
            action: Optional action name for parent directory

        Returns:
            Full path to document file
        """
        # Get parent directory
        parent = self.build_shipment_path(awb_number, action)

        # Clean document type for filename
        doc_type_clean = self._clean_for_path(document_type)

        # Build filename
        if not extension.startswith("."):
            extension = f".{extension}"

        if version > 1:
            filename = f"{doc_type_clean}_{awb_number}_v{version}{extension}"
        else:
            filename = f"{doc_type_clean}_{awb_number}{extension}"

        return parent / filename

    def build_package_path(
        self,
        awb_number: str,
        client_type: str,
        create: bool = True,
    ) -> Path:
        """
        Build path to document package directory.

        Args:
            awb_number: AWB number
            client_type: Type of client (TiA, FF, IP)
            create: Whether to create directory

        Returns:
            Path to package directory
        """
        clean_awb = self._clean_for_path(awb_number)
        path = self.output_dir / f"AWB-{clean_awb}" / f"Комплект_{client_type}"

        if create:
            path.mkdir(parents=True, exist_ok=True)

        return path

    def build_zip_path(
        self,
        awb_number: str,
        client_type: str | None = None,
        zip_type: str = "комплект",
    ) -> Path:
        """
        Build path for a ZIP archive.

        Args:
            awb_number: AWB number
            client_type: Optional client type
            zip_type: Type of ZIP (комплект, реестр)

        Returns:
            Path to ZIP file
        """
        clean_awb = self._clean_for_path(awb_number)
        today = date.today().strftime("%Y-%m-%d")

        parent = self.output_dir / f"AWB-{clean_awb}"
        parent.mkdir(parents=True, exist_ok=True)

        if client_type:
            filename = f"Комплект_{client_type}_{today}.zip"
        else:
            filename = f"{zip_type.capitalize()}_{clean_awb}_{today}.zip"

        return parent / filename

    def build_email_path(
        self,
        awb_number: str,
        create: bool = True,
    ) -> Path:
        """
        Build path to email drafts directory.

        Args:
            awb_number: AWB number
            create: Whether to create directory

        Returns:
            Path to emails directory
        """
        clean_awb = self._clean_for_path(awb_number)
        path = self.output_dir / f"AWB-{clean_awb}" / "Письма"

        if create:
            path.mkdir(parents=True, exist_ok=True)

        return path

    def build_registry_path(
        self,
        registry_date: date | None = None,
        format: str = "xlsx",
    ) -> Path:
        """
        Build path for a registry file.

        Args:
            registry_date: Date for registry (defaults to today)
            format: File format (xlsx, zip)

        Returns:
            Path to registry file
        """
        if registry_date is None:
            registry_date = date.today()

        date_str = registry_date.strftime("%Y-%m-%d")

        registry_dir = self.output_dir / "Реестры"
        registry_dir.mkdir(parents=True, exist_ok=True)

        return registry_dir / f"Реестр_{date_str}.{format}"

    def get_latest_version_path(
        self,
        awb_number: str,
        document_type: str,
        extension: str,
    ) -> tuple[Path | None, int]:
        """
        Find the latest version of a document and return next version number.

        Args:
            awb_number: AWB number
            document_type: Type of document
            extension: File extension

        Returns:
            Tuple of (path to latest version or None, next version number)
        """
        parent = self.build_shipment_path(awb_number, create=False)

        if not parent.exists():
            return None, 1

        doc_type_clean = self._clean_for_path(document_type)
        if not extension.startswith("."):
            extension = f".{extension}"

        # Pattern: {type}_{awb}_v{n}{ext} or {type}_{awb}{ext}
        import re

        pattern = re.compile(
            rf"{re.escape(doc_type_clean)}_{re.escape(awb_number)}(?:_v(\d+))?{re.escape(extension)}$"
        )

        max_version = 0
        latest_path = None

        for file_path in parent.rglob(f"*{extension}"):
            match = pattern.match(file_path.name)
            if match:
                version = int(match.group(1)) if match.group(1) else 1
                if version > max_version:
                    max_version = version
                    latest_path = file_path

        return latest_path, max_version + 1

    def _clean_for_path(self, text: str) -> str:
        """
        Clean text for use in file/directory names.

        Removes/replaces characters that are invalid in Windows paths.
        """
        # Characters invalid in Windows filenames
        invalid_chars = '<>:"/\\|?*'

        result = text
        for char in invalid_chars:
            result = result.replace(char, "_")

        # Remove leading/trailing spaces and dots
        result = result.strip(". ")

        # Limit length
        if len(result) > 100:
            result = result[:100]

        return result
