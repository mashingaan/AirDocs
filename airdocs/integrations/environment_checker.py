# AirDocs - Environment Checker
# =====================================

import logging
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.app_context import get_context

logger = logging.getLogger("airdocs.integrations")


@dataclass
class ComponentStatus:
    """Status of a single component."""

    name: str
    available: bool
    version: str | None = None
    path: str | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def message(self) -> str | None:
        """Alias for error (used by UI)."""
        return self.error

    @property
    def status_text(self) -> str:
        """Get human-readable status text."""
        if self.available:
            if self.version:
                return f"Доступен ({self.version})"
            return "Доступен"
        if self.error:
            return f"Недоступен: {self.error}"
        return "Недоступен"

    @property
    def status_color(self) -> str:
        """Get color for status display."""
        return "#00AA00" if self.available else "#CC0000"


@dataclass
class EnvironmentStatus:
    """Complete environment status report."""

    checked_at: datetime = field(default_factory=datetime.now)
    python_version: str = ""
    platform_info: str = ""
    components: dict[str, ComponentStatus] = field(default_factory=dict)

    @property
    def office(self) -> ComponentStatus:
        """Get Microsoft Office status (alias for UI compatibility)."""
        return self.components.get("ms_office", ComponentStatus(
            name="Microsoft Office", available=False, error="Not checked"
        ))

    @property
    def libreoffice(self) -> ComponentStatus:
        """Get LibreOffice status (alias for UI compatibility)."""
        return self.components.get("libreoffice", ComponentStatus(
            name="LibreOffice", available=False, error="Not checked"
        ))

    @property
    def awb_editor(self) -> ComponentStatus:
        """Get AWB Editor status (alias for UI compatibility)."""
        return self.components.get("awb_editor", ComponentStatus(
            name="AWB Editor", available=False, error="Not checked"
        ))

    @property
    def all_available(self) -> bool:
        """Check if all components are available."""
        return all(c.available for c in self.components.values())

    @property
    def pdf_conversion_available(self) -> bool:
        """Check if PDF conversion is possible (Office OR LibreOffice)."""
        office = self.components.get("ms_office")
        libre = self.components.get("libreoffice")
        return (office and office.available) or (libre and libre.available)

    def get_warnings(self) -> list[str]:
        """Get list of warning messages for unavailable components."""
        warnings = []

        if not self.pdf_conversion_available:
            warnings.append(
                "Конвертация в PDF недоступна. "
                "Установите Microsoft Office или LibreOffice."
            )

        for name, component in self.components.items():
            if not component.available and component.error:
                warnings.append(f"{component.name}: {component.error}")

        return warnings


