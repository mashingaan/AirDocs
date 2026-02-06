# AirDocs - Field Mapper
# ==============================

import logging
from datetime import date, datetime
from typing import Any

from num2words import num2words

from core.app_context import get_context

logger = logging.getLogger("airdocs.utils")


class FieldMapper:
    """
    Utility for mapping fields between different representations.

    Uses field_mapping.yaml as the single source of truth.

    Responsibilities:
    - Convert UI values to database format
    - Convert database values to template context
    - Format values for display
    - Add computed/derived fields
    """

    def __init__(self):
        self._context = get_context()

    @property
    def fields(self) -> dict[str, Any]:
        """Get field definitions from config."""
        return self._context.fields

    def get_field_config(self, field_name: str) -> dict[str, Any] | None:
        """Get configuration for a specific field."""
        return self.fields.get(field_name)

    def get_ui_label(self, field_name: str, language: str = "ru") -> str:
        """
        Get UI label for a field.

        Args:
            field_name: Canonical field name
            language: Language code (ru, en)

        Returns:
            UI label string
        """
        config = self.get_field_config(field_name)
        if not config:
            return field_name

        if language == "en":
            return config.get("ui_label_en", config.get("ui_label", field_name))
        return config.get("ui_label", field_name)

    def get_word_placeholder(self, field_name: str) -> str | None:
        """Get Word template placeholder for a field."""
        config = self.get_field_config(field_name)
        if config:
            return config.get("word_placeholder")
        return None

    def get_awb_field(self, field_name: str) -> str | None:
        """Get AWB AcroForm field name for a field."""
        config = self.get_field_config(field_name)
        if config:
            return config.get("awb_field")
        return None

    def format_value(
        self,
        field_name: str,
        value: Any,
        format_type: str = "display",
    ) -> str:
        """
        Format a value according to field configuration.

        Args:
            field_name: Canonical field name
            value: Value to format
            format_type: Format type (display, db, word)

        Returns:
            Formatted string
        """
        if value is None:
            return ""

        config = self.get_field_config(field_name)
        if not config:
            return str(value)

        field_type = config.get("type", "string")
        format_config = config.get("format", {})

        if field_type == "date":
            return self._format_date(value, format_config, format_type)
        elif field_type == "float":
            return self._format_float(value, format_config)
        elif field_type == "integer":
            return str(int(value))
        else:
            return str(value)

    def _format_date(
        self,
        value: Any,
        format_config: dict,
        format_type: str,
    ) -> str:
        """Format date value."""
        if isinstance(value, str):
            try:
                value = date.fromisoformat(value)
            except ValueError:
                return value

        if isinstance(value, datetime):
            value = value.date()

        if not isinstance(value, date):
            return str(value)

        # Get format string
        if format_type == "db":
            fmt = format_config.get("db", "%Y-%m-%d")
        elif format_type == "word":
            fmt = format_config.get("word", format_config.get("display", "%d.%m.%Y"))
        else:
            fmt = format_config.get("display", "%d.%m.%Y")

        return value.strftime(fmt)

    def _format_float(self, value: Any, format_config: dict) -> str:
        """Format float value."""
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            return str(value)

        decimal_places = format_config.get("decimal_places", 2)
        return f"{float_value:.{decimal_places}f}"

    def build_template_context(
        self,
        data: dict[str, Any],
        include_computed: bool = True,
    ) -> dict[str, Any]:
        """
        Build a complete template context from data.

        Args:
            data: Dictionary with canonical field names
            include_computed: Whether to include computed fields

        Returns:
            Template context dictionary with all placeholders
        """
        context = {}

        # Add all provided fields
        for field_name, value in data.items():
            # Format value for template
            formatted = self.format_value(field_name, value, "word")
            context[field_name] = formatted

        # Add computed fields
        if include_computed:
            context.update(self._get_computed_fields(data))

        return context

    def _get_computed_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """Get computed/derived fields."""
        computed = {}

        # Current date
        today = date.today()
        computed["current_date"] = today.strftime("%d.%m.%Y")
        computed["current_year"] = today.year

        # Amount in words (if invoice_amount present)
        if "invoice_amount" in data and data["invoice_amount"]:
            try:
                amount = float(data["invoice_amount"])
                computed["invoice_amount_words"] = self._amount_to_words(amount)
            except (ValueError, TypeError):
                pass

        # Document date (defaults to current date)
        if "document_date" not in data:
            computed["document_date"] = today.strftime("%d.%m.%Y")

        return computed

    def _amount_to_words(self, amount: float, currency: str = "RUB") -> str:
        """
        Convert numeric amount to words (Russian).

        Args:
            amount: Amount to convert
            currency: Currency code

        Returns:
            Amount in words
        """
        try:
            rubles = int(amount)
            kopeks = int(round((amount - rubles) * 100))

            # Convert rubles to words
            rubles_word = num2words(rubles, lang="ru")

            # Determine ruble word form
            ruble_form = self._get_ruble_form(rubles)

            # Determine kopek word form
            kopek_form = self._get_kopek_form(kopeks)

            return f"{rubles_word.capitalize()} {ruble_form} {kopeks:02d} {kopek_form}"

        except Exception as e:
            logger.warning(f"Could not convert amount to words: {e}")
            return f"{amount:.2f} руб."

    def _get_ruble_form(self, n: int) -> str:
        """Get correct Russian form of 'рубль'."""
        n = abs(n) % 100
        if 11 <= n <= 19:
            return "рублей"
        n = n % 10
        if n == 1:
            return "рубль"
        if 2 <= n <= 4:
            return "рубля"
        return "рублей"

    def _get_kopek_form(self, n: int) -> str:
        """Get correct Russian form of 'копейка'."""
        n = abs(n) % 100
        if 11 <= n <= 19:
            return "копеек"
        n = n % 10
        if n == 1:
            return "копейка"
        if 2 <= n <= 4:
            return "копейки"
        return "копеек"

    def map_to_db(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Map field values to database format.

        Args:
            data: Dictionary with canonical field names

        Returns:
            Dictionary with database-formatted values
        """
        result = {}

        for field_name, value in data.items():
            config = self.get_field_config(field_name)
            if not config:
                result[field_name] = value
                continue

            field_type = config.get("type", "string")

            if field_type == "date" and isinstance(value, date):
                result[field_name] = value.isoformat()
            elif field_type == "boolean":
                result[field_name] = 1 if value else 0
            else:
                result[field_name] = value

        return result

    def map_from_db(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Map database values to Python types.

        Args:
            data: Dictionary with database values

        Returns:
            Dictionary with Python-typed values
        """
        result = {}

        for field_name, value in data.items():
            config = self.get_field_config(field_name)
            if not config:
                result[field_name] = value
                continue

            field_type = config.get("type", "string")

            if field_type == "date" and isinstance(value, str):
                try:
                    result[field_name] = date.fromisoformat(value)
                except ValueError:
                    result[field_name] = value
            elif field_type == "boolean":
                result[field_name] = bool(value)
            else:
                result[field_name] = value

        return result

    def get_required_fields(self) -> list[str]:
        """Get list of required field names."""
        return [
            name for name, config in self.fields.items()
            if config.get("required", False)
        ]

    def get_fields_for_document_type(self, document_type: str) -> list[str]:
        """
        Get list of fields relevant for a document type.

        Args:
            document_type: Type of document (awb, invoice, etc.)

        Returns:
            List of relevant field names
        """
        relevant = []

        for name, config in self.fields.items():
            # Check if field has word_placeholder (for Word docs)
            # or awb_field (for AWB)
            if document_type == "awb":
                if config.get("awb_field"):
                    relevant.append(name)
            else:
                if config.get("word_placeholder"):
                    relevant.append(name)

        return relevant
