# AirDocs - Word Generator
# ================================

import logging
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate

from core.exceptions import GenerationError, TemplateError
from .base_generator import BaseGenerator

logger = logging.getLogger("airdocs.generators")


class WordGenerator(BaseGenerator):
    """
    Generator for Word documents using docxtpl (Jinja2-based templating).

    Uses placeholders in the format: {{ field_name }}

    Supports:
    - Text replacement
    - Tables with loops: {% for item in items %}...{% endfor %}
    - Conditionals: {% if condition %}...{% endif %}
    - Rich text formatting preservation
    """

    TEMPLATE_TYPE = "word"

    def generate(
        self,
        template_name: str,
        data: dict[str, Any],
        output_path: Path | str,
    ) -> None:
        """
        Generate a Word document from template.

        Args:
            template_name: Name of the template (e.g., 'invoice', 'upd', 'act')
            data: Data dictionary with canonical field names
            output_path: Path where to save the generated document

        Raises:
            GenerationError: If generation fails
            TemplateError: If template not found or invalid
        """
        output_path = Path(output_path)

        try:
            # Get template path
            template_path = self.get_template_path(self.TEMPLATE_TYPE, template_name)

            # Prepare context
            context = self.prepare_context(data)

            # Load template
            doc = DocxTemplate(template_path)

            # Render
            doc.render(context)

            # Ensure output directory exists
            self.ensure_output_dir(output_path)

            # Save
            doc.save(output_path)

            logger.info(f"Generated Word document: {output_path}")

        except TemplateError:
            raise
        except Exception as e:
            self._handle_generation_error(e, template_name, output_path)

    def generate_from_file(
        self,
        template_path: Path | str,
        data: dict[str, Any],
        output_path: Path | str,
    ) -> None:
        """
        Generate Word document from a specific template file path.

        Args:
            template_path: Full path to the template file
            data: Data dictionary
            output_path: Path where to save
        """
        template_path = Path(template_path)
        output_path = Path(output_path)

        if not template_path.exists():
            raise TemplateError(
                f"Template file not found: {template_path}",
                template_path=str(template_path),
            )

        try:
            context = self.prepare_context(data)
            doc = DocxTemplate(template_path)
            doc.render(context)
            self.ensure_output_dir(output_path)
            doc.save(output_path)
            logger.info(f"Generated Word document from custom template: {output_path}")
        except Exception as e:
            self._handle_generation_error(e, str(template_path), output_path)

    def get_template_fields(self, template_name: str) -> list[str]:
        """
        Get list of placeholder fields in a template.

        Args:
            template_name: Name of the template

        Returns:
            List of field names found in template
        """
        try:
            template_path = self.get_template_path(self.TEMPLATE_TYPE, template_name)
            doc = DocxTemplate(template_path)
            # undeclared_template_variables returns the variable names
            return list(doc.undeclared_template_variables)
        except Exception as e:
            logger.warning(f"Could not extract fields from template: {e}")
            return []

    def validate_template(self, template_name: str) -> tuple[bool, str]:
        """
        Validate a template by checking if it can be loaded.

        Args:
            template_name: Name of the template

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            template_path = self.get_template_path(self.TEMPLATE_TYPE, template_name)
            DocxTemplate(template_path)
            return True, ""
        except Exception as e:
            return False, str(e)

    def prepare_context(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Prepare context with Word-specific handling.

        Converts special values for proper Word rendering.
        """
        context = super().prepare_context(data)

        # Handle multiline text - replace \n with Word line breaks
        for key, value in context.items():
            if isinstance(value, str) and "\n" in value:
                # For docxtpl, newlines in text are preserved
                pass

        return context
