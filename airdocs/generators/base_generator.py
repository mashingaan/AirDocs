# AirDocs - Base Generator
# ================================

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.app_context import get_context
from core.exceptions import GenerationError, TemplateError

logger = logging.getLogger("airdocs.generators")


class BaseGenerator(ABC):
    """
    Abstract base class for document generators.

    Provides common functionality:
    - Template loading
    - Context preparation
    - Error handling
    """

    def __init__(self):
        self._context = get_context()
        self._logger = logger

    @property
    def context(self):
        """Get application context."""
        return self._context

    def get_template_path(self, template_type: str, template_name: str) -> Path:
        """
        Get path to a template file.

        Args:
            template_type: Type of template ('word', 'excel', 'pdf')
            template_name: Name of the template

        Returns:
            Path to template file

        Raises:
            TemplateError: If template not found
        """
        try:
            path = self._context.get_template_path(template_type, template_name)
            if not path.exists():
                raise TemplateError(
                    f"Template file not found: {path}",
                    template_path=str(path),
                )
            return path
        except Exception as e:
            raise TemplateError(
                f"Error getting template path: {e}",
                template_path=f"{template_type}/{template_name}",
                cause=e if isinstance(e, Exception) else None,
            )

    def prepare_context(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Prepare data context for template rendering.

        Applies formatting and adds computed fields.

        Args:
            data: Raw data dictionary

        Returns:
            Prepared context dictionary
        """
        # Make a copy to avoid modifying original
        context = data.copy()

        # Ensure all values are strings or have proper string representation
        for key, value in context.items():
            if value is None:
                context[key] = ""
            elif isinstance(value, (int, float)):
                # Keep numbers as-is for templates that need them
                pass
            elif not isinstance(value, str):
                context[key] = str(value)

        return context

    def ensure_output_dir(self, output_path: Path) -> None:
        """Ensure the output directory exists."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def generate(
        self,
        template_name: str,
        data: dict[str, Any],
        output_path: Path,
    ) -> None:
        """
        Generate a document.

        Args:
            template_name: Name of the template to use
            data: Data for template rendering
            output_path: Path where to save generated document

        Raises:
            GenerationError: If generation fails
        """
        pass

    def _handle_generation_error(
        self,
        error: Exception,
        template_name: str,
        output_path: Path,
    ) -> None:
        """
        Handle and re-raise generation errors with proper logging.

        Args:
            error: Original exception
            template_name: Name of template being processed
            output_path: Target output path
        """
        self._logger.error(
            f"Generation failed for template '{template_name}' "
            f"to '{output_path}': {error}",
            exc_info=True,
        )
        raise GenerationError(
            f"Failed to generate document: {error}",
            document_type=template_name,
            template_path=template_name,
            cause=error,
        )
