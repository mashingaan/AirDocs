# AirDocs - Application Context (Singleton)
# ==========================================

import logging
import logging.config
import platform
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigurationError


class AppContext:
    """
    Singleton class holding global application state.

    Provides access to:
    - Configuration (settings.yaml)
    - Field mappings (field_mapping.yaml)
    - Logger
    - Base paths (app_dir and user_dir)

    Application runs in portable-only mode.
    All user data is stored exclusively in the local 'data/' subdirectory.
    """

    _instance: "AppContext | None" = None
    _initialized: bool = False

    def __new__(cls) -> "AppContext":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if AppContext._initialized:
            return
        AppContext._initialized = True

        self._config: dict[str, Any] = {}
        self._field_mapping: dict[str, Any] = {}
        self._logger: logging.Logger | None = None
        self._base_path: Path | None = None
        self._data_path: Path | None = None

    def initialize(self, base_path: Path | str | None = None) -> None:
        """
        Initialize the application context.

        Args:
            base_path: Deprecated. Base path is auto-detected.
        """
        # Determine writable base path used for data/ in portable mode.
        if getattr(sys, 'frozen', False):
            # PyInstaller: directory containing EXE.
            self._base_path = Path(sys.executable).parent.resolve()
        else:
            # Development: source directory.
            self._base_path = Path(__file__).parent.parent.resolve()

        # Startup diagnostics for frozen/dev environment troubleshooting.
        logging.info(f"Python executable: {sys.executable}")
        logging.info(f"Frozen (PyInstaller): {getattr(sys, 'frozen', False)}")

        if getattr(sys, 'frozen', False):
            try:
                meipass = getattr(sys, '_MEIPASS', None)
                if meipass:
                    logging.info(f"PyInstaller temp dir (_MEIPASS): {meipass}")
                else:
                    logging.debug("PyInstaller _MEIPASS is not available")
            except Exception as e:
                logging.debug(f"Could not access _MEIPASS: {e}")

        logging.info(
            f"Platform: {platform.system()} {platform.release()} ({platform.version()})"
        )
        logging.info(f"Base path (writable): {self._base_path}")
        logging.info(f"Resources directory (bundled): {self.resources_dir}")

        # Determine user data directory (portable mode only)
        self._user_dir = self._base_path / "data"
        logging.info(f"User data directory: {self._user_dir}")
        portable_marker = self._user_dir / ".portable"

        try:
            self._user_dir.mkdir(parents=True, exist_ok=True)
            portable_marker.touch(exist_ok=True)
        except OSError as e:
            logging.error(
                f"Failed to initialize portable data directory: {e}",
                exc_info=True,
            )
            try:
                from PySide6.QtWidgets import QMessageBox, QApplication

                app = QApplication.instance()
                if app is None:
                    app = QApplication(sys.argv)

                QMessageBox.critical(
                    None,
                    "Ошибка доступа",
                    "Нельзя записывать рядом с приложением. Переместите папку приложения в место с правами записи (например, Рабочий стол/Документы).",
                )
            except Exception:
                logging.error(
                    "Failed to show portable mode access error dialog",
                    exc_info=True,
                )
            raise

        # Copy bundled configs to user_dir for customization
        self._copy_bundled_configs_to_user_dir()

        # Load configurations
        self._load_config()
        self._load_field_mapping()
        self._setup_logging()
        self._ensure_directories()

        self._logger.info(
            f"AppContext initialized. Base path: {self._base_path}"
        )

    @property
    def app_dir(self) -> Path:
        """
        Directory containing bundled application resources.

        For PyInstaller bundles, this resolves to sys._MEIPASS.
        For development, this is the awb_dispatcher source directory.

        Use this for loading bundled files (config/, templates/, migrations/).
        For writable storage, use user_dir (base_path/data).
        """
        return self.resources_dir

    @property
    def user_dir(self) -> Path:
        """
        Directory for user data in portable-only mode.

        Returns the local 'data/' subdirectory within the application directory.
        """
        return self._user_dir

    @property
    def resources_dir(self) -> Path:
        """
        Directory containing read-only bundled resources (config, templates, migrations).

        For PyInstaller bundles: sys._MEIPASS (temporary extraction directory).
        For development: awb_dispatcher source directory.

        Use this for loading config files, templates, and migrations.
        Use app_dir for writable application directory (EXE location).
        """
        if getattr(sys, 'frozen', False):
            # PyInstaller: bundled resources in temp dir.
            return Path(sys._MEIPASS)
        # Development: source directory.
        return self._base_path

    def _load_config(self) -> None:
        """Load main configuration from bundled settings with user overlay."""
        user_config_path = self.user_dir / "config" / "settings.yaml"
        bundled_config_path = self.resources_dir / "config" / "settings.yaml"

        if not bundled_config_path.exists() and not user_config_path.exists():
            raise ConfigurationError(
                "Configuration file not found in bundled or user config paths",
                config_file=str(bundled_config_path),
            )

        bundled_config: dict[str, Any] = {}
        user_config: dict[str, Any] = {}

        if bundled_config_path.exists():
            try:
                with open(bundled_config_path, "r", encoding="utf-8") as f:
                    bundled_config = yaml.safe_load(f) or {}
                logging.info(f"Loaded bundled config base: {bundled_config_path}")
            except yaml.YAMLError as e:
                raise ConfigurationError(
                    f"Error parsing bundled configuration file: {e}",
                    config_file=str(bundled_config_path),
                )
        else:
            logging.warning(f"Bundled config not found: {bundled_config_path}")

        if user_config_path.exists():
            try:
                with open(user_config_path, "r", encoding="utf-8") as f:
                    user_config = yaml.safe_load(f) or {}
                logging.info(f"Loaded user config overlay: {user_config_path}")
            except yaml.YAMLError as e:
                raise ConfigurationError(
                    f"Error parsing user configuration file: {e}",
                    config_file=str(user_config_path),
                )

        if bundled_config:
            self._config = self._deep_merge_with_validation(bundled_config, user_config)
        else:
            self._config = user_config

        # Legacy: Check for old config_override.yaml (can be removed in future)
        override_path = self.user_dir / "config_override.yaml"
        if override_path.exists():
            try:
                with open(override_path, "r", encoding="utf-8") as f:
                    override_config = yaml.safe_load(f) or {}

                self._config = self._deep_merge_with_validation(
                    self._config, override_config
                )
                logging.info(f"Applied legacy config override from {override_path}")

            except yaml.YAMLError as e:
                self._show_config_error_dialog(str(e), override_path)

    def _deep_merge_with_validation(
        self, base: dict, override: dict
    ) -> dict:
        """
        Deep merge override into base with validation.

        - Nested dicts: merged recursively
        - Lists: replaced entirely
        - Primitives: replaced with override value
        - Unknown keys: allowed (logged as warning)
        - Type mismatch: use base value (logged as warning)
        """
        result = base.copy()

        for key, override_value in override.items():
            if key not in base:
                # Unknown key - allow but warn
                logging.warning(f"Config override: unknown key '{key}'")
                result[key] = override_value
            elif isinstance(base[key], dict) and isinstance(override_value, dict):
                # Nested dict - recurse
                result[key] = self._deep_merge_with_validation(
                    base[key], override_value
                )
            elif type(base[key]) != type(override_value) and base[key] is not None:
                # Type mismatch - use base
                logging.warning(
                    f"Config override: type mismatch for '{key}', "
                    f"expected {type(base[key]).__name__}, "
                    f"got {type(override_value).__name__}. Using base value."
                )
            else:
                # Replace (primitives and lists)
                result[key] = override_value

        return result

    def _show_config_error_dialog(self, error: str, config_path: Path) -> None:
        """Show error dialog for config override issues."""
        try:
            from PySide6.QtWidgets import QMessageBox, QApplication

            # Ensure QApplication exists
            app = QApplication.instance()
            if app is None:
                # Can't show dialog without QApplication
                logging.error(
                    f"Config override error in {config_path}: {error}"
                )
                return

            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Ошибка конфигурации")
            msg.setText(
                f"Ошибка в файле переопределения конфигурации:\n{config_path}\n\n{error}\n\nИспользуется базовая конфигурация."
            )

            open_btn = msg.addButton("Открыть файл", QMessageBox.ActionRole)
            ok_btn = msg.addButton("OK", QMessageBox.AcceptRole)

            msg.exec()

            if msg.clickedButton() == open_btn:
                subprocess.Popen(['notepad', str(config_path)])

        except ImportError:
            # PySide6 not available yet
            logging.error(
                f"Config override error in {config_path}: {error}"
            )

    def _load_field_mapping(self) -> None:
        """Load field mapping from bundled config with user overlay."""
        user_mapping_path = self.user_dir / "config" / "field_mapping.yaml"
        bundled_mapping_path = self.resources_dir / "config" / "field_mapping.yaml"

        if not bundled_mapping_path.exists() and not user_mapping_path.exists():
            raise ConfigurationError(
                "Field mapping file not found in bundled or user config paths",
                config_file=str(bundled_mapping_path),
            )

        bundled_mapping: dict[str, Any] = {}
        user_mapping: dict[str, Any] = {}

        if bundled_mapping_path.exists():
            try:
                with open(bundled_mapping_path, "r", encoding="utf-8") as f:
                    bundled_mapping = yaml.safe_load(f) or {}
                logging.info(
                    f"Loaded bundled field mapping base: {bundled_mapping_path}"
                )
            except yaml.YAMLError as e:
                raise ConfigurationError(
                    f"Error parsing bundled field mapping file: {e}",
                    config_file=str(bundled_mapping_path),
                )
        else:
            logging.warning(f"Bundled field mapping not found: {bundled_mapping_path}")

        if user_mapping_path.exists():
            try:
                with open(user_mapping_path, "r", encoding="utf-8") as f:
                    user_mapping = yaml.safe_load(f) or {}
                logging.info(
                    f"Loaded user field mapping overlay: {user_mapping_path}"
                )
            except yaml.YAMLError as e:
                raise ConfigurationError(
                    f"Error parsing user field mapping file: {e}",
                    config_file=str(user_mapping_path),
                )

        if bundled_mapping:
            self._field_mapping = self._deep_merge_with_validation(
                bundled_mapping, user_mapping
            )
        else:
            self._field_mapping = user_mapping

    def _setup_logging(self) -> None:
        """Setup logging from bundled config with user overlay or use default config."""
        user_logging_path = self.user_dir / "config" / "logging.yaml"
        bundled_logging_path = self.resources_dir / "config" / "logging.yaml"

        # Ensure logs directory exists
        logs_dir = self.get_path("logs_dir")
        logs_dir.mkdir(parents=True, exist_ok=True)

        if bundled_logging_path.exists() or user_logging_path.exists():
            try:
                bundled_logging_config: dict[str, Any] = {}
                user_logging_config: dict[str, Any] = {}

                if bundled_logging_path.exists():
                    with open(bundled_logging_path, "r", encoding="utf-8") as f:
                        bundled_logging_config = yaml.safe_load(f) or {}
                    logging.info(
                        f"Loaded bundled logging config base: {bundled_logging_path}"
                    )
                else:
                    logging.warning(
                        f"Bundled logging config not found: {bundled_logging_path}"
                    )

                if user_logging_path.exists():
                    with open(user_logging_path, "r", encoding="utf-8") as f:
                        user_logging_config = yaml.safe_load(f) or {}
                    logging.info(
                        f"Loaded user logging config overlay: {user_logging_path}"
                    )

                if bundled_logging_config:
                    log_config = self._deep_merge_with_validation(
                        bundled_logging_config, user_logging_config
                    )
                else:
                    log_config = user_logging_config

                # Update file paths to be absolute (in user_dir)
                if "handlers" in log_config:
                    for handler_name, handler_config in log_config["handlers"].items():
                        if "filename" in handler_config:
                            # Route log files to user_dir
                            rel_path = Path(handler_config["filename"]).name
                            abs_path = logs_dir / rel_path
                            abs_path.parent.mkdir(parents=True, exist_ok=True)
                            handler_config["filename"] = str(abs_path)

                logging.config.dictConfig(log_config)
            except Exception as e:
                # Fallback to basic config
                self._setup_basic_logging()
                logging.warning(f"Could not load logging config: {e}")
        else:
            self._setup_basic_logging()

        self._logger = logging.getLogger("airdocs")

    def _setup_basic_logging(self) -> None:
        """Setup basic logging when config file is not available."""
        logs_dir = self.get_path("logs_dir")
        log_file = logs_dir / "app.log"

        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file, encoding="utf-8"),
            ],
        )

    def _ensure_directories(self) -> None:
        """Ensure all required directories exist (defensive - should already be created by main.py)."""
        directories = [
            self.get_path("data_dir"),
            self.get_path("output_dir"),
            self.get_path("logs_dir"),
            self.user_dir / "backups",
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _copy_bundled_configs_to_user_dir(self) -> None:
        """
        Copy bundled config files to user_dir/config/ if they don't exist.

        This allows users to customize configs that persist across updates.
        Bundled configs in resources_dir remain as read-only defaults.
        """
        user_config_dir = self.user_dir / "config"
        user_config_dir.mkdir(parents=True, exist_ok=True)

        config_files = ["settings.yaml", "field_mapping.yaml", "logging.yaml"]

        for config_file in config_files:
            bundled_path = self.resources_dir / "config" / config_file
            user_path = user_config_dir / config_file

            # Skip if user already has this config
            if user_path.exists():
                logging.debug(f"User config exists: {user_path}")
                continue

            # Copy from bundle if it exists
            if bundled_path.exists():
                try:
                    shutil.copy2(bundled_path, user_path)
                    logging.info(f"Copied bundled config to user dir: {config_file}")
                except Exception as e:
                    logging.warning(
                        f"Failed to copy {config_file} to user dir: {e}. "
                        "Will use bundled version."
                    )
            else:
                logging.warning(f"Bundled config not found: {bundled_path}")

    @property
    def config(self) -> dict[str, Any]:
        """Get the main configuration dictionary."""
        return self._config

    @property
    def field_mapping(self) -> dict[str, Any]:
        """Get the field mapping dictionary."""
        return self._field_mapping

    @property
    def fields(self) -> dict[str, Any]:
        """Get the fields definitions from field mapping."""
        return self._field_mapping.get("fields", {})

    @property
    def logger(self) -> logging.Logger:
        """Get the application logger."""
        if self._logger is None:
            self._logger = logging.getLogger("airdocs")
        return self._logger

    @property
    def base_path(self) -> Path:
        """Get the base path of the application."""
        if self._base_path is None:
            raise ConfigurationError("AppContext not initialized")
        return self._base_path

    def get_path(self, key: str) -> Path:
        """
        Get a path from configuration.

        Data paths (database, logs, output) are routed to user_dir.
        App paths (templates, config) are routed to app_dir.

        Args:
            key: Path key from settings.yaml (e.g., 'data_dir', 'output_dir')

        Returns:
            Absolute path
        """
        # Keys that should be in user_dir (data)
        data_keys = {'database', 'logs_dir', 'output_dir', 'data_dir'}

        # Determine base directory
        base = self._user_dir if key in data_keys else self.resources_dir

        # Get path from config or defaults
        paths_config = self._config.get("paths", {})

        if key not in paths_config:
            # Use defaults (already normalized for user_dir)
            defaults = {
                "data_dir": "",  # root of user_dir
                "output_dir": "output",
                "database": "airdocs.db",
                "logs_dir": "logs",
                "templates_dir": "templates",
            }
            rel_path = defaults.get(key, key)
        else:
            rel_path = paths_config[key]

        # Make absolute
        if not rel_path:
            return base

        path = Path(rel_path)
        if path.is_absolute():
            return path

        # When using user_dir, strip "data/" or "data\" prefix from config paths
        # This allows settings.yaml to have paths like "data/logs" for app_dir mode
        # but resolve to "logs" when using user_dir
        if key in data_keys:
            path_str = str(path).replace("\\", "/")
            if path_str.startswith("data/"):
                path = Path(path_str[5:])  # Strip "data/"
            elif path_str == "data":
                return base

        return base / path

    def get_template_path(self, template_type: str, template_name: str) -> Path:
        """
        Get path to a template file.

        Args:
            template_type: Type of template ('word', 'excel', 'pdf', 'email')
            template_name: Name of the template within the type

        Returns:
            Absolute path to the template file
        """
        templates_config = self._config.get("templates", {})
        type_config = templates_config.get(template_type, {})

        if template_name not in type_config:
            raise ConfigurationError(
                f"Template not found in config: {template_type}/{template_name}",
                key=f"templates.{template_type}.{template_name}",
            )

        rel_path = type_config[template_name]
        templates_dir = self.resources_dir / "templates"
        return templates_dir / rel_path

    def get_field_config(self, field_key: str) -> dict[str, Any]:
        """
        Get configuration for a specific field.

        Args:
            field_key: Canonical field key

        Returns:
            Field configuration dictionary
        """
        fields = self._field_mapping.get("fields", {})
        if field_key not in fields:
            raise ConfigurationError(
                f"Field not found in mapping: {field_key}",
                config_file="field_mapping.yaml",
                key=f"fields.{field_key}",
            )
        return fields[field_key]

    def get_client_types(self) -> dict[str, Any]:
        """Get client type definitions."""
        return self._field_mapping.get("client_types", {})

    def get_statuses(self) -> dict[str, Any]:
        """Get status definitions."""
        return self._field_mapping.get("statuses", {})

    def get_awb_overlay_config(self) -> dict[str, Any]:
        """Get AWB PDF overlay configuration."""
        return self._config.get("awb_overlay", {})

    def get_office_config(self) -> dict[str, Any]:
        """Get Office integration configuration."""
        return self._config.get("office", {})

    def get_libreoffice_config(self) -> dict[str, Any]:
        """Get LibreOffice configuration."""
        return self._config.get("libreoffice", {})

    def get_awb_editor_config(self) -> dict[str, Any]:
        """Get AWB Editor configuration."""
        return self._config.get("awb_editor", {})

    def save_ui_config(self, ui_settings: dict[str, Any]) -> None:
        """
        Save UI settings to config override file.

        Args:
            ui_settings: Dictionary with UI settings to save (e.g., {'window_width': 1400, 'window_height': 900})
        """
        override_path = self._user_dir / "config_override.yaml"

        # Load existing override or create new
        existing_override = {}
        if override_path.exists():
            try:
                with open(override_path, "r", encoding="utf-8") as f:
                    existing_override = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                self._logger.warning(f"Could not load config override: {e}")

        # Merge UI settings
        if "ui" not in existing_override:
            existing_override["ui"] = {}
        existing_override["ui"].update(ui_settings)

        # Save to file
        try:
            with open(override_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(existing_override, f, allow_unicode=True, default_flow_style=False)
            self._logger.info(f"Saved UI config to {override_path}")
        except Exception as e:
            self._logger.error(f"Failed to save UI config: {e}", exc_info=True)


# Global convenience function
def get_context() -> AppContext:
    """Get the global AppContext instance."""
    return AppContext()

