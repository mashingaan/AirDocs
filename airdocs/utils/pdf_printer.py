"""PDF printing utilities using Qt."""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMarginsF, QSizeF, Qt
from PySide6.QtGui import QPainter, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PySide6.QtWidgets import QWidget
from pypdf import PdfReader

from core.app_context import get_context

logger = logging.getLogger("airdocs.utils")


class PDFPrinter:
    """Utility for printing PDF files using Qt."""

    def __init__(self):
        self._context = get_context()
        self._printer_config = self._context.config.get("printer", {})

    def print_with_preview(
        self,
        pdf_path: Path | str,
        parent: Optional[QWidget] = None,
        printer_mode: str = "a4",
        template_info: Optional[dict] = None,
    ) -> bool:
        """
        Show print preview dialog for PDF.

        Args:
            pdf_path: Path to PDF file
            parent: Parent widget for dialog
            printer_mode: "a4" or "label"
            template_info: Optional template info from AWBPDFGenerator.get_template_info()

        Returns:
            True if printed, False if cancelled
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return False

        # Create printer with configuration
        printer = self._create_printer(printer_mode, template_info)

        # Create preview dialog
        preview = QPrintPreviewDialog(printer, parent)
        preview.setWindowTitle(f"Предпросмотр печати: {pdf_path.name}")

        # Connect paint request to render function
        preview.paintRequested.connect(
            lambda p: self._render_pdf(pdf_path, p)
        )

        # Show dialog and return result
        result = preview.exec()
        return result == QPrintPreviewDialog.Accepted

    def print_direct(
        self,
        pdf_path: Path | str,
        parent: Optional[QWidget] = None,
        printer_mode: str = "a4",
        show_dialog: bool = True,
        template_info: Optional[dict] = None,
    ) -> bool:
        """
        Print PDF directly (with optional print dialog).

        Args:
            pdf_path: Path to PDF file
            parent: Parent widget for dialog
            printer_mode: "a4" or "label"
            show_dialog: Show print dialog before printing
            template_info: Optional template info from AWBPDFGenerator.get_template_info()

        Returns:
            True if printed, False if cancelled
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return False

        # Create printer
        printer = self._create_printer(printer_mode, template_info)

        # Show print dialog if requested
        if show_dialog:
            dialog = QPrintDialog(printer, parent)
            dialog.setWindowTitle("Печать")
            if dialog.exec() != QPrintDialog.Accepted:
                return False

        # Render PDF to printer
        self._render_pdf(pdf_path, printer)
        return True

    def print_multiple(
        self,
        pdf_paths: list[Path | str],
        parent: Optional[QWidget] = None,
        printer_mode: str = "a4",
        template_info: Optional[dict] = None,
    ) -> bool:
        """
        Print multiple PDFs (e.g., document set).

        Args:
            pdf_paths: List of PDF file paths
            parent: Parent widget
            printer_mode: "a4" or "label"
            template_info: Optional template info for page configuration

        Returns:
            True if all printed successfully
        """
        if not pdf_paths:
            return False

        # Create printer
        printer = self._create_printer(printer_mode, template_info)

        # Show print dialog once
        dialog = QPrintDialog(printer, parent)
        dialog.setWindowTitle(f"Печать комплекта ({len(pdf_paths)} документов)")
        if dialog.exec() != QPrintDialog.Accepted:
            return False

        # Print all PDFs
        painter = QPainter()
        if not painter.begin(printer):
            logger.error("Failed to start painter")
            return False

        try:
            for i, pdf_path in enumerate(pdf_paths):
                pdf_path = Path(pdf_path)
                if not pdf_path.exists():
                    logger.warning(f"Skipping missing PDF: {pdf_path}")
                    continue

                # New page for each document (except first)
                if i > 0:
                    if not printer.newPage():
                        logger.error("Failed to create new page")
                        break

                # Render PDF pages
                self._render_pdf_to_painter(pdf_path, painter, printer)

        finally:
            painter.end()

        return True

    def _create_printer(self, mode: str = "a4", template_info: Optional[dict] = None) -> QPrinter:
        """Create configured QPrinter instance.
        
        Args:
            mode: Printer mode ("a4" or "label")
            template_info: Optional template info from AWBPDFGenerator.get_template_info()
                           If provided, overrides page_size and orientation from config.
        """
        printer = QPrinter(QPrinter.HighResolution)

        # Get mode config
        mode_config = self._printer_config.get(mode, {})
        options = self._printer_config.get("options", {})

        # Check if template_info provides page dimensions
        if template_info and 'page_size' in template_info:
            # Use template-derived page size
            w, h = template_info['page_size']
            page_size = QPageSize(QSizeF(w, h), QPageSize.Point)
            
            # Determine orientation from template dimensions
            if w > h:
                orientation = QPageLayout.Landscape
            else:
                orientation = QPageLayout.Portrait
            
            # Use template-derived margins or fall back to config
            margins = mode_config.get("margins", [10, 10, 10, 10])
            logger.info(f"Using template-derived page size: {w}x{h} pts, orientation: {orientation}")
        else:
            # Set page size from config
            page_size_str = mode_config.get("page_size", "A4")
            if page_size_str == "A4":
                page_size = QPageSize(QPageSize.A4)
            elif page_size_str == "custom":
                width_mm = mode_config.get("width_mm", 100)
                height_mm = mode_config.get("height_mm", 150)
                page_size = QPageSize(QSizeF(width_mm, height_mm), QPageSize.Millimeter)
            else:
                page_size = QPageSize(QPageSize.A4)

            # Set orientation from config
            orientation_str = mode_config.get("orientation", "portrait")
            orientation = (
                QPageLayout.Landscape
                if orientation_str == "landscape"
                else QPageLayout.Portrait
            )

            # Set margins from config
            margins = mode_config.get("margins", [10, 10, 10, 10])
        margins_f = QMarginsF(*margins)

        # Create page layout
        layout = QPageLayout(page_size, orientation, margins_f, QPageLayout.Millimeter)
        printer.setPageLayout(layout)

        # Set color mode
        color_mode = options.get("color_mode", "grayscale")
        if color_mode == "grayscale":
            printer.setColorMode(QPrinter.GrayScale)
        else:
            printer.setColorMode(QPrinter.Color)

        # Set resolution
        resolution = options.get("resolution", 300)
        printer.setResolution(resolution)

        # Set duplex
        duplex = options.get("duplex", False)
        if duplex:
            printer.setDuplex(QPrinter.DuplexAuto)
        else:
            printer.setDuplex(QPrinter.DuplexNone)

        return printer

    def _render_pdf(self, pdf_path: Path, printer: QPrinter) -> None:
        """Render PDF to printer."""
        painter = QPainter()
        if not painter.begin(printer):
            logger.error("Failed to start painter")
            return

        try:
            self._render_pdf_to_painter(pdf_path, painter, printer)
        finally:
            painter.end()

    def _render_pdf_to_painter(
        self,
        pdf_path: Path,
        painter: QPainter,
        printer: QPrinter,
    ) -> None:
        """Render PDF pages to painter."""
        try:
            reader = PdfReader(pdf_path)
            page_count = len(reader.pages)

            for i, page in enumerate(reader.pages):
                # New page for each PDF page (except first)
                if i > 0:
                    if not printer.newPage():
                        logger.error("Failed to create new page")
                        break

                # Get page dimensions
                media_box = page.mediabox
                page_width = float(media_box.width)
                page_height = float(media_box.height)

                # Get printer page rect
                page_rect = printer.pageRect(QPrinter.DevicePixel)

                # Calculate scaling to fit page
                scale_x = page_rect.width() / page_width
                scale_y = page_rect.height() / page_height
                scale = min(scale_x, scale_y)

                # Center page
                x_offset = (page_rect.width() - page_width * scale) / 2
                y_offset = (page_rect.height() - page_height * scale) / 2

                # Render using PyPDF (convert to image first)
                # Note: This is a simplified approach
                # For production, consider using pdf2image or similar
                from io import BytesIO
                from pypdf import PdfWriter
                from PySide6.QtGui import QImage, QPixmap

                # Extract single page
                writer = PdfWriter()
                writer.add_page(page)
                buffer = BytesIO()
                writer.write(buffer)
                buffer.seek(0)

                # Render PDF using PyMuPDF
                import fitz
                doc = fitz.open(pdf_path)
                pdf_page = doc.load_page(i)
                
                # Get DPI for rendering (use printer resolution)
                dpi = printer.resolution()
                pix = pdf_page.get_pixmap(dpi=dpi)
                
                # Convert to QImage
                img_data = pix.tobytes("png")
                qimage = QImage.fromData(img_data)
                
                # Scale to fit printer page while maintaining aspect ratio
                scaled_image = qimage.scaled(
                    int(page_width * scale),
                    int(page_height * scale),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                
                # Draw the image centered on the page
                painter.save()
                painter.translate(x_offset, y_offset)
                painter.drawImage(0, 0, scaled_image)
                painter.restore()
                
                doc.close()
                
                logger.debug(f"Rendered page {i+1}/{page_count} of {pdf_path.name}")

        except Exception as e:
            logger.error(f"Failed to render PDF {pdf_path}: {e}", exc_info=True)
