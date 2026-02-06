# AirDocs - AWB Editor Integration
# ========================================
#
# NOTE: This is a PLACEHOLDER integration for AWB Editor.
# The actual AWB Editor API/CLI is UNKNOWN at this time.
#
# This wrapper provides:
# - Configuration-based setup (path, import format, etc.)
# - Safe no-op behavior when AWB Editor is unavailable
# - Clear UI messages about integration status
#
# When actual AWB Editor details become available, update:
# 1. The export_data() method to generate the correct format
# 2. The call_awb_editor() method with correct CLI parameters
# 3. The check_output() method to find generated files

import csv
import json
import logging
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from core.app_context import get_context
from core.exceptions import IntegrationError

logger = logging.getLogger("airdocs.integrations")


class AWBEditorIntegration:
    """
    Integration wrapper for AWB Editor (third-party application).

    IMPORTANT: This is a PLACEHOLDER implementation.
    The actual AWB Editor API is unknown.

    Current implementation provides:
    - Configuration management (path, formats)
    - Data export in CSV/XML/JSON formats
    - Subprocess invocation (if CLI is supported)
    - Clear error messages for UI

    Usage:
    1. Configure AWB Editor in settings.yaml:
       awb_editor:
         enabled: true
         executable_path: "C:/path/to/awb_editor.exe"
         import_format: "csv"

    2. Use this class to attempt integration:
       editor = AWBEditorIntegration()
       if editor.is_available():
           result = editor.generate_awb(data, output_dir)
    """

    def __init__(self):
        self._context = get_context()
        self._config = self._context.get_awb_editor_config()

    def is_enabled(self) -> bool:
        """Check if AWB Editor integration is enabled in config."""
        return self._config.get("enabled", False)

    def is_available(self) -> bool:
        """
        Check if AWB Editor is available for use.

        Returns True only if:
        - Integration is enabled in config
        - Executable path is configured
        - Executable file exists
        """
        if not self.is_enabled():
            return False

        exe_path = self._config.get("executable_path", "")
        if not exe_path:
            return False

        return Path(exe_path).exists()

    def get_executable_path(self) -> Path | None:
        """Get path to AWB Editor executable."""
        exe_path = self._config.get("executable_path", "")
        if exe_path:
            path = Path(exe_path)
            if path.exists():
                return path
        return None

    def get_import_format(self) -> str:
        """Get configured import format (csv, xml, json)."""
        return self._config.get("import_format", "csv")

    def get_exchange_dir(self) -> Path:
        """Get directory for file exchange with AWB Editor."""
        exchange_dir = self._config.get("exchange_dir", "data/awb_editor_exchange")
        path = self._context.base_path / exchange_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    def export_data(
        self,
        data: dict[str, Any],
        format: str | None = None,
    ) -> Path:
        """
        Export AWB data to a file format for import into AWB Editor.

        Args:
            data: Dictionary with canonical AWB field names
            format: Export format (csv, xml, json). Uses config if not specified.

        Returns:
            Path to exported file

        NOTE: The exact format expected by AWB Editor is unknown.
        This creates files in common formats that AWB Editor might support.
        """
        format = format or self.get_import_format()
        exchange_dir = self.get_exchange_dir()

        awb_number = data.get("awb_number", "unknown")
        base_name = f"awb_export_{awb_number}"

        if format == "csv":
            return self._export_csv(data, exchange_dir / f"{base_name}.csv")
        elif format == "xml":
            return self._export_xml(data, exchange_dir / f"{base_name}.xml")
        elif format == "json":
            return self._export_json(data, exchange_dir / f"{base_name}.json")
        else:
            raise IntegrationError(
                f"Unknown export format: {format}",
                integration="awb_editor",
                operation="export_data",
            )

    def _export_csv(self, data: dict[str, Any], path: Path) -> Path:
        """Export data to CSV format."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["field", "value"])
            for key, value in data.items():
                writer.writerow([key, str(value) if value is not None else ""])
        logger.debug(f"Exported AWB data to CSV: {path}")
        return path

    def _export_xml(self, data: dict[str, Any], path: Path) -> Path:
        """Export data to XML format."""
        root = ET.Element("AWB")
        for key, value in data.items():
            elem = ET.SubElement(root, key)
            elem.text = str(value) if value is not None else ""
        tree = ET.ElementTree(root)
        tree.write(path, encoding="utf-8", xml_declaration=True)
        logger.debug(f"Exported AWB data to XML: {path}")
        return path

    def _export_json(self, data: dict[str, Any], path: Path) -> Path:
        """Export data to JSON format."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Exported AWB data to JSON: {path}")
        return path

    def generate_awb(
        self,
        data: dict[str, Any],
        output_dir: Path | str,
    ) -> tuple[bool, Path | None, str]:
        """
        Attempt to generate AWB PDF using AWB Editor.

        Args:
            data: AWB data dictionary
            output_dir: Directory where to expect output

        Returns:
            Tuple of (success, output_path or None, message)

        NOTE: This is a PLACEHOLDER implementation.
        The actual AWB Editor CLI parameters are unknown.
        """
        if not self.is_enabled():
            return False, None, (
                "AWB Editor integration отключена. "
                "Включите в настройках (settings.yaml -> awb_editor -> enabled: true)"
            )

        if not self.is_available():
            exe_path = self._config.get("executable_path", "не указан")
            return False, None, (
                f"AWB Editor недоступен. "
                f"Путь к файлу: {exe_path}. "
                f"Проверьте, что AWB Editor установлен и путь указан верно."
            )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Export data to exchange format
            export_file = self.export_data(data)

            # Try to call AWB Editor
            # NOTE: CLI parameters are UNKNOWN - this is a guess
            exe_path = self.get_executable_path()
            awb_number = data.get("awb_number", "unknown")
            expected_output = output_dir / f"AWB-{awb_number}.pdf"

            # Attempt to invoke AWB Editor
            # The actual command line format is unknown
            # This is a placeholder that documents what we would try
            result = self._call_awb_editor(
                exe_path,
                export_file,
                expected_output,
            )

            if result and expected_output.exists():
                return True, expected_output, "AWB успешно создан через AWB Editor"

            # If direct call didn't work, provide instructions
            return False, None, (
                f"AWB Editor вызван, но PDF не создан. "
                f"Возможно, требуется ручное действие. "
                f"Экспортированные данные: {export_file}"
            )

        except Exception as e:
            logger.error(f"AWB Editor integration failed: {e}", exc_info=True)
            return False, None, f"Ошибка AWB Editor: {str(e)}"

    def _call_awb_editor(
        self,
        exe_path: Path,
        import_file: Path,
        output_file: Path,
    ) -> bool:
        """
        Call AWB Editor executable.

        NOTE: The actual CLI parameters are UNKNOWN.
        This is a placeholder implementation that tries common patterns.
        """
        # Try various possible CLI patterns
        # Pattern 1: --import <file> --output <file>
        # Pattern 2: positional arguments
        # Pattern 3: /import /output

        patterns = [
            [str(exe_path), "--import", str(import_file), "--output", str(output_file)],
            [str(exe_path), str(import_file), str(output_file)],
            [str(exe_path), "/import", str(import_file), "/output", str(output_file)],
        ]

        for cmd in patterns:
            try:
                logger.debug(f"Trying AWB Editor command: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    logger.info("AWB Editor command succeeded")
                    return True
            except subprocess.TimeoutExpired:
                logger.warning("AWB Editor command timed out")
            except Exception as e:
                logger.debug(f"AWB Editor command failed: {e}")

        # None of the patterns worked
        logger.warning(
            "Could not determine AWB Editor CLI format. "
            "Please configure the correct command line parameters."
        )
        return False

    def get_integration_status(self) -> dict[str, Any]:
        """
        Get detailed status information for UI display.

        Returns:
            Dictionary with integration status details
        """
        return {
            "enabled": self.is_enabled(),
            "available": self.is_available(),
            "executable_path": str(self.get_executable_path()) if self.is_available() else None,
            "import_format": self.get_import_format(),
            "exchange_dir": str(self.get_exchange_dir()),
            "status_message": self._get_status_message(),
        }

    def _get_status_message(self) -> str:
        """Get human-readable status message."""
        if not self.is_enabled():
            return (
                "AWB Editor integration отключена. "
                "Для включения установите enabled: true в настройках."
            )

        exe_path = self._config.get("executable_path", "")
        if not exe_path:
            return (
                "AWB Editor: путь к исполняемому файлу не указан. "
                "Укажите executable_path в настройках."
            )

        if not Path(exe_path).exists():
            return f"AWB Editor: файл не найден по пути {exe_path}"

        return f"AWB Editor: готов к использованию ({exe_path})"
