# AirDocs - AWB PDF Generator
# ===================================

import io
import logging
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.app_context import get_context
from core.exceptions import GenerationError, TemplateError
from data.repositories import CalibrationRepository

logger = logging.getLogger("airdocs.generators")


class AWBPDFGenerator:
    """
    Generator for AWB PDF documents.

    Primary strategy: OVERLAY (ReportLab + PyPDF merge)
    - Creates overlay PDF with text at calibrated coordinates
    - Merges overlay onto blank AWB template

    Secondary strategy: AcroForm (if template supports it)
    - Fills AcroForm fields directly (rarely available)

    The strategy is automatically selected based on template analysis.
    """

    TEMPLATE_TYPE = "pdf"

    def __init__(self):
        self._context = get_context()
        self._calibration_repo = CalibrationRepository()
        self._logger = logger

        # Try to register a font that supports Cyrillic
        self._font_name = "Helvetica"  # Default fallback
        self._try_register_cyrillic_font()

    def _try_register_cyrillic_font(self) -> None:
        """Try to register a font that supports Cyrillic characters."""
        # Try common system fonts
        font_paths = [
            # Windows fonts
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
        ]

        for font_path in font_paths:
            if Path(font_path).exists():
                try:
                    pdfmetrics.registerFont(TTFont("CyrillicFont", font_path))
                    self._font_name = "CyrillicFont"
                    logger.debug(f"Registered Cyrillic font from: {font_path}")
                    return
                except Exception as e:
                    logger.debug(f"Could not register font {font_path}: {e}")

        logger.warning(
            "Could not register Cyrillic font. "
            "AWB PDF may not display Cyrillic characters correctly."
        )

    def generate(
        self,
        data: dict[str, Any],
        output_path: Path | str,
        template_name: str = "awb_blank",
    ) -> None:
        """
        Generate AWB PDF using the best available strategy.

        Args:
            data: Data dictionary with canonical field names
            output_path: Path where to save the generated PDF
            template_name: Name of the AWB template (default: awb_blank)

        Raises:
            GenerationError: If generation fails
        """
        output_path = Path(output_path)

        try:
            # Get template path
            template_path = self._get_template_path(template_name)

            # Check template type and choose strategy
            has_acroform = self._check_acroform(template_path)

            if has_acroform:
                logger.info("AWB template has AcroForm - attempting AcroForm fill")
                try:
                    self._generate_acroform(data, template_path, output_path)
                    return
                except Exception as e:
                    logger.warning(
                        f"AcroForm fill failed, falling back to overlay: {e}"
                    )

            # Primary strategy: Overlay
            logger.info("Using overlay strategy for AWB PDF generation")
            self._generate_overlay(data, template_path, output_path)

        except TemplateError:
            raise
        except Exception as e:
            logger.error(f"AWB PDF generation failed: {e}", exc_info=True)
            raise GenerationError(
                f"Failed to generate AWB PDF: {e}",
                document_type="awb",
                cause=e,
            )

    def _get_template_path(self, template_name: str) -> Path:
        """Get path to AWB template PDF."""
        try:
            path = self._context.get_template_path(self.TEMPLATE_TYPE, template_name)
            if not path.exists():
                raise TemplateError(
                    f"AWB template not found: {path}",
                    template_path=str(path),
                )
            return path
        except Exception as e:
            if isinstance(e, TemplateError):
                raise
            raise TemplateError(
                f"Error getting AWB template path: {e}",
                template_path=template_name,
                cause=e if isinstance(e, Exception) else None,
            )

    def _check_acroform(self, template_path: Path) -> bool:
        """
        Check if PDF template has AcroForm fields.

        Args:
            template_path: Path to PDF template

        Returns:
            True if template has AcroForm fields
        """
        try:
            reader = PdfReader(template_path)

            # Check for /AcroForm in the catalog
            if reader.trailer and "/Root" in reader.trailer:
                root = reader.trailer["/Root"]
                if hasattr(root, "get_object"):
                    root = root.get_object()
                if "/AcroForm" in root:
                    acroform = root["/AcroForm"]
                    if hasattr(acroform, "get_object"):
                        acroform = acroform.get_object()
                    if "/Fields" in acroform:
                        fields = acroform["/Fields"]
                        if len(fields) > 0:
                            logger.debug(f"Found {len(fields)} AcroForm fields")
                            return True

            # Alternative check using get_fields
            fields = reader.get_fields()
            if fields and len(fields) > 0:
                logger.debug(f"Found {len(fields)} form fields via get_fields()")
                return True

            return False

        except Exception as e:
            logger.debug(f"AcroForm check failed: {e}")
            return False

    def _generate_acroform(
        self,
        data: dict[str, Any],
        template_path: Path,
        output_path: Path,
    ) -> None:
        """
        Generate AWB PDF by filling AcroForm fields.

        Args:
            data: Data dictionary
            template_path: Path to template PDF
            output_path: Path where to save
        """
        reader = PdfReader(template_path)
        writer = PdfWriter()

        # Add all pages
        for page in reader.pages:
            writer.add_page(page)

        # Get field mapping from config
        field_mapping = self._context.fields

        # Build form field values
        form_values = {}
        for canonical_key, value in data.items():
            # Look up AWB field name
            if canonical_key in field_mapping:
                awb_field = field_mapping[canonical_key].get("awb_field")
                if awb_field:
                    form_values[awb_field] = str(value) if value else ""

        # Update form fields
        if form_values:
            writer.update_page_form_field_values(
                writer.pages[0],
                form_values,
            )

        # Ensure output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save
        with open(output_path, "wb") as f:
            writer.write(f)

        logger.info(f"Generated AWB PDF via AcroForm: {output_path}")

    def _generate_overlay(
        self,
        data: dict[str, Any],
        template_path: Path,
        output_path: Path,
    ) -> None:
        """
        Generate AWB PDF using overlay strategy.

        Creates text overlay and merges with template.

        Args:
            data: Data dictionary
            template_path: Path to template PDF
            output_path: Path where to save
        """
        # Read template to get page size
        reader = PdfReader(template_path)
        template_page = reader.pages[0]

        # Get page dimensions
        media_box = template_page.mediabox
        page_width = float(media_box.width)
        page_height = float(media_box.height)

        # Get calibration data (from DB or config)
        coordinates = self._get_coordinates()

        # Get overlay config
        overlay_config = self._context.get_awb_overlay_config()
        font_size = overlay_config.get("font_size", 10)
        font_size_small = overlay_config.get("font_size_small", 8)

        # Create overlay PDF in memory
        overlay_buffer = io.BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

        # Set font
        c.setFont(self._font_name, font_size)

        # Draw text at calibrated coordinates
        for field_name, (x, y) in coordinates.items():
            value = data.get(field_name, "")
            if value:
                # Use smaller font for longer text
                text_str = str(value)
                if len(text_str) > 30:
                    c.setFont(self._font_name, font_size_small)
                else:
                    c.setFont(self._font_name, font_size)

                c.drawString(x, y, text_str)

        c.save()
        overlay_buffer.seek(0)

        # Merge overlay with template
        overlay_reader = PdfReader(overlay_buffer)
        overlay_page = overlay_reader.pages[0]

        writer = PdfWriter()

        # Merge overlay onto template page
        template_page.merge_page(overlay_page)
        writer.add_page(template_page)

        # Add remaining pages from template (if any)
        for page in reader.pages[1:]:
            writer.add_page(page)

        # Ensure output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save
        with open(output_path, "wb") as f:
            writer.write(f)

        logger.info(f"Generated AWB PDF via overlay: {output_path}")

    def _get_coordinates(self) -> dict[str, tuple[float, float]]:
        """
        Get field coordinates for overlay.

        First tries database calibration, then falls back to config.

        Returns:
            Dictionary of field_name -> (x, y) coordinates
        """
        # Try database calibration first
        try:
            db_coords = self._calibration_repo.get_as_dict("awb_blank")
            if db_coords:
                logger.debug("Using calibrated coordinates from database")
                return db_coords
        except Exception as e:
            logger.debug(f"Could not load calibration from DB: {e}")

        # Fall back to config
        config_coords = self._context.get_awb_overlay_config().get("coordinates", {})
        if config_coords:
            # Convert from config format (list) to tuple
            return {
                field: tuple(coords) if isinstance(coords, list) else coords
                for field, coords in config_coords.items()
            }

        # Default coordinates if nothing configured
        logger.warning("No coordinate calibration found, using defaults")
        return {
            "awb_number": (380.0, 550.0),
            "shipment_date": (380.0, 530.0),
            "shipper_name": (50.0, 480.0),
            "consignee_name": (50.0, 380.0),
            "weight_kg": (600.0, 350.0),
            "pieces": (650.0, 350.0),
        }

    def generate_with_coordinates(
        self,
        data: dict[str, Any],
        output_path: Path | str,
        coordinates: dict[str, dict],
        template_name: str = "awb_blank",
    ) -> None:
        """
        Generate AWB PDF with explicit coordinates (for calibration testing).

        Args:
            data: Data dictionary with canonical field names
            output_path: Path where to save the generated PDF
            coordinates: Dictionary of field_name -> {x, y, font_size}
            template_name: Name of the AWB template
        """
        output_path = Path(output_path)
        template_path = self._get_template_path(template_name)

        # Read template
        reader = PdfReader(template_path)
        template_page = reader.pages[0]
        media_box = template_page.mediabox
        page_width = float(media_box.width)
        page_height = float(media_box.height)

        # Create overlay
        overlay_buffer = io.BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

        # Draw text at specified coordinates
        for field_name, coord_info in coordinates.items():
            value = data.get(field_name, "")
            if value:
                x = coord_info.get("x", 0) * 2.83465  # mm to points
                y = coord_info.get("y", 0) * 2.83465  # mm to points
                font_size = coord_info.get("font_size", 10)

                c.setFont(self._font_name, font_size)
                c.drawString(x, y, str(value))

        c.save()
        overlay_buffer.seek(0)

        # Merge
        overlay_reader = PdfReader(overlay_buffer)
        overlay_page = overlay_reader.pages[0]
        template_page.merge_page(overlay_page)

        writer = PdfWriter()
        writer.add_page(template_page)

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            writer.write(f)

        logger.info(f"Generated calibration test PDF: {output_path}")

    def get_template_info(self, template_name: str = "awb_blank") -> dict[str, Any]:
        """
        Get information about an AWB template.

        Returns:
            Dictionary with template info:
            - path: Path to template
            - has_acroform: Whether template has AcroForm
            - page_size: (width, height) in points
            - acroform_fields: List of field names if AcroForm
        """
        try:
            template_path = self._get_template_path(template_name)
            reader = PdfReader(template_path)
            page = reader.pages[0]
            media_box = page.mediabox

            info = {
                "path": str(template_path),
                "has_acroform": self._check_acroform(template_path),
                "page_size": (float(media_box.width), float(media_box.height)),
                "page_count": len(reader.pages),
                "acroform_fields": [],
            }

            if info["has_acroform"]:
                fields = reader.get_fields()
                if fields:
                    info["acroform_fields"] = list(fields.keys())

            return info

        except Exception as e:
            logger.error(f"Could not get template info: {e}")
            return {
                "path": template_name,
                "has_acroform": False,
                "page_size": (842, 595),  # A4 landscape default
                "page_count": 0,
                "acroform_fields": [],
                "error": str(e),
            }
