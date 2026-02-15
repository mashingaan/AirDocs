#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AirDocs - Main Entry Point
=================================

AirDocs - Logistics Document Management
Desktop application for logistics document management.
Portable mode only: all user data is stored in the 'data/' subdirectory.

Usage:
    python main.py              # Normal startup
    python main.py --debug      # Debug mode with verbose logging
    python main.py --reset-db   # Reset database (WARNING: deletes all data)
    python main.py --diagnostics # Run environment diagnostics only

Requirements:
    - Python 3.11+
    - PySide6
    - See requirements.txt for full list

Copyright (c) 2026
"""

import argparse
import json
import logging
import platform
import shutil
import sqlite3
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.app_context import AppContext

# Ensure the package directory is in path
APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def check_vcredist_dependencies() -> None:
    """Check required Visual C++ runtime DLLs before loading heavy dependencies."""
    if platform.system() != "Windows":
        return

    try:
        import ctypes

        required_dlls = ["vcruntime140.dll", "msvcp140.dll"]
        missing_dlls: list[str] = []

        for dll_name in required_dlls:
            module_handle = ctypes.windll.kernel32.LoadLibraryW(dll_name)
            if module_handle:
                ctypes.windll.kernel32.FreeLibrary(module_handle)
            else:
                missing_dlls.append(dll_name)

        if not missing_dlls:
            return

        message = (
            "Ошибка запуска AirDocs\n\n"
            "Отсутствуют необходимые системные библиотеки (Visual C++ Runtime).\n\n"
            "Решение:\n"
            "1. Скачайте Microsoft Visual C++ Redistributable x64:\n"
            "   https://aka.ms/vs/17/release/vc_redist.x64.exe\n"
            "2. Установите и перезапустите AirDocs.\n\n"
            "Если проблема сохраняется, отправьте data/logs/app.log разработчику."
        )
        ctypes.windll.user32.MessageBoxW(0, message, "AirDocs - Ошибка", 0x10)
        sys.exit(1)
    except Exception as e:
        print(f"Warning: Could not check VC++ dependencies: {e}", file=sys.stderr)


from core.version import VERSION, get_version


def ensure_data_dirs() -> Path:
    """
    Ensure all required data subdirectories exist.

    Creates the full data/ directory structure before logging or AppContext init.
    Works in both development and PyInstaller frozen modes.

    Returns:
        Path to the data directory
    """
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else (APP_DIR or Path.cwd())
    data_dir = base / "data"

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "logs").mkdir(parents=True, exist_ok=True)
        (data_dir / "output").mkdir(parents=True, exist_ok=True)
        (data_dir / "backups").mkdir(parents=True, exist_ok=True)
        (data_dir / "templates").mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Failed to create data directories: {e}", file=sys.stderr)

    return data_dir


def check_directory_access(path: Path) -> tuple[bool, str | None]:
    """Check read/write access for directory."""
    if not path.exists() or not path.is_dir():
        return False, f"Директория не существует: {path}"

    try:
        # Read check
        _ = next(path.iterdir(), None)

        # Write check
        with tempfile.NamedTemporaryFile(mode="w", dir=path, delete=True) as temp_file:
            temp_file.write("airdocs_access_test")
            temp_file.flush()
    except PermissionError as e:
        return False, f"Нет доступа к директории {path}: {e}"
    except OSError as e:
        return False, f"Ошибка доступа к директории {path}: {e}"

    return True, None


def get_disk_space_info(path: Path) -> dict[str, int]:
    """Get disk usage information for path."""
    try:
        usage = shutil.disk_usage(path)
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
        }
    except Exception:
        return {}


def log_system_diagnostics(logger: logging.Logger, context: "AppContext") -> None:
    """Log system diagnostics for startup troubleshooting."""
    logger.info(f"Application version: {VERSION}")
    logger.info(f"System: {platform.system()} {platform.release()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"App directory: {context.app_dir}")
    logger.info(f"Data directory: {context.user_dir}")
    logger.info(f"Database path: {context.get_path('database')}")

    disk_info = get_disk_space_info(context.user_dir)
    if disk_info:
        logger.info(
            "Disk usage for data directory: "
            f"total={disk_info['total']} bytes, "
            f"used={disk_info['used']} bytes, "
            f"free={disk_info['free']} bytes"
        )
    else:
        logger.warning(f"Failed to read disk usage for: {context.user_dir}")

    can_access, access_error = check_directory_access(context.user_dir)
    if can_access:
        logger.info(f"Directory access check passed: {context.user_dir}")
    else:
        logger.warning(f"Directory access check failed: {access_error}")


def show_initialization_error_dialog(
    error: Exception,
    context: "AppContext | None",
) -> None:
    """Show user-friendly initialization error dialog with diagnostics."""
    logger = logging.getLogger("airdocs")

    data_path = None
    logs_path = None
    if context is not None:
        try:
            data_path = context.user_dir
            logs_path = context.get_path("logs_dir")
        except Exception:
            pass

    error_text = str(error)
    details_lines = [
        f"Ошибка: {error_text}",
    ]
    if data_path is not None:
        details_lines.append(f"Путь к данным: {data_path}")
    if logs_path is not None:
        details_lines.append(f"Путь к логам: {logs_path}")
    details_lines.append("")
    details_lines.append("Traceback:")
    details_lines.append(
        "".join(traceback.format_exception(type(error), error, error.__traceback__))
    )
    details_text = "\n".join(details_lines)

    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        logger.error("Initialization failed before QApplication startup", exc_info=True)
        print("Ошибка инициализации приложения.", file=sys.stderr)
        print(f"Причина: {error_text}", file=sys.stderr)
        if data_path is not None:
            print(f"Путь к данным: {data_path}", file=sys.stderr)
        if logs_path is not None:
            print(f"Путь к логам: {logs_path}", file=sys.stderr)
        print("Проверьте права доступа, свободное место и логи.", file=sys.stderr)
        return

    from PySide6.QtWidgets import QMessageBox

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle("Ошибка инициализации")
    msg.setText(
        "Приложение не удалось инициализировать.\n\n"
        f"Причина: {error_text}\n\n"
        "Проверьте права доступа, свободное место и логи."
    )
    msg.setDetailedText(details_text)

    open_logs_btn = None
    if logs_path is not None:
        open_logs_btn = msg.addButton("Открыть папку с логами", QMessageBox.ActionRole)

    copy_btn = msg.addButton("Скопировать ошибку", QMessageBox.ActionRole)
    msg.addButton("Закрыть", QMessageBox.AcceptRole)

    msg.exec()

    if msg.clickedButton() == copy_btn:
        clipboard = QApplication.clipboard()
        clipboard.setText(details_text)

    if open_logs_btn is not None and msg.clickedButton() == open_logs_btn:
        import subprocess

        subprocess.Popen(f'explorer "{logs_path}"')


def setup_logging(debug: bool = False) -> logging.Logger:
    """Set up logging configuration."""
    from logging.config import dictConfig
    import yaml

    # Create logs directory before loading logging config
    data_dir = ensure_data_dirs()
    log_dir = data_dir / "logs"
    try:
        from core.app_context import get_context

        context = get_context()
        if getattr(context, "_base_path", None) is not None and hasattr(context, "_user_dir"):
            log_dir = context.get_path("logs_dir")
    except Exception:
        log_dir = data_dir / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    # Determine config path based on frozen state
    if getattr(sys, "frozen", False):
        # PyInstaller frozen mode: bundled files in sys._MEIPASS
        config_path = Path(sys._MEIPASS) / "config" / "logging.yaml"
    else:
        # Development mode: use APP_DIR
        config_path = APP_DIR / "config" / "logging.yaml"

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Adjust log level for debug mode
        if debug:
            config["root"]["level"] = "DEBUG"
            for handler in config.get("handlers", {}).values():
                handler["level"] = "DEBUG"

        # Update all file handler paths
        for handler_name, handler_config in config.get("handlers", {}).items():
            if "filename" in handler_config:
                filename = Path(handler_config["filename"]).name
                handler_config["filename"] = str(log_dir / filename)

        dictConfig(config)
    else:
        # Fallback basic config
        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    return logging.getLogger("airdocs")


def init_application() -> bool:
    """Initialize application context and database."""
    from core.app_context import AppContext
    from core.exceptions import DatabaseError
    from data.database import Database

    logger = logging.getLogger("airdocs")

    try:
        # Initialize singleton context (loads config, field mapping, logging)
        context = AppContext()
        base_path = Path(sys.executable).parent if getattr(sys, "frozen", False) else APP_DIR
        context.initialize(base_path=base_path)
        log_system_diagnostics(logger, context)

        # Initialize database with migrations
        db_path = context.get_path("database")
        migrations_path = APP_DIR / "data" / "migrations"

        logger.info(f"Migrations path: {migrations_path}")
        logger.info(f"Migrations exist: {migrations_path.exists()}")
        if migrations_path.exists():
            migration_files = list(migrations_path.glob("*.sql"))
            logger.info(f"Found {len(migration_files)} migration files")

        logger.info(f"Initializing database at: {db_path}")
        can_access, access_error = check_directory_access(db_path.parent)
        if not can_access:
            logger.error(f"Cannot access database directory: {access_error}")
            raise DatabaseError(f"Нет доступа к директории базы данных: {access_error}")

        disk_info = get_disk_space_info(db_path.parent)
        if disk_info:
            free_mb = disk_info["free"] / 1024 / 1024
            logger.info(f"Free disk space: {free_mb:.1f} MB")
            if free_mb < 100:
                logger.warning(f"Low disk space: {free_mb:.1f} MB")

        db = Database()
        db.initialize(db_path, migrations_path)

        # Verify migrations applied successfully
        try:
            stats = db.get_database_stats(mode="fast", include_integrity=False)
            logger.info(
                "Database initialized successfully:\n"
                f"  Schema version: {stats.schema_version}\n"
                f"  Last migration: {stats.last_migration}\n"
                f"  Total tables: {stats.total_tables}\n"
                f"  Healthy: {stats.is_healthy}"
            )

            if not stats.is_healthy:
                logger.warning(f"Database health issue: {stats.error_message}")

            if stats.schema_version is None or stats.schema_version < 1:
                raise DatabaseError(
                    "Миграции не применены. "
                    f"Schema version: {stats.schema_version}",
                    operation="init_verify"
                )

        except Exception as e:
            logger.error(f"Post-migration verification failed: {e}", exc_info=True)
            raise DatabaseError(
                "Не удалось проверить состояние базы данных после миграций: "
                f"{e}",
                operation="init_verify"
            ) from e

        return True

    except Exception as e:
        logger.error(f"Application initialization failed: {e}", exc_info=True)
        show_initialization_error_dialog(e, context if "context" in locals() else None)
        return False


def reset_database() -> bool:
    """Reset the database (delete and recreate)."""
    from core.app_context import get_context
    from data.database import Database

    context = get_context()
    db_path = context.get_path("database")

    # Close existing connection if any
    db = Database()
    db.close()

    if db_path.exists():
        print(f"Deleting database: {db_path}")
        db_path.unlink()

    # Reset the singleton state to allow reinitialization
    Database._initialized = False

    # Reinitialize database (will run migrations)
    migrations_path = APP_DIR / "data" / "migrations"
    db = Database()
    db.initialize(db_path, migrations_path)

    print("Database reset complete.")
    return True


def run_diagnostics() -> int:
    """Run environment diagnostics and exit."""
    from integrations.environment_checker import EnvironmentChecker

    print("\n" + "=" * 60)
    print("AIRDOCS - ENVIRONMENT DIAGNOSTICS")
    print("=" * 60 + "\n")

    checker = EnvironmentChecker()
    status = checker.check_all()

    # Print results
    print("MICROSOFT OFFICE")
    print("-" * 40)
    if status.office.available:
        print(f"  Status: AVAILABLE")
        print(f"  Version: {status.office.version or 'unknown'}")
        if status.office.path:
            print(f"  Path: {status.office.path}")
    else:
        print(f"  Status: NOT AVAILABLE")
        print(f"  Reason: {status.office.message or 'not installed'}")

    print("\nLIBREOFFICE")
    print("-" * 40)
    if status.libreoffice.available:
        print(f"  Status: AVAILABLE")
        print(f"  Version: {status.libreoffice.version or 'unknown'}")
        if status.libreoffice.path:
            print(f"  Path: {status.libreoffice.path}")
    else:
        print(f"  Status: NOT AVAILABLE")
        print(f"  Reason: {status.libreoffice.message or 'not installed'}")

    print("\nAWB EDITOR")
    print("-" * 40)
    if status.awb_editor.available:
        print(f"  Status: AVAILABLE")
        if status.awb_editor.path:
            print(f"  Path: {status.awb_editor.path}")
    else:
        print(f"  Status: NOT CONFIGURED")
        print(f"  Reason: {status.awb_editor.message or 'not configured'}")

    print("\nCAPABILITIES")
    print("-" * 40)
    print(f"  PDF Conversion: {'YES' if status.pdf_conversion_available else 'NO'}")

    if status.pdf_conversion_available:
        methods = []
        if status.office.available:
            methods.append("Office COM (primary)")
        if status.libreoffice.available:
            methods.append("LibreOffice (fallback)")
        print(f"  Available methods: {', '.join(methods)}")

    print("\n" + "=" * 60 + "\n")

    return 0 if status.pdf_conversion_available else 1


def check_templates():
    """Check if templates exist, create if not."""
    templates_dir = APP_DIR / "templates"

    word_dir = templates_dir / "word"
    excel_dir = templates_dir / "excel"
    pdf_dir = templates_dir / "pdf"

    missing = []
    if not (word_dir / "invoice.docx").exists():
        missing.append("word/invoice.docx")
    if not (excel_dir / "registry_1c.xlsx").exists():
        missing.append("excel/registry_1c.xlsx")
    if not (pdf_dir / "awb_blank.pdf").exists():
        missing.append("pdf/awb_blank.pdf")

    if missing:
        print("\nMissing templates detected:")
        for m in missing:
            print(f"  - {m}")
        print("\nRun 'python scripts/create_demo_templates.py' to create demo templates.\n")


def handle_first_run() -> bool:
    """
    Handle first run of the application.

    Handles data migration, portable mode selection, and shortcut creation.

    Returns:
        True if first run handled successfully
    """
    from core.app_context import get_context
    from utils.data_migrator import detect_data_locations, migrate_data
    from utils.shortcut_creator import create_desktop_shortcut
    from data.database import Database, get_db
    from core.exceptions import DatabaseError
    from PySide6.QtWidgets import QApplication

    logger = logging.getLogger("airdocs")
    context = get_context()

    if QApplication.instance() is None:
        raise RuntimeError(
            "QApplication must be created before calling handle_first_run() "
            "(main.py is responsible)."
        )

    # Check migration marker
    migrated_marker = context.user_dir / '.migrated'
    if migrated_marker.exists():
        return True  # Not first run

    # Detect data locations
    locations = detect_data_locations()

    source = None

    # Scenario 1: Data conflict (both sources exist)
    if locations.has_app_data and locations.has_user_data:
        from ui.dialogs.data_conflict_dialog import DataConflictDialog

        dialog = DataConflictDialog(locations.app_data_info, locations.user_data_info)
        if dialog.exec():
            if dialog.get_selected_source() == "data_folder":
                source = locations.app_data_path
            else:
                source = locations.user_data_path
        else:
            return False  # User cancelled

    # Scenario 2: Only old data (migration required)
    elif locations.has_app_data:
        source = locations.app_data_path

    # Scenario 3: Only new data or no data
    else:
        source = None

    # Perform migration if required
    if source:
        result = migrate_data(source, context.user_dir, create_backup=True)
        if not result.success:
            logger.error(f"Data migration failed: {result.error}")
            return False

    # Check if we need to run setup wizard
    from data.repositories import PartyRepository
    from core.constants import PartyType

    party_repo = PartyRepository()

    try:
        # Verify database schema is complete before querying
        try:
            db = get_db()
            stats = db.get_database_stats(mode="fast", include_integrity=False)

            if not stats.is_healthy:
                logger.error(f"Database unhealthy: {stats.error_message}")
                raise DatabaseError(
                    "База данных не инициализирована корректно: "
                    f"{stats.error_message}",
                    operation="first_run_check"
                )

            # Check if essential tables exist
            if stats.schema_version is None or stats.schema_version < 1:
                logger.error(f"Schema version too low: {stats.schema_version}")
                raise DatabaseError(
                    "Миграции базы данных не применены. Схема не создана.",
                    operation="first_run_check"
                )

            logger.info(
                f"Database health check passed. Schema version: {stats.schema_version}"
            )

        except DatabaseError as e:
            logger.error(f"Database health check failed: {e}", exc_info=True)
            # Will be caught by outer try/except below
            raise

        # Prefer lightweight counters (do not load full rows)
        shipper_count = party_repo.count_by_type(PartyType.SHIPPER)
        consignee_count = party_repo.count_by_type(PartyType.CONSIGNEE)

        wizard_completed = False
        wizard_skipped = False

        # Run wizard only if essential parties are missing
        if shipper_count == 0 or consignee_count == 0:
            from ui.dialogs.setup_wizard_dialog import SetupWizardDialog
            from PySide6.QtWidgets import QMessageBox

            while True:
                wizard = SetupWizardDialog()
                wizard.exec()

                outcome = wizard.get_outcome()  # 'completed' | 'skipped' | 'cancelled'

                if outcome == 'completed':
                    wizard_completed = True
                    break

                if outcome == 'skipped':
                    wizard_skipped = True
                    break

                # outcome == 'cancelled' -> Cancel ≠ Skip
                box = QMessageBox()
                box.setIcon(QMessageBox.Warning)
                box.setWindowTitle("Настройка не завершена")
                box.setText(
                    "Вы закрыли мастер настройки. Хотите выйти или вернуться в мастер?"
                )
                exit_btn = box.addButton("Выйти", QMessageBox.AcceptRole)
                return_btn = box.addButton(
                    "Вернуться в мастер", QMessageBox.RejectRole
                )
                box.exec()

                if box.clickedButton() == return_btn:
                    continue

                # User explicitly chose to exit without completing setup
                wizard_skipped = True
                break

    except DatabaseError as e:
        logger.error(f"First run database check failed: {e}", exc_info=True)

        # Show recovery dialog
        from PySide6.QtWidgets import QMessageBox

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Ошибка базы данных")
        msg.setText(
            "База данных не инициализирована корректно.\n\n"
            f"Причина: {e}\n\n"
            "Возможные действия:\n"
            "1. Перезапустить приложение\n"
            "2. Проверить логи в data/logs/app.log\n"
            "3. Удалить data/airdocs.db для пересоздания"
        )

        logs_btn = msg.addButton("Открыть логи", QMessageBox.ActionRole)
        reinit_btn = msg.addButton("Пересоздать БД", QMessageBox.ActionRole)
        exit_btn = msg.addButton("Выйти", QMessageBox.RejectRole)

        msg.exec()

        if msg.clickedButton() == logs_btn:
            import subprocess
            logs_path = context.get_path("logs_dir")
            subprocess.Popen(f'explorer "{logs_path}"')
            return False

        if msg.clickedButton() == reinit_btn:
            # Attempt to apply pending migrations first
            try:
                db_path = context.get_path("database")
                migrations_path = context.app_dir / "data" / "migrations"

                db = get_db()
                db._initialized = False
                Database._initialized = False
                db.initialize(db_path, migrations_path)

                pending_backup = db.apply_pending_migrations()
                if pending_backup is not None:
                    logger.info("Pending migrations applied successfully")
                    QMessageBox.information(
                        None,
                        "Успех",
                        "Миграции применены. Продолжите настройку."
                    )
                    return handle_first_run()

            except Exception as migrate_error:
                logger.error(
                    f"Pending migrations failed: {migrate_error}", exc_info=True
                )

            # Fall back to reinitialize database
            try:
                db_path = context.get_path("database")
                if db_path.exists():
                    backup_path = db_path.with_suffix(".db.backup")
                    shutil.copy2(db_path, backup_path)
                    logger.info(f"Backed up database to {backup_path}")
                    db_path.unlink()

                # Reinitialize
                db = get_db()
                db._initialized = False
                Database._initialized = False
                migrations_path = context.app_dir / "data" / "migrations"
                db.initialize(db_path, migrations_path)

                logger.info("Database reinitialized successfully")
                QMessageBox.information(
                    None,
                    "Успех",
                    "База данных пересоздана. Продолжите настройку."
                )
                # Retry first run
                return handle_first_run()

            except Exception as reinit_error:
                logger.error(
                    f"Reinitialization failed: {reinit_error}", exc_info=True
                )
                QMessageBox.critical(
                    None,
                    "Ошибка",
                    "Не удалось пересоздать базу данных:\n"
                    f"{reinit_error}"
                )
                return False

        # User chose exit
        return False

    # Create desktop shortcut
    exe_path = Path(sys.executable) if getattr(sys, 'frozen', False) else Path(__file__)
    shortcut_created = create_desktop_shortcut(exe_path)

    # Record first run info
    try:
        db = get_db()
        with db.transaction() as cursor:
            cursor.execute("""
                INSERT INTO first_run_info
                (id, first_run_date, installation_path, data_migration_source,
                 data_migration_date, shortcut_created, portable_mode, initial_version,
                 wizard_completed, wizard_skipped)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    wizard_completed = excluded.wizard_completed,
                    wizard_skipped = excluded.wizard_skipped
            """, (
                datetime.now().isoformat(),
                str(context.app_dir),
                "data_folder" if source == locations.app_data_path else
                "appdata_existing" if source else "fresh",
                datetime.now().isoformat() if source else None,
                1 if shortcut_created else 0,
                1,  # portable_mode - always True now
                VERSION,
                1 if wizard_completed else 0,
                1 if wizard_skipped else 0,
            ))
    except Exception as e:
        logger.warning(f"Failed to record first run info: {e}")

    # Ensure demo templates exist
    templates_ready = ensure_demo_templates()
    if not templates_ready:
        logger.warning("Failed to ensure demo templates during first run")

    # Create migration marker
    try:
        context.user_dir.mkdir(parents=True, exist_ok=True)
        marker = context.user_dir / '.migrated'
        marker.write_text(f"First run completed on {datetime.now().isoformat()}")
    except OSError as e:
        logger.warning(f"Failed to create migration marker: {e}")

    return True


def ensure_demo_templates() -> bool:
    """
    Ensure demo templates exist in data/templates/.

    Creates templates if missing using logic from scripts/create_demo_templates.py.

    Returns:
        True if templates exist or were created successfully
    """
    from core.app_context import get_context
    from pathlib import Path

    logger = logging.getLogger("airdocs")
    context = get_context()

    # Define expected template paths in data/templates/
    templates_base = context.user_dir / "templates"

    expected_templates = {
        "word/invoice.docx": templates_base / "word" / "invoice.docx",
        "word/upd.docx": templates_base / "word" / "upd.docx",
        "word/act.docx": templates_base / "word" / "act.docx",
        "excel/registry_1c.xlsx": templates_base / "excel" / "registry_1c.xlsx",
        "pdf/awb_blank.pdf": templates_base / "pdf" / "awb_blank.pdf",
    }

    # Check if any templates are missing
    missing = [name for name, path in expected_templates.items() if not path.exists()]

    if not missing:
        logger.info("All demo templates already exist in data/templates/")
        return True

    logger.info(f"Creating {len(missing)} missing templates: {', '.join(missing)}")

    try:
        # Import template creation functions
        from scripts.create_demo_templates import (
            create_word_invoice_template,
            create_word_upd_template,
            create_word_act_template,
            create_excel_registry_template,
            create_pdf_awb_blank,
        )

        # Create missing templates
        if not expected_templates["word/invoice.docx"].exists():
            create_word_invoice_template(expected_templates["word/invoice.docx"])

        if not expected_templates["word/upd.docx"].exists():
            create_word_upd_template(expected_templates["word/upd.docx"])

        if not expected_templates["word/act.docx"].exists():
            create_word_act_template(expected_templates["word/act.docx"])

        if not expected_templates["excel/registry_1c.xlsx"].exists():
            create_excel_registry_template(expected_templates["excel/registry_1c.xlsx"])

        if not expected_templates["pdf/awb_blank.pdf"].exists():
            create_pdf_awb_blank(expected_templates["pdf/awb_blank.pdf"])

        logger.info("Шаблоны созданы автоматически")
        logger.info("Demo templates created successfully in data/templates/")
        return True

    except ImportError as e:
        logger.error(f"Failed to import template creation functions: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Failed to create demo templates: {e}", exc_info=True)
        return False


def _get_updater_logger(user_dir: Path) -> logging.Logger:
    """Get updater logger writing to user_dir/logs/updater.log."""
    log_dir = user_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "updater.log"

    updater_logger = logging.getLogger("airdocs.updater")
    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == log_path
        for handler in updater_logger.handlers
    ):
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        updater_logger.addHandler(handler)
        updater_logger.setLevel(logging.INFO)
        updater_logger.propagate = False

    return updater_logger


def apply_pending_update() -> bool:
    """
    Apply pending update if marker exists.
    Must be called BEFORE init_application() to avoid file locks.

    Returns:
        True if update applied successfully, False otherwise
    """
    from core.app_context import get_context

    context = get_context()
    try:
        user_dir = context.user_dir
    except Exception:
        user_dir = None

    if not user_dir:
        user_dir = APP_DIR / "data"

    updater_logger = _get_updater_logger(user_dir)
    pending_marker = user_dir / ".pending_update"

    if not pending_marker.exists():
        return True

    updater_logger.info("Pending update marker found")

    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    try:
        with open(pending_marker, "r", encoding="utf-8") as f:
            update_data = json.load(f)
    except Exception as e:
        updater_logger.error(f"Failed to read pending update marker: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Ошибка обновления",
            "Не удалось прочитать маркер отложенного обновления.\n\n"
            "Проверьте файл .pending_update."
        )
        return False

    version = update_data.get("version", "unknown")
    extracted_path_value = update_data.get("extracted_path")
    if not extracted_path_value:
        updater_logger.error("Pending update marker missing extracted_path")
        QMessageBox.critical(
            None,
            "Ошибка обновления",
            "Маркер обновления не содержит путь к извлеченным файлам."
        )
        return False

    extracted_path = Path(extracted_path_value)
    if not extracted_path.is_absolute():
        extracted_path = user_dir / extracted_path
    extracted_under_app = False
    extracted_rel: Path | None = None

    try:
        extracted_rel = extracted_path.relative_to(APP_DIR)
        extracted_under_app = True
    except ValueError:
        extracted_under_app = False
        extracted_rel = None

    if not extracted_path.exists():
        updater_logger.error(f"Extracted update path does not exist: {extracted_path}")
        QMessageBox.critical(
            None,
            "Ошибка обновления",
            "Папка с извлеченным обновлением не найдена.\n\n"
            f"Путь: {extracted_path}"
        )
        return False

    app_dir = APP_DIR
    app_old = app_dir.parent / f"{app_dir.name}_old"
    rollback_occurred = False

    from ui.dialogs.update_progress_dialog import UpdateProgressDialog

    progress_dialog = UpdateProgressDialog(version)
    progress_dialog.show()
    QApplication.processEvents()

    def _update_step(text: str, value: int) -> None:
        progress_dialog.set_step(text, value)
        QApplication.processEvents()

    try:
        updater_logger.info("Backing up current version")
        _update_step("Резервное копирование...", 1)

        if app_old.exists():
            shutil.rmtree(app_old)
        app_dir.rename(app_old)

        if extracted_under_app and extracted_rel is not None:
            extracted_source = app_old / extracted_rel
        else:
            extracted_source = extracted_path

        if not extracted_source.exists():
            raise RuntimeError(
                f"Extracted update path not found after rename: {extracted_source}"
            )

        updater_logger.info("Copying new files")
        _update_step("Копирование файлов...", 2)

        shutil.copytree(extracted_source, app_dir)

        updater_logger.info("Restoring user data")
        _restore_user_data(app_old, app_dir, user_dir, updater_logger)

        updater_logger.info("Verifying installation")
        _update_step("Проверка...", 3)

        exe_name = "airdocs.exe" if getattr(sys, "frozen", False) else "python.exe"
        if not (app_dir / exe_name).exists():
            raise RuntimeError(f"Executable not found after update: {exe_name}")

        updater_logger.info(f"Update applied successfully: v{version}")

        try:
            shutil.rmtree(extracted_source)
        except Exception as e:
            updater_logger.warning(f"Failed to remove extracted files: {e}")

        try:
            pending_marker.unlink()
        except Exception as e:
            updater_logger.warning(f"Failed to remove pending marker: {e}")

        try:
            _record_update_history(
                update_data,
                user_dir,
                success=True,
                rollback=False,
                error_message=None
            )
        except Exception as e:
            updater_logger.warning(f"Failed to record update history: {e}")

        QMessageBox.information(
            None,
            "Обновление установлено",
            f"Обновление до v{version} установлено успешно."
        )

        return True

    except Exception as e:
        updater_logger.error(f"Failed to apply update: {e}", exc_info=True)
        error_message = str(e)

        try:
            updater_logger.info("Attempting rollback")
            if app_dir.exists():
                shutil.rmtree(app_dir, ignore_errors=True)
            if app_old.exists():
                app_old.rename(app_dir)
                rollback_occurred = True
                updater_logger.info("Rollback completed")
        except Exception as rollback_error:
            updater_logger.error(
                f"Rollback failed: {rollback_error}",
                exc_info=True
            )
            QMessageBox.critical(
                None,
                "Критическая ошибка обновления",
                "Не удалось установить обновление и выполнить откат.\n\n"
                f"Текущая папка приложения: {app_dir}\n"
                f"Папка резервной копии: {app_old}\n\n"
                "Проверьте эти пути вручную."
            )
            try:
                _record_update_history(
                    update_data,
                    user_dir,
                    success=False,
                    rollback=False,
                    error_message=error_message
                )
            except Exception as record_error:
                updater_logger.warning(
                    f"Failed to record update history: {record_error}"
                )
            return False

        try:
            _record_update_history(
                update_data,
                user_dir,
                success=False,
                rollback=rollback_occurred,
                error_message=error_message
            )
        except Exception as record_error:
            updater_logger.warning(f"Failed to record update history: {record_error}")

        QMessageBox.critical(
            None,
            "Ошибка обновления",
            f"Не удалось установить обновление:\n\n{error_message}"
        )
        return False

    finally:
        progress_dialog.allow_close()
        progress_dialog.close()


def _record_update_history(
    update_data: dict,
    user_dir: Path,
    success: bool,
    rollback: bool,
    error_message: str | None,
) -> None:
    """Record update history entry in the database."""
    db_path = user_dir / "awb_dispatcher.db"
    if not db_path.exists():
        return

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO update_history
            (version, previous_version, channel, install_method, download_size,
             download_duration, install_success, error_message, rollback_occurred)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                update_data.get("version", ""),
                VERSION,
                update_data.get("channel", "latest"),
                "auto",
                int(update_data.get("size", 0) or 0),
                0,
                1 if success else 0,
                error_message,
                1 if rollback else 0,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _merge_user_directory(
    source_dir: Path,
    target_dir: Path,
    logger: logging.Logger,
) -> None:
    """Merge directory contents without overwriting existing files."""
    for path in source_dir.rglob("*"):
        if path.is_dir():
            continue
        rel_path = path.relative_to(source_dir)
        target_path = target_dir / rel_path
        if target_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target_path)
        logger.info(f"Restored file: {target_path}")


def _restore_user_data(
    app_old: Path,
    app_dir: Path,
    user_dir: Path,
    logger: logging.Logger,
) -> None:
    """Restore user data from previous installation."""
    try:
        user_dir.relative_to(app_dir)
        restore_required = True
    except ValueError:
        restore_required = False

    if not restore_required:
        logger.info("User data directory is outside app directory; restore skipped")
        return

    old_data = app_old / "data"
    new_data = user_dir

    if not old_data.exists():
        return

    new_data.mkdir(parents=True, exist_ok=True)

    # Restore critical user files (overwrite if needed)
    for filename in ("awb_dispatcher.db", "config_override.yaml"):
        source_file = old_data / filename
        if source_file.exists():
            shutil.copy2(source_file, new_data / filename)
            logger.info(f"Restored {filename}")

    # Restore hidden markers (skip pending update marker)
    for hidden_file in old_data.iterdir():
        if hidden_file.is_file() and hidden_file.name.startswith("."):
            if hidden_file.name == ".pending_update":
                continue
            target_file = new_data / hidden_file.name
            if target_file.exists():
                continue
            shutil.copy2(hidden_file, target_file)
            logger.info(f"Restored {hidden_file.name}")

    # Restore user data directories (merge, skip existing files)
    user_dirs = [
        "logs",
        "output",
        "backups",
        "updates",
        "awb_editor_exchange",
    ]
    for dir_name in user_dirs:
        source_dir = old_data / dir_name
        if source_dir.exists():
            _merge_user_directory(source_dir, new_data / dir_name, logger)


def cleanup_old_version() -> None:
    """Clean up old version after successful update."""
    from core.app_context import get_context

    logger = logging.getLogger("airdocs")
    context = get_context()
    app_old = context.app_dir.parent / f'{context.app_dir.name}_old'

    if app_old.exists():
        try:
            shutil.rmtree(app_old)
            logger.info(f"Cleaned up old version: {app_old}")
        except Exception as e:
            logger.warning(f"Failed to cleanup old version: {e}")


def check_pending_update() -> None:
    """Check for pending update and offer to install."""
    from core.app_context import get_context

    logger = logging.getLogger("airdocs")
    context = get_context()

    pending_marker = context.user_dir / '.pending_update'

    if pending_marker.exists():
        try:
            from PySide6.QtWidgets import QMessageBox, QApplication

            app = QApplication.instance()
            if not app:
                return

            reply = QMessageBox.question(
                None,
                "Отложенное обновление",
                "Обновление готово, но не установлено.\n\n"
                "Перезапустить приложение?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                QApplication.quit()

        except Exception as e:
            logger.error(f"Failed to process pending update: {e}")


def check_for_github_updates() -> None:
    """Check for updates from GitHub Releases on startup."""
    from core.app_context import get_context
    from utils.github_checker import get_latest_release
    from core.version import VERSION
    from ui.dialogs.update_dialog import UpdateDialog
    from PySide6.QtWidgets import QApplication

    logger = logging.getLogger("airdocs")

    try:
        context = get_context()
        config = context.config.get('updater', {})

        # Check if startup check is enabled
        if not config.get('check_on_startup', True):
            logger.debug("Startup update check disabled in config")
            return

        # Get GitHub repo from config
        github_repo = config.get('github_repo')
        if not github_repo:
            logger.warning("GitHub repo not configured in settings.yaml")
            return

        logger.info(f"Checking for updates from GitHub: {github_repo}")

        # Check for updates
        update_info = get_latest_release(github_repo, VERSION)

        if update_info is None:
            logger.info("No updates available")
            return

        logger.info(f"Update available: {update_info.version}")

        # Show update dialog
        app = QApplication.instance()
        if not app:
            logger.warning("QApplication not available, skipping update dialog")
            return

        dialog = UpdateDialog(update_info)
        dialog.exec()

    except Exception as e:
        logger.warning(f"Failed to check for updates: {e}", exc_info=True)


def run_gui(debug: bool = False) -> int:
    """Run the main GUI application."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    # Check if QApplication already exists (created during first run dialogs)
    app = QApplication.instance()
    if app is None:
        # High DPI support - must be called before creating QApplication
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)

    app.setApplicationName("AirDocs")
    app.setOrganizationName("AWB")
    app.setApplicationVersion(VERSION)

    # Set style
    app.setStyle("Fusion")

    # Global validation error styles (used via hasError dynamic property)
    error_qss = """
    QLineEdit[hasError="true"],
    QSpinBox[hasError="true"],
    QDoubleSpinBox[hasError="true"],
    QComboBox[hasError="true"],
    QDateEdit[hasError="true"],
    QTextEdit[hasError="true"] {
        border: 2px solid #dc3545;
        border-radius: 3px;
        background-color: #fff5f5;
    }
    QLineEdit[hasError="true"]:hover,
    QComboBox[hasError="true"]:hover {
        border: 2px solid #c82333;
    }
    """
    existing_qss = app.styleSheet()
    if existing_qss:
        app.setStyleSheet(existing_qss + "\n" + error_qss)
    else:
        app.setStyleSheet(error_qss)

    # Check for pending updates (must be after QApplication is created)
    check_pending_update()

    # Create main window
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    return app.exec()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AirDocs - Logistics Document Management"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with verbose logging"
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Reset database (WARNING: deletes all data)"
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Run environment diagnostics and exit"
    )

    args = parser.parse_args()

    # Validate VC++ runtime before logging setup or any Qt imports.
    check_vcredist_dependencies()

    # Ensure data directories exist before logging setup
    ensure_data_dirs()

    # Setup logging
    logger = setup_logging(debug=args.debug)
    logger.info("Starting AirDocs...")
    logger.info(f"Application version: {get_version()}")

    # Create QApplication once in entrypoint before any Qt UI code.
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    app = QApplication.instance()
    if app is None:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)

    # Apply pending update (must be before init to avoid file locks)
    if not apply_pending_update():
        logger.error("Failed to apply pending update")
        # Continue anyway - user can retry later

    # Initialize application
    if not init_application():
        logger.critical("Application initialization failed. See logs for details.")
        from core.app_context import get_context
        try:
            context = get_context()
            log_path = context.get_path("logs_dir") / "app.log"
            print(f"\nПроверьте логи для деталей: {log_path}")
        except Exception:
            pass
        return 1

    # Handle first run
    if not handle_first_run():
        logger.critical("First run setup failed")
        print("ERROR: First run setup failed")
        return 1

    # Log successful initialization with diagnostics
    logger.info("=" * 60)
    logger.info("Application initialized successfully")
    logger.info(f"Version: {VERSION}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    from core.app_context import get_context
    context = get_context()
    logger.info(f"App directory: {context.app_dir}")
    logger.info(f"Data directory: {context.user_dir}")
    logger.info(f"Database: {context.get_path('database')}")
    logger.info("=" * 60)

    # Cleanup old version after update
    cleanup_old_version()

    # Check for updates from GitHub
    check_for_github_updates()

    # Handle special commands
    if args.reset_db:
        confirm = input("WARNING: This will delete all data. Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            return 0 if reset_database() else 1
        else:
            print("Cancelled.")
            return 0

    if args.diagnostics:
        return run_diagnostics()

    # Check templates
    check_templates()

    # Run GUI (pending update check happens after QApplication is created)
    logger.info("Starting GUI...")
    exit_code = run_gui(debug=args.debug)

    logger.info(f"Application exiting with code {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
