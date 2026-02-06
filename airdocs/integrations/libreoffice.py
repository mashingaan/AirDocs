# AirDocs - LibreOffice Integration
# =========================================

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.app_context import get_context
from core.exceptions import IntegrationError

logger = logging.getLogger("airdocs.integrations")


class LibreOfficeIntegration:
    """
    LibreOffice headless mode integration for document conversion.

    Used as FALLBACK when Microsoft Office is not available.

    Supports:
    - DOCX to PDF conversion
    - XLSX to PDF conversion
    - ODT/ODS to PDF conversion

    Requires LibreOffice to be installed on the system.
    """

    def __init__(self):
        self._context = get_context()
        self._config = self._context.get_libreoffice_config()
        self._soffice_path: Path | None = None

    def _find_soffice(self) -> Path | None:
        """
        Find LibreOffice soffice executable.

        Searches:
        1. Configured paths in settings.yaml
        2. Common installation locations
        3. System PATH

        Returns:
            Path to soffice executable or None if not found
        """
        if self._soffice_path and self._soffice_path.exists():
            return self._soffice_path

        # Check configured paths first
        configured_paths = self._config.get("install_paths", [])
        for path_str in configured_paths:
            path = Path(path_str)
            if path.exists():
                self._soffice_path = path
                logger.debug(f"Found LibreOffice at configured path: {path}")
                return path

        # Common Windows paths
        common_paths = [
            Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
            Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
            Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "LibreOffice" / "program" / "soffice.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "LibreOffice" / "program" / "soffice.exe",
        ]

        for path in common_paths:
            if path.exists():
                self._soffice_path = path
                logger.debug(f"Found LibreOffice at: {path}")
                return path

        # Check PATH
        soffice_in_path = shutil.which("soffice")
        if soffice_in_path:
            self._soffice_path = Path(soffice_in_path)
            logger.debug(f"Found LibreOffice in PATH: {soffice_in_path}")
            return self._soffice_path

        logger.debug("LibreOffice not found")
        return None

    def is_available(self) -> bool:
        """Check if LibreOffice is available."""
        return self._find_soffice() is not None

    def get_version(self) -> str | None:
        """Get LibreOffice version string."""
        soffice = self._find_soffice()
        if not soffice:
            return None

        try:
            result = subprocess.run(
                [str(soffice), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.debug(f"Could not get LibreOffice version: {e}")
            return None

    def get_path(self) -> Path | None:
        """Get path to LibreOffice executable."""
        return self._find_soffice()

    def convert_to_pdf(
        self,
        source_path: Path | str,
        output_path: Path | str,
    ) -> None:
        """
        Convert document to PDF using LibreOffice headless mode.

        Args:
            source_path: Path to source document (DOCX, XLSX, ODT, ODS)
            output_path: Path where to save PDF

        Raises:
            IntegrationError: If LibreOffice not available or conversion fails
        """
        soffice = self._find_soffice()
        if not soffice:
            raise IntegrationError(
                "LibreOffice not installed or not found",
                integration="libreoffice",
                operation="convert_to_pdf",
            )

        source_path = Path(source_path).resolve()
        output_path = Path(output_path).resolve()

        if not source_path.exists():
            raise IntegrationError(
                f"Source file not found: {source_path}",
                integration="libreoffice",
                operation="convert_to_pdf",
            )

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # LibreOffice converts to the same directory as source by default,
        # so we need to specify output directory and then move if needed
        output_dir = output_path.parent

        # Get timeout from config
        timeout = self._config.get("conversion_timeout", 60)

        try:
            # Run LibreOffice in headless mode
            cmd = [
                str(soffice),
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(output_dir),
                str(source_path),
            ]

            logger.debug(f"Running LibreOffice: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise IntegrationError(
                    f"LibreOffice conversion failed: {error_msg}",
                    integration="libreoffice",
                    operation="convert_to_pdf",
                )

            # LibreOffice creates PDF with same name as source in output_dir
            expected_output = output_dir / (source_path.stem + ".pdf")

            if not expected_output.exists():
                raise IntegrationError(
                    f"LibreOffice did not create expected output: {expected_output}",
                    integration="libreoffice",
                    operation="convert_to_pdf",
                )

            # Rename to target path if different
            if expected_output != output_path:
                if output_path.exists():
                    output_path.unlink()
                expected_output.rename(output_path)

            logger.info(f"Converted to PDF via LibreOffice: {output_path}")

        except subprocess.TimeoutExpired:
            raise IntegrationError(
                f"LibreOffice conversion timed out after {timeout} seconds",
                integration="libreoffice",
                operation="convert_to_pdf",
            )
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(
                f"LibreOffice conversion failed: {e}",
                integration="libreoffice",
                operation="convert_to_pdf",
                cause=e,
            )

    def convert_batch(
        self,
        source_paths: list[Path | str],
        output_dir: Path | str,
    ) -> list[tuple[Path, Path | None, str | None]]:
        """
        Convert multiple documents to PDF.

        Args:
            source_paths: List of source document paths
            output_dir: Directory where to save PDFs

        Returns:
            List of tuples: (source_path, output_path or None, error or None)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for source_path in source_paths:
            source_path = Path(source_path)
            output_path = output_dir / (source_path.stem + ".pdf")

            try:
                self.convert_to_pdf(source_path, output_path)
                results.append((source_path, output_path, None))
            except IntegrationError as e:
                results.append((source_path, None, str(e)))
                logger.error(f"Failed to convert {source_path}: {e}")

        return results