class EnvironmentChecker:
    """
    Checks environment for required and optional components.

    Checks:
    - Microsoft Office (Word, Excel, Outlook)
    - LibreOffice
    - AWB Editor (if configured)
    - Required Python packages

    Provides diagnostic information for the "Environment Diagnostics" screen.
    """

    def __init__(self):
        self._context = get_context()
        self._status: EnvironmentStatus | None = None

    def check_all(self, force_refresh: bool = False) -> EnvironmentStatus:
        """
        Run all environment checks.

        Args:
            force_refresh: Force re-check even if cached status exists

        Returns:
            EnvironmentStatus with all component statuses
        """
        if self._status and not force_refresh:
            return self._status

        status = EnvironmentStatus(
            python_version=f"Python {sys.version}",
            platform_info=f"{platform.system()} {platform.release()} ({platform.machine()})",
        )

        # Check all components
        status.components["ms_office"] = self._check_ms_office()
        status.components["ms_word"] = self._check_ms_word()
        status.components["ms_excel"] = self._check_ms_excel()
        status.components["ms_outlook"] = self._check_ms_outlook()
        status.components["libreoffice"] = self._check_libreoffice()
        status.components["awb_editor"] = self._check_awb_editor()
        status.components["pywin32"] = self._check_pywin32()

        self._status = status
        logger.info("Environment check completed")

        return status

    def _check_ms_office(self) -> ComponentStatus:
        """Check if Microsoft Office is available."""
        try:
            from integrations.office_com import OfficeCOMIntegration
            office = OfficeCOMIntegration()

            if office.is_available():
                version = office.get_version()
                return ComponentStatus(
                    name="Microsoft Office",
                    available=True,
                    version=version,
                    details={"role": "Primary PDF conversion"},
                )
            else:
                return ComponentStatus(
                    name="Microsoft Office",
                    available=False,
                    error="Office not installed or COM not available",
                )

        except Exception as e:
            return ComponentStatus(
                name="Microsoft Office",
                available=False,
                error=str(e),
            )

    def _check_ms_word(self) -> ComponentStatus:
        """Check if Microsoft Word is available."""
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            version = word.Version
            word.Quit()

            return ComponentStatus(
                name="Microsoft Word",
                available=True,
                version=version,
            )

        except ImportError:
            return ComponentStatus(
                name="Microsoft Word",
                available=False,
                error="pywin32 not installed",
            )
        except Exception as e:
            return ComponentStatus(
                name="Microsoft Word",
                available=False,
                error=str(e),
            )

    def _check_ms_excel(self) -> ComponentStatus:
        """Check if Microsoft Excel is available."""
        try:
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            version = excel.Version
            excel.Quit()

            return ComponentStatus(
                name="Microsoft Excel",
                available=True,
                version=version,
            )

        except ImportError:
            return ComponentStatus(
                name="Microsoft Excel",
                available=False,
                error="pywin32 not installed",
            )
        except Exception as e:
            return ComponentStatus(
                name="Microsoft Excel",
                available=False,
                error=str(e),
            )

    def _check_ms_outlook(self) -> ComponentStatus:
        """Check if Microsoft Outlook is available."""
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            version = outlook.Version

            return ComponentStatus(
                name="Microsoft Outlook",
                available=True,
                version=version,
                details={"note": "Used for email drafts"},
            )

        except ImportError:
            return ComponentStatus(
                name="Microsoft Outlook",
                available=False,
                error="pywin32 not installed",
            )
        except Exception as e:
            return ComponentStatus(
                name="Microsoft Outlook",
                available=False,
                error=str(e),
            )

    def _check_libreoffice(self) -> ComponentStatus:
        """Check if LibreOffice is available."""
        try:
            from integrations.libreoffice import LibreOfficeIntegration
            libre = LibreOfficeIntegration()

            if libre.is_available():
                version = libre.get_version()
                path = libre.get_path()
                return ComponentStatus(
                    name="LibreOffice",
                    available=True,
                    version=version,
                    path=str(path) if path else None,
                    details={"role": "Fallback PDF conversion"},
                )
            else:
                return ComponentStatus(
                    name="LibreOffice",
                    available=False,
                    error="LibreOffice not installed",
                )

        except Exception as e:
            return ComponentStatus(
                name="LibreOffice",
                available=False,
                error=str(e),
            )

    def _check_awb_editor(self) -> ComponentStatus:
        """Check if AWB Editor is configured and available."""
        config = self._context.get_awb_editor_config()

        if not config.get("enabled", False):
            return ComponentStatus(
                name="AWB Editor",
                available=False,
                error="Не настроен (AWB Editor integration disabled)",
                details={"configured": False},
            )

        exe_path = config.get("executable_path", "")
        if not exe_path:
            return ComponentStatus(
                name="AWB Editor",
                available=False,
                error="Путь к исполняемому файлу не указан",
                details={"configured": True},
            )

        path = Path(exe_path)
        if not path.exists():
            return ComponentStatus(
                name="AWB Editor",
                available=False,
                path=str(path),
                error=f"Файл не найден: {path}",
                details={"configured": True},
            )

        return ComponentStatus(
            name="AWB Editor",
            available=True,
            path=str(path),
            details={
                "configured": True,
                "import_format": config.get("import_format", "csv"),
            },
        )

    def _check_pywin32(self) -> ComponentStatus:
        """Check if pywin32 is installed."""
        try:
            import win32com.client
            import pythoncom
            return ComponentStatus(
                name="pywin32 (COM)",
                available=True,
                details={"note": "Required for Office COM automation"},
            )
        except ImportError:
            return ComponentStatus(
                name="pywin32 (COM)",
                available=False,
                error="Package not installed: pip install pywin32",
            )

    def get_pdf_conversion_status(self) -> dict[str, Any]:
        """
        Get summary of PDF conversion capabilities.

        Returns:
            Dictionary with PDF conversion status:
            - available: bool
            - primary_method: str or None
            - fallback_method: str or None
            - warnings: list of warnings
        """
        status = self.check_all()

        office = status.components.get("ms_office")
        libre = status.components.get("libreoffice")

        result = {
            "available": status.pdf_conversion_available,
            "primary_method": None,
            "fallback_method": None,
            "warnings": [],
        }

        if office and office.available:
            result["primary_method"] = "Microsoft Office (COM)"
            if libre and libre.available:
                result["fallback_method"] = "LibreOffice"
        elif libre and libre.available:
            result["primary_method"] = "LibreOffice"
            result["warnings"].append(
                "Microsoft Office недоступен, используется LibreOffice"
            )
        else:
            result["warnings"].append(
                "Конвертация в PDF недоступна! Установите Microsoft Office или LibreOffice."
            )

        return result

    def generate_report(self) -> str:
        """
        Generate a text report of environment status.

        Returns:
            Formatted text report
        """
        status = self.check_all()

        lines = [
            "=" * 60,
            "ДИАГНОСТИКА ОКРУЖЕНИЯ",
            "=" * 60,
            f"Дата проверки: {status.checked_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Python: {status.python_version}",
            f"Платформа: {status.platform_info}",
            "",
            "-" * 60,
            "КОМПОНЕНТЫ:",
            "-" * 60,
        ]

        for name, component in status.components.items():
            icon = "✓" if component.available else "✗"
            lines.append(f"  {icon} {component.name}: {component.status_text}")
            if component.path:
                lines.append(f"      Путь: {component.path}")
            if component.details:
                for key, value in component.details.items():
                    lines.append(f"      {key}: {value}")

        lines.extend([
            "",
            "-" * 60,
            "КОНВЕРТАЦИЯ PDF:",
            "-" * 60,
        ])

        pdf_status = self.get_pdf_conversion_status()
        if pdf_status["available"]:
            lines.append(f"  Основной метод: {pdf_status['primary_method']}")
            if pdf_status["fallback_method"]:
                lines.append(f"  Резервный метод: {pdf_status['fallback_method']}")
        else:
            lines.append("  ⚠ PDF конвертация НЕДОСТУПНА!")

        if pdf_status["warnings"]:
            lines.append("")
            lines.append("ПРЕДУПРЕЖДЕНИЯ:")
            for warning in pdf_status["warnings"]:
                lines.append(f"  ⚠ {warning}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)
