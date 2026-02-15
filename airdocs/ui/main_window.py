# AirDocs - Main Window
# =====================

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QMenuBar,
    QMenu,
    QStatusBar,
    QLabel,
    QMessageBox,
    QToolBar,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon

from core.app_context import get_context
from core.constants import APP_NAME
from core.version import VERSION

logger = logging.getLogger("airdocs.ui")


class MainWindow(QMainWindow):
    """
    Main application window.

    Contains:
    - Menu bar (Файл, Правка, Справочники, Настройки, Помощь)
    - Tab widget with modules (Бронирование, Местная доставка, Комплекты счетов, Реестры 1С)
    - Status bar
    """

    def __init__(self):
        super().__init__()
        self._context = get_context()
        self._update_info = None
        self._update_checker_thread = None

        self._init_ui()
        self._init_menu()
        self._init_tabs()
        self._init_status_bar()

        logger.info("Main window initialized")

    def _init_ui(self):
        """Initialize main UI properties."""
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")

        # Get size from config
        ui_config = self._context.config.get("ui", {})
        width = ui_config.get("window_width", 1400)
        height = ui_config.get("window_height", 900)

        self.resize(width, height)
        self.setMinimumSize(1000, 700)

        # Center on screen
        screen = self.screen().geometry()
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        self.move(x, y)

    def _init_menu(self):
        """Initialize menu bar."""
        menubar = self.menuBar()

        # === Файл menu ===
        file_menu = menubar.addMenu("Файл")

        new_action = QAction("Новый AWB", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._on_new_awb)
        file_menu.addAction(new_action)

        open_action = QAction("Открыть...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        export_action = QAction("Экспорт...", self)
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # === Правка menu ===
        edit_menu = menubar.addMenu("Правка")

        refresh_action = QAction("Обновить", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._on_refresh)
        edit_menu.addAction(refresh_action)

        # === Справочники menu ===
        ref_menu = menubar.addMenu("Справочники")

        parties_action = QAction("Контрагенты...", self)
        parties_action.triggered.connect(self._on_manage_parties)
        ref_menu.addAction(parties_action)

        presets_action = QAction("Пресеты...", self)
        presets_action.triggered.connect(self._on_manage_presets)
        ref_menu.addAction(presets_action)

        # === Настройки menu ===
        settings_menu = menubar.addMenu("Настройки")

        diagnostics_action = QAction("Диагностика окружения...", self)
        diagnostics_action.triggered.connect(self._on_diagnostics)
        settings_menu.addAction(diagnostics_action)

        db_check_action = QAction("Проверить базу данных...", self)
        db_check_action.triggered.connect(self._on_check_database)
        settings_menu.addAction(db_check_action)
        calibration_action = QAction("Калибровка AWB PDF...", self)
        calibration_action.triggered.connect(self._on_calibration)
        settings_menu.addAction(calibration_action)

        settings_menu.addSeparator()

        open_data_action = QAction("Открыть папку данных", self)
        open_data_action.triggered.connect(self._on_open_data_folder)
        settings_menu.addAction(open_data_action)

        # === Помощь menu ===
        help_menu = menubar.addMenu("Помощь")

        about_action = QAction("О программе...", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _init_tabs(self):
        """Initialize tab widget with modules."""
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Lazy-load modules
        from ui.modules.booking_module import BookingModule
        from ui.modules.delivery_module import DeliveryModule
        from ui.modules.invoice_sets_module import InvoiceSetsModule
        from ui.modules.registry_1c_module import Registry1CModule

        # Add modules as tabs
        self.booking_module = BookingModule()
        self.tab_widget.addTab(self.booking_module, "Бронирование")

        self.delivery_module = DeliveryModule()
        self.tab_widget.addTab(self.delivery_module, "Местная доставка")

        self.invoice_sets_module = InvoiceSetsModule()
        self.tab_widget.addTab(self.invoice_sets_module, "Комплекты счетов")

        self.registry_module = Registry1CModule()
        self.tab_widget.addTab(self.registry_module, "Реестры 1С")

    def _init_status_bar(self):
        """Initialize status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово")

        self.db_status_label = QLabel()
        self.db_status_label.setText("🗄️ БД: Загрузка...")
        self.status_bar.addPermanentWidget(self.db_status_label)
        self._update_db_status()

    def _update_db_status(self):
        """Update database status indicator in status bar."""
        try:
            from data.database import get_db

            stats = get_db().get_database_stats(mode="fast")
            total = stats.table_counts.get("shipments", 0)

            if not stats.is_healthy:
                self.db_status_label.setText("🗄️ БД: Ошибка")
                self.db_status_label.setStyleSheet("color: #FF0000;")
            elif not stats.integrity_checked:
                self.db_status_label.setText(f"🗄️ БД: Не проверена | Отправлений: {total}")
                self.db_status_label.setStyleSheet("color: #CC8400;")
            elif stats.integrity_ok:
                self.db_status_label.setText(f"🗄️ БД: OK | Отправлений: {total}")
                self.db_status_label.setStyleSheet("color: #00AA00;")
            else:
                self.db_status_label.setText(f"🗄️ БД: Ошибка целостности | Отправлений: {total}")
                self.db_status_label.setStyleSheet("color: #FF0000;")

            size_mb = stats.db_size_bytes / 1024 / 1024
            schema_text = (
                str(stats.schema_version)
                if stats.schema_version is not None
                else "неизвестно"
            )
            if not stats.integrity_checked:
                integrity_text = "не проверена"
            elif stats.integrity_ok:
                integrity_text = "OK"
            else:
                integrity_text = "ошибка"

            details = [
                f"Размер БД: {size_mb:.2f} MB",
                f"Версия схемы: {schema_text}",
                f"Отправления: {total}",
                f"Целостность: {integrity_text}",
            ]

            if stats.integrity_checked and stats.integrity_ok is False and stats.integrity_errors:
                details.append(f"Ошибки: {'; '.join(stats.integrity_errors)}")
            elif stats.error_message:
                details.append(f"Ошибка: {stats.error_message}")

            self.db_status_label.setToolTip(
                "\n".join(details)
            )

        except Exception as e:
            logger.error(f"Failed to update database status: {e}", exc_info=True)
            self.db_status_label.setText("🗄️ БД: Ошибка")
            self.db_status_label.setStyleSheet("color: #FF0000;")
            self.db_status_label.setToolTip(str(e))

    def show_status(self, message: str, timeout: int = 5000):
        """Show message in status bar."""
        self.status_bar.showMessage(message, timeout)

    def show_error(self, title: str, message: str):
        """Show error dialog."""
        QMessageBox.critical(self, title, message)

    def show_warning(self, title: str, message: str):
        """Show warning dialog."""
        QMessageBox.warning(self, title, message)

    def show_info(self, title: str, message: str):
        """Show info dialog."""
        QMessageBox.information(self, title, message)

    # === Menu handlers ===

    def _on_new_awb(self):
        """Handle new AWB action."""
        # Switch to booking tab and create new
        self.tab_widget.setCurrentWidget(self.booking_module)
        self.booking_module.create_new_shipment()

    def _on_open(self):
        """Handle open action."""
        self.tab_widget.setCurrentWidget(self.booking_module)
        # Could open a search dialog here

    def _on_export(self):
        """Handle export action."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Экспорт пока недоступен")
        msg.setText(
            "Функция экспорта данных находится в разработке.\n\n"
            "Вы можете вручную скопировать данные из папки с выходными файлами."
        )

        open_folder_btn = msg.addButton("Открыть папку с данными", QMessageBox.ActionRole)
        close_btn = msg.addButton("Закрыть", QMessageBox.RejectRole)

        msg.exec()

        if msg.clickedButton() == open_folder_btn:
            self._on_open_data_folder()

    def _on_refresh(self):
        """Handle refresh action."""
        # Refresh current module
        current = self.tab_widget.currentWidget()
        if hasattr(current, "refresh"):
            current.refresh()
        self._update_db_status()
        self.show_status("Данные обновлены")

    def _on_manage_parties(self):
        """Open parties management dialog."""
        from ui.dialogs.party_edit_dialog import PartyManagementDialog
        dialog = PartyManagementDialog(self)
        dialog.exec()

    def _on_manage_presets(self):
        """Open presets management dialog."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Пресеты пока недоступны")
        msg.setText(
            "Функция управления пресетами находится в разработке.\n\n"
            "Вы можете скопировать существующую отправку в модуле Бронирование."
        )

        open_booking_btn = msg.addButton("Открыть Бронирование", QMessageBox.ActionRole)
        close_btn = msg.addButton("Закрыть", QMessageBox.RejectRole)

        msg.exec()

        if msg.clickedButton() == open_booking_btn:
            self.tab_widget.setCurrentWidget(self.booking_module)

    def _on_diagnostics(self):
        """Open environment diagnostics dialog."""
        from ui.dialogs.environment_dialog import EnvironmentDialog
        dialog = EnvironmentDialog(self)
        dialog.exec()
        self._update_db_status()

    def _on_check_database(self):
        """Open environment diagnostics dialog on database tab."""
        from ui.dialogs.environment_dialog import EnvironmentDialog

        dialog = EnvironmentDialog(self)
        dialog.switch_to_database_tab()
        dialog.exec()
        self._update_db_status()

    def _on_calibration(self):
        """Open AWB PDF calibration dialog."""
        from ui.dialogs.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(self)
        dialog.exec()

    def _on_open_data_folder(self):
        """Open data folder in file explorer."""
        import subprocess
        data_path = self._context.get_path("data_dir")
        data_path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{data_path}"')

    def _on_about(self):
        """Show about dialog."""
        about_text = f"""
<h2>{APP_NAME}</h2>
<p>Версия {VERSION}</p>
<p>Desktop-приложение для автоматизации логистического документооборота</p>
<hr>
<p><b>Возможности:</b></p>
<ul>
<li>Создание и управление AWB</li>
<li>Генерация документов (счета, УПД, акты)</li>
<li>Формирование комплектов для отправки</li>
<li>Реестры для импорта в 1С</li>
</ul>
<hr>
<p>Python {self._get_python_version()}</p>
<p>PySide6 (Qt)</p>
"""
        QMessageBox.about(self, f"О программе {APP_NAME}", about_text)

    def _get_python_version(self):
        """Get Python version string."""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def showEvent(self, event):
        """Start update check after window is shown."""
        super().showEvent(event)
        if not self._update_checker_thread:
            self._start_update_check()

    def _start_update_check(self):
        """Start background update check."""
        from ui.dialogs.update_dialog import UpdateCheckerThread

        config = self._context.config.get('updater', {})

        if not config.get('check_on_startup', True):
            return

        self._update_checker_thread = UpdateCheckerThread()
        self._update_checker_thread.update_available.connect(self._on_update_available)
        self._update_checker_thread.no_update.connect(self._on_no_update)
        self._update_checker_thread.check_failed.connect(self._on_update_check_failed)
        self._update_checker_thread.start()

    def _on_update_available(self, update_info):
        """Handle available update."""
        self._update_info = update_info

        # Show in status bar
        self.status_bar.showMessage(
            f"Доступно обновление: {update_info.version}",
            0  # Permanent
        )

        # Add menu item
        self._add_update_menu_item(update_info.version)

    def _on_no_update(self):
        """Handle no update available."""
        logger.info("No updates available")

    def _on_update_check_failed(self, error):
        """Handle update check failure."""
        logger.warning(f"Update check failed: {error}")

    def _add_update_menu_item(self, version):
        """Add update menu item to Help menu."""
        help_menu = None
        for action in self.menuBar().actions():
            if action.text() == "Помощь":
                help_menu = action.menu()
                break

        if not help_menu:
            return

        update_action = QAction(f"Обновить до версии {version}...", self)
        update_action.triggered.connect(self._on_check_updates)

        # Insert before "О программе"
        actions = help_menu.actions()
        if actions:
            help_menu.insertAction(actions[-1], update_action)
            help_menu.insertSeparator(actions[-1])

    def _on_check_updates(self):
        """Open update dialog."""
        if self._update_info:
            from ui.dialogs.update_dialog import UpdateDialog
            dialog = UpdateDialog(self._update_info, self)
            dialog.exec()

    def closeEvent(self, event):
        """Handle window close."""
        # Save window size to config
        try:
            current_size = self.size()
            ui_settings = {
                "window_width": current_size.width(),
                "window_height": current_size.height()
            }
            self._context.save_ui_config(ui_settings)
        except Exception as e:
            logger.error(f"Failed to save window size: {e}", exc_info=True)

        logger.info("Application closing")
        event.accept()
