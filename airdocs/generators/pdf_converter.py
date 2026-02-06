# AirDocs - PDF Converter
# ===============================

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.constants import PDFConversionMethod
from core.app_context import get_context
from core.exceptions import ConversionError

logger = logging.getLogger("airdocs.generators")


@dataclass
class ConversionResult:
    """Result of a PDF conversion operation."""

    success: bool
    method: PDFConversionMethod
    output_path: Path | None = None
    error: str | None = None
    warnings: list[str] | None = None

    def __bool__(self) -> bool:
        return self.success


class PDFConverter:
    """
    Converts Word (DOCX) and Excel (XLSX) documents to PDF.

    Strategy (FIXED, not configurable):
    1. PRIMARY: Microsoft Office COM automation (ExportAsFixedFormat)
    2. FALLBACK: LibreOffice headless mode

    IMPORTANT: Never silently switch between methods.
    Always log and notify UI about which method is being used.
    """

    def __init__(self):
        self._context = get_context()
        self._office_integration = None
        self._libreoffice_integration = None

        # Cache availability status
        self._office_available: bool | None = None
        self._libreoffice_available: bool | None = None

    @property
    def office_integration(self):
        """Lazy load Office COM integration."""
        if self._office_integration is None:
            from integrations.office_com import OfficeCOMIntegration
            self._office_integration = OfficeCOMIntegration()
        return self._office_integration

    @property
    def libreoffice_integration(self):
        """Lazy load LibreOffice integration."""
        if self._libreoffice_integration is None:
            from integrations.libreoffice import LibreOfficeIntegration
            self._libreoffice_integration = LibreOfficeIntegration()
        return self._libreoffice_integration

    def convert(
        self,
        source_path: Path | str,
        output_path: Path | str | None = None,
        force_method: PDFConversionMethod | None = None,
    ) -> ConversionResult:
        """
        Convert a document to PDF.

        Args:
            source_path: Path to source document (DOCX or XLSX)
            output_path: Optional output path. If None, uses source path with .pdf extension.
            force_method: Optional method to force (bypasses normal strategy)

        Returns:
            ConversionResult with success status and details

        Strategy:
        1. Try Office COM first (if available)
        2. If Office fails or unavailable, try LibreOffice
        3. If both fail, return error
        """
        source_path = Path(source_path)
        if not source_path.exists():
            return ConversionResult(
                success=False,
                method=PDFConversionMethod.NONE,
                error=f"Source file not found: {source_path}",
            )

        # Determine output path
        if output_path is None:
            output_path = source_path.with_suffix(".pdf")
        else:
            output_path = Path(output_path)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        warnings = []

        # Force specific method if requested
        if force_method:
            return self._convert_with_method(source_path, output_path, force_method)

        # Strategy: Office COM first, then LibreOffice
        if self._is_office_available():
            logger.info(f"Converting to PDF using Office COM: {source_path}")
            result = self._convert_with_office(source_path, output_path)
            if result.success:
                return result
            else:
                warnings.append(f"Office COM failed: {result.error}")
                logger.warning(f"Office COM conversion failed: {result.error}")

        # Fallback to LibreOffice
        if self._is_libreoffice_available():
            logger.info(f"Converting to PDF using LibreOffice (fallback): {source_path}")
            warnings.append("Using LibreOffice fallback for PDF conversion")
            result = self._convert_with_libreoffice(source_path, output_path)
            result.warnings = warnings
            return result
        else:
            logger.warning("LibreOffice is not available for fallback")

        # Both methods failed/unavailable
        error_msg = "No PDF conversion method available. "
        if not self._is_office_available():
            error_msg += "Microsoft Office not installed. "
        if not self._is_libreoffice_available():
            error_msg += "LibreOffice not installed. "

        return ConversionResult(
            success=False,
            method=PDFConversionMethod.NONE,
            error=error_msg.strip(),
            warnings=warnings if warnings else None,
        )

    def _convert_with_method(
        self,
        source_path: Path,
        output_path: Path,
        method: PDFConversionMethod,
    ) -> ConversionResult:
        """Convert using a specific method."""
        if method == PDFConversionMethod.OFFICE_COM:
            if not self._is_office_available():
                return ConversionResult(
                    success=False,
                    method=method,
                    error="Microsoft Office is not available",
                )
            return self._convert_with_office(source_path, output_path)

        elif method == PDFConversionMethod.LIBREOFFICE:
            if not self._is_libreoffice_available():
                return ConversionResult(
                    success=False,
                    method=method,
                    error="LibreOffice is not available",
                )
            return self._convert_with_libreoffice(source_path, output_path)

        else:
            return ConversionResult(
                success=False,
                method=method,
                error=f"Unknown conversion method: {method}",
            )

    def _convert_with_office(
        self,
        source_path: Path,
        output_path: Path,
    ) -> ConversionResult:
        """Convert using Office COM."""
        try:
            suffix = source_path.suffix.lower()

            if suffix == ".docx":
                self.office_integration.word_to_pdf(source_path, output_path)
            elif suffix == ".xlsx":
                self.office_integration.excel_to_pdf(source_path, output_path)
            else:
                return ConversionResult(
                    success=False,
                    method=PDFConversionMethod.OFFICE_COM,
                    error=f"Unsupported file type for Office conversion: {suffix}",
                )

            return ConversionResult(
                success=True,
                method=PDFConversionMethod.OFFICE_COM,
                output_path=output_path,
            )

        except Exception as e:
            return ConversionResult(
                success=False,
                method=PDFConversionMethod.OFFICE_COM,
                error=str(e),
            )

    def _convert_with_libreoffice(
        self,
        source_path: Path,
        output_path: Path,
    ) -> ConversionResult:
        """Convert using LibreOffice headless mode."""
        try:
            self.libreoffice_integration.convert_to_pdf(source_path, output_path)

            return ConversionResult(
                success=True,
                method=PDFConversionMethod.LIBREOFFICE,
                output_path=output_path,
            )

        except Exception as e:
            return ConversionResult(
                success=False,
                method=PDFConversionMethod.LIBREOFFICE,
                error=str(e),
            )

    def _is_office_available(self) -> bool:
        """Check if Office COM is available (cached)."""
        if self._office_available is None:
            try:
                self._office_available = self.office_integration.is_available()
            except Exception:
                self._office_available = False
        return self._office_available

    def _is_libreoffice_available(self) -> bool:
        """Check if LibreOffice is available (cached)."""
        if self._libreoffice_available is None:
            try:
                self._libreoffice_available = self.libreoffice_integration.is_available()
            except Exception:
                self._libreoffice_available = False
        return self._libreoffice_available

    def get_available_methods(self) -> list[PDFConversionMethod]:
        """Get list of available conversion methods."""
        methods = []
        if self._is_office_available():
            methods.append(PDFConversionMethod.OFFICE_COM)
        if self._is_libreoffice_available():
            methods.append(PDFConversionMethod.LIBREOFFICE)
        return methods

    def get_diagnostics(self) -> dict[str, Any]:
        """
        Get diagnostic information about PDF conversion capabilities.

        Returns:
            Dictionary with diagnostic info for UI display
        """
        diag = {
            "office_com": {
                "available": self._is_office_available(),
                "label": "Microsoft Office (COM)",
                "role": "Primary",
            },
            "libreoffice": {
                "available": self._is_libreoffice_available(),
                "label": "LibreOffice",
                "role": "Fallback",
            },
            "any_available": bool(self.get_available_methods()),
            "preferred_method": None,
        }

        if self._is_office_available():
            diag["preferred_method"] = PDFConversionMethod.OFFICE_COM
            diag["office_com"]["version"] = self.office_integration.get_version()
        elif self._is_libreoffice_available():
            diag["preferred_method"] = PDFConversionMethod.LIBREOFFICE
            diag["libreoffice"]["version"] = self.libreoffice_integration.get_version()

        return diag

    def refresh_availability(self) -> None:
        """Force refresh of availability cache."""
        self._office_available = None
        self._libreoffice_available = None
        logger.debug("PDF converter availability cache cleared")
