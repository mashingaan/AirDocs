# AirDocs - Office COM Integration
# ========================================

import logging
import time
from pathlib import Path
from typing import Any

from core.app_context import get_context
from core.exceptions import IntegrationError

logger = logging.getLogger("airdocs.integrations")

# COM constants for PDF export
WD_EXPORT_FORMAT_PDF = 17  # Word: wdExportFormatPDF
XL_TYPE_PDF = 0  # Excel: xlTypePDF


class OfficeCOMIntegration:
    """
    Microsoft Office COM automation wrapper.

    Provides:
    - Word document to PDF conversion
    - Excel document to PDF conversion
    - Outlook email draft creation

    Uses pywin32 for COM automation.
    Implements retry logic and proper resource cleanup.
    """

    def __init__(self):
        self._context = get_context()
        self._config = self._context.get_office_config()

        # COM instances (lazy initialized)
        self._word_app = None
        self._excel_app = None
        self._outlook_app = None

        # Check if pywin32 is available
        self._com_available = self._check_com_available()

    def _check_com_available(self) -> bool:
        """Check if pywin32 COM is available."""
        try:
            import win32com.client
            import pythoncom
            return True
        except ImportError:
            logger.warning("pywin32 not installed - Office COM unavailable")
            return False

    def is_available(self) -> bool:
        """Check if Office COM automation is available."""
        if not self._com_available:
            return False

        try:
            # Try to instantiate Word to verify Office is installed
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Quit()
            return True
        except Exception as e:
            logger.debug(f"Office COM check failed: {e}")
            return False

    def get_version(self) -> str | None:
        """Get Office version string."""
        if not self._com_available:
            return None

        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            version = word.Version
            word.Quit()
            return f"Microsoft Office {version}"
        except Exception as e:
            logger.debug(f"Could not get Office version: {e}")
            return None

    def _get_word_app(self):
        """Get or create Word application instance."""
        import win32com.client
        import pythoncom

        pythoncom.CoInitialize()

        if self._word_app is None:
            self._word_app = win32com.client.Dispatch("Word.Application")
            self._word_app.Visible = False
            self._word_app.DisplayAlerts = False

        return self._word_app

    def _get_excel_app(self):
        """Get or create Excel application instance."""
        import win32com.client
        import pythoncom

        pythoncom.CoInitialize()

        if self._excel_app is None:
            self._excel_app = win32com.client.Dispatch("Excel.Application")
            self._excel_app.Visible = False
            self._excel_app.DisplayAlerts = False

        return self._excel_app

    def _get_outlook_app(self):
        """Get or create Outlook application instance."""
        import win32com.client
        import pythoncom

        pythoncom.CoInitialize()

        if self._outlook_app is None:
            self._outlook_app = win32com.client.Dispatch("Outlook.Application")

        return self._outlook_app

    def word_to_pdf(
        self,
        source_path: Path | str,
        output_path: Path | str,
    ) -> None:
        """
        Convert Word document to PDF using Office COM.

        Args:
            source_path: Path to source DOCX file
            output_path: Path where to save PDF

        Raises:
            IntegrationError: If conversion fails
        """
        if not self._com_available:
            raise IntegrationError(
                "Office COM not available (pywin32 not installed)",
                integration="office_com",
                operation="word_to_pdf",
            )

        source_path = Path(source_path).resolve()
        output_path = Path(output_path).resolve()

        if not source_path.exists():
            raise IntegrationError(
                f"Source file not found: {source_path}",
                integration="office_com",
                operation="word_to_pdf",
            )

        retries = self._config.get("com_retries", 3)
        retry_delay = self._config.get("retry_delay", 1)

        doc = None
        word = None

        for attempt in range(retries):
            try:
                import pythoncom
                pythoncom.CoInitialize()

                word = self._get_word_app()
                doc = word.Documents.Open(str(source_path))

                # Export to PDF
                doc.ExportAsFixedFormat(
                    OutputFileName=str(output_path),
                    ExportFormat=WD_EXPORT_FORMAT_PDF,
                    OpenAfterExport=False,
                    OptimizeFor=0,  # wdExportOptimizeForPrint
                )

                logger.info(f"Converted Word to PDF: {output_path}")
                return

            except Exception as e:
                logger.warning(
                    f"Word to PDF attempt {attempt + 1}/{retries} failed: {e}"
                )
                if attempt < retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise IntegrationError(
                        f"Word to PDF conversion failed after {retries} attempts: {e}",
                        integration="office_com",
                        operation="word_to_pdf",
                        cause=e,
                        fallback_available=True,
                    )
            finally:
                if doc:
                    try:
                        doc.Close(SaveChanges=False)
                    except Exception:
                        pass

    def excel_to_pdf(
        self,
        source_path: Path | str,
        output_path: Path | str,
    ) -> None:
        """
        Convert Excel document to PDF using Office COM.

        Args:
            source_path: Path to source XLSX file
            output_path: Path where to save PDF

        Raises:
            IntegrationError: If conversion fails
        """
        if not self._com_available:
            raise IntegrationError(
                "Office COM not available (pywin32 not installed)",
                integration="office_com",
                operation="excel_to_pdf",
            )

        source_path = Path(source_path).resolve()
        output_path = Path(output_path).resolve()

        if not source_path.exists():
            raise IntegrationError(
                f"Source file not found: {source_path}",
                integration="office_com",
                operation="excel_to_pdf",
            )

        retries = self._config.get("com_retries", 3)
        retry_delay = self._config.get("retry_delay", 1)

        wb = None
        excel = None

        for attempt in range(retries):
            try:
                import pythoncom
                pythoncom.CoInitialize()

                excel = self._get_excel_app()
                wb = excel.Workbooks.Open(str(source_path))

                # Export to PDF
                wb.ExportAsFixedFormat(
                    Type=XL_TYPE_PDF,
                    Filename=str(output_path),
                    Quality=0,  # xlQualityStandard
                    IncludeDocProperties=True,
                    IgnorePrintAreas=False,
                    OpenAfterPublish=False,
                )

                logger.info(f"Converted Excel to PDF: {output_path}")
                return

            except Exception as e:
                logger.warning(
                    f"Excel to PDF attempt {attempt + 1}/{retries} failed: {e}"
                )
                if attempt < retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise IntegrationError(
                        f"Excel to PDF conversion failed after {retries} attempts: {e}",
                        integration="office_com",
                        operation="excel_to_pdf",
                        cause=e,
                        fallback_available=True,
                    )
            finally:
                if wb:
                    try:
                        wb.Close(SaveChanges=False)
                    except Exception:
                        pass

    def create_email_draft(
        self,
        recipient: str,
        subject: str,
        body_html: str | None = None,
        body_text: str | None = None,
        attachments: list[Path | str] | None = None,
    ) -> bool:
        """
        Create an email draft in Outlook.

        Args:
            recipient: Recipient email address
            subject: Email subject
            body_html: HTML body (preferred)
            body_text: Plain text body (fallback)
            attachments: List of file paths to attach

        Returns:
            True if draft created successfully

        Raises:
            IntegrationError: If Outlook is not available or draft creation fails
        """
        if not self._com_available:
            raise IntegrationError(
                "Office COM not available",
                integration="outlook",
                operation="create_draft",
            )

        try:
            import pythoncom
            pythoncom.CoInitialize()

            outlook = self._get_outlook_app()

            # Create mail item (0 = olMailItem)
            mail = outlook.CreateItem(0)

            mail.To = recipient
            mail.Subject = subject

            if body_html:
                mail.HTMLBody = body_html
            elif body_text:
                mail.Body = body_text

            # Add attachments
            if attachments:
                for attachment_path in attachments:
                    path = Path(attachment_path).resolve()
                    if path.exists():
                        mail.Attachments.Add(str(path))
                    else:
                        logger.warning(f"Attachment not found: {path}")

            # Save as draft (don't send)
            mail.Save()

            logger.info(f"Created Outlook draft: {subject} to {recipient}")
            return True

        except Exception as e:
            raise IntegrationError(
                f"Failed to create Outlook draft: {e}",
                integration="outlook",
                operation="create_draft",
                cause=e,
                fallback_available=False,
            )

    def cleanup(self) -> None:
        """Clean up COM resources."""
        try:
            if self._word_app:
                try:
                    self._word_app.Quit()
                except Exception:
                    pass
                self._word_app = None

            if self._excel_app:
                try:
                    self._excel_app.Quit()
                except Exception:
                    pass
                self._excel_app = None

            # Note: Don't quit Outlook as user might have it open
            self._outlook_app = None

            logger.debug("Office COM resources cleaned up")

        except Exception as e:
            logger.warning(f"Error during Office COM cleanup: {e}")

    def __del__(self):
        """Destructor - cleanup COM resources."""
        self.cleanup()
