# AirDocs - Custom Exceptions
# ===================================

from typing import Any


class AWBDispatcherError(Exception):
    """Base exception for all AWB Dispatcher errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} [{details_str}]"
        return self.message


class ValidationError(AWBDispatcherError):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        expected: str | None = None,
    ):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]  # Truncate long values
        if expected:
            details["expected"] = expected
        super().__init__(message, details)
        self.field = field
        self.value = value
        self.expected = expected


class GenerationError(AWBDispatcherError):
    """Raised when document generation fails."""

    def __init__(
        self,
        message: str,
        document_type: str | None = None,
        template_path: str | None = None,
        cause: Exception | None = None,
    ):
        details = {}
        if document_type:
            details["document_type"] = document_type
        if template_path:
            details["template_path"] = template_path
        if cause:
            details["cause"] = str(cause)
        super().__init__(message, details)
        self.document_type = document_type
        self.template_path = template_path
        self.cause = cause


class DatabaseError(AWBDispatcherError):
    """Raised when database operations fail."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        table: str | None = None,
        cause: Exception | None = None,
    ):
        details = {}
        if operation:
            details["operation"] = operation
        if table:
            details["table"] = table
        if cause:
            details["cause"] = str(cause)
        super().__init__(message, details)
        self.operation = operation
        self.table = table
        self.cause = cause


class IntegrationError(AWBDispatcherError):
    """Raised when external integration fails (Office COM, LibreOffice, AWB Editor)."""

    def __init__(
        self,
        message: str,
        integration: str | None = None,
        operation: str | None = None,
        cause: Exception | None = None,
        fallback_available: bool = False,
    ):
        details = {}
        if integration:
            details["integration"] = integration
        if operation:
            details["operation"] = operation
        if cause:
            details["cause"] = str(cause)
        details["fallback_available"] = fallback_available
        super().__init__(message, details)
        self.integration = integration
        self.operation = operation
        self.cause = cause
        self.fallback_available = fallback_available


class ConfigurationError(AWBDispatcherError):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        config_file: str | None = None,
        key: str | None = None,
    ):
        details = {}
        if config_file:
            details["config_file"] = config_file
        if key:
            details["key"] = key
        super().__init__(message, details)
        self.config_file = config_file
        self.key = key


class TemplateError(AWBDispatcherError):
    """Raised when template processing fails."""

    def __init__(
        self,
        message: str,
        template_path: str | None = None,
        placeholder: str | None = None,
        cause: Exception | None = None,
    ):
        details = {}
        if template_path:
            details["template_path"] = template_path
        if placeholder:
            details["placeholder"] = placeholder
        if cause:
            details["cause"] = str(cause)
        super().__init__(message, details)
        self.template_path = template_path
        self.placeholder = placeholder
        self.cause = cause


class FileOperationError(AWBDispatcherError):
    """Raised when file operations fail."""

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        operation: str | None = None,
        cause: Exception | None = None,
    ):
        details = {}
        if file_path:
            details["file_path"] = file_path
        if operation:
            details["operation"] = operation
        if cause:
            details["cause"] = str(cause)
        super().__init__(message, details)
        self.file_path = file_path
        self.operation = operation
        self.cause = cause


class ConversionError(AWBDispatcherError):
    """Raised when document conversion fails (e.g., DOCX -> PDF)."""

    def __init__(
        self,
        message: str,
        source_path: str | None = None,
        target_format: str | None = None,
        method: str | None = None,
        cause: Exception | None = None,
    ):
        details = {}
        if source_path:
            details["source_path"] = source_path
        if target_format:
            details["target_format"] = target_format
        if method:
            details["method"] = method
        if cause:
            details["cause"] = str(cause)
        super().__init__(message, details)
        self.source_path = source_path
        self.target_format = target_format
        self.method = method
        self.cause = cause
