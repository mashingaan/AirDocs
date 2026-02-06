# AirDocs - Environment Diagnostics Dialog
# ===============================================

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from integrations.environment_checker import EnvironmentChecker, EnvironmentStatus

if TYPE_CHECKING:
    from data.database import DatabaseStats

logger = logging.getLogger("airdocs.ui")


class CheckerThread(QThread):
    """Background thread for environment checks."""

    finished = Signal(EnvironmentStatus)

    def run(self):
        checker = EnvironmentChecker()
        status = checker.check_all()
        self.finished.emit(status)


class DatabaseStatsThread(QThread):
    """Background thread for database statistics collection."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        mode: str = "full",
        include_integrity: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._mode = mode
        self._include_integrity = include_integrity

    def run(self):
        try:
            from data.database import get_db

            stats = get_db().get_database_stats(
                mode=self._mode,
                include_integrity=self._include_integrity,
            )
            self.finished.emit(stats)
        except Exception as e:
            self.failed.emit(str(e))


class StatusIndicator(QFrame):
    """Visual status indicator (colored circle)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._color = QColor("#808080")
        self.setStyleSheet(self._build_style())

    def _build_style(self) -> str:
        return f"""
            background-color: {self._color.name()};
            border-radius: 8px;
            border: 1px solid #404040;
        """

    def set_status(self, available: bool, critical: bool = False):
        """Set indicator color based on status."""
        if available:
            self._color = QColor("#00AA00")
        elif critical:
            self._color = QColor("#FF0000")
        else:
            self._color = QColor("#FFA500")
        self.setStyleSheet(self._build_style())


class ComponentStatusWidget(QGroupBox):
    """Widget displaying status of a single component."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        status_layout = QHBoxLayout()
        self.indicator = StatusIndicator()
        status_layout.addWidget(self.indicator)

        self.status_label = QLabel("Checking...")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        self.details_label.setStyleSheet("color: #606060; font-size: 11px;")
        layout.addWidget(self.details_label)

    def set_status(
        self,
        available: bool,
        status_text: str,
        details: str = "",
        critical: bool = False,
    ):
        """Update component status display."""
        self.indicator.set_status(available, critical)
        self.status_label.setText(status_text)
        if available:
            self.status_label.setStyleSheet("font-weight: bold; color: #00AA00;")
        elif critical:
            self.status_label.setStyleSheet("font-weight: bold; color: #FF0000;")
        else:
            self.status_label.setStyleSheet("font-weight: bold; color: #FFA500;")
        self.details_label.setText(details)


class EnvironmentDialog(QDialog):
    """Dialog showing environment diagnostics."""

    TAB_DB_NAME = "\u0411\u0430\u0437\u0430 \u0434\u0430\u043d\u043d\u044b\u0445"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checker_thread = None
        self._db_stats_thread = None
        self._integrity_thread = None
        self._status: EnvironmentStatus | None = None
        self._db_stats: "DatabaseStats | None" = None
        self._database_tab_index: int | None = None
        self._integrity_ok: bool | None = None
        self._integrity_errors: list[str] = []

        self._init_ui()
        self._run_checks()

    def _init_ui(self):
        self.setWindowTitle("\u0414\u0438\u0430\u0433\u043d\u043e\u0441\u0442\u0438\u043a\u0430 \u043e\u043a\u0440\u0443\u0436\u0435\u043d\u0438\u044f")
        self.setMinimumSize(700, 760)

        layout = QVBoxLayout(self)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        self._init_database_tab()
        self._init_components_tab()
        self._init_diagnostics_tab()

        button_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("\u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c")
        self.refresh_btn.clicked.connect(self._run_checks)
        button_layout.addWidget(self.refresh_btn)

        export_btn = QPushButton("\u042d\u043a\u0441\u043f\u043e\u0440\u0442 \u043e\u0442\u0447\u0435\u0442\u0430...")
        export_btn.clicked.connect(self._on_export_report)
        button_layout.addWidget(export_btn)

        button_layout.addStretch()

        close_btn = QPushButton("\u0417\u0430\u043a\u0440\u044b\u0442\u044c")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _init_database_tab(self):
        database_widget = QWidget()
        database_layout = QVBoxLayout(database_widget)

        header = QLabel("\u0418\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044f \u043e \u0431\u0430\u0437\u0435 \u0434\u0430\u043d\u043d\u044b\u0445")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        database_layout.addWidget(header)

        general_group = QGroupBox("\u041e\u0431\u0449\u0430\u044f \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044f")
        general_layout = QVBoxLayout(general_group)
        self.db_path_label = QLabel("\u041f\u0443\u0442\u044c \u043a \u0411\u0414: \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...")
        self.db_size_label = QLabel("\u0420\u0430\u0437\u043c\u0435\u0440 \u0411\u0414: \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...")
        self.db_version_label = QLabel("\u0412\u0435\u0440\u0441\u0438\u044f \u0441\u0445\u0435\u043c\u044b: \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...")
        self.db_health_label = QLabel("\u0421\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435: \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...")
        general_layout.addWidget(self.db_path_label)
        general_layout.addWidget(self.db_size_label)
        general_layout.addWidget(self.db_version_label)
        general_layout.addWidget(self.db_health_label)
        database_layout.addWidget(general_group)

        tables_group = QGroupBox("\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430 \u0442\u0430\u0431\u043b\u0438\u0446")
        tables_layout = QVBoxLayout(tables_group)
        self.db_tables_text = QTextEdit()
        self.db_tables_text.setReadOnly(True)
        self.db_tables_text.setFontFamily("Consolas, Courier New, monospace")
        tables_layout.addWidget(self.db_tables_text)
        database_layout.addWidget(tables_group)

        integrity_group = QGroupBox("\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438")
        integrity_layout = QVBoxLayout(integrity_group)
        self.db_integrity_text = QTextEdit()
        self.db_integrity_text.setReadOnly(True)
        self.db_integrity_text.setMinimumHeight(120)
        self.db_integrity_text.setPlainText("\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043d\u0435 \u0437\u0430\u043f\u0443\u0441\u043a\u0430\u043b\u0430\u0441\u044c.")
        integrity_layout.addWidget(self.db_integrity_text)

        self.db_integrity_btn = QPushButton("\u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u044c")
        self.db_integrity_btn.clicked.connect(self._on_check_integrity)
        integrity_layout.addWidget(self.db_integrity_btn)

        database_layout.addWidget(integrity_group)
        self._database_tab_index = self.tab_widget.addTab(database_widget, self.TAB_DB_NAME)

    def _init_components_tab(self):
        components_widget = QWidget()
        components_layout = QVBoxLayout(components_widget)

        header = QLabel("\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043a\u043e\u043c\u043f\u043e\u043d\u0435\u043d\u0442\u043e\u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u044b")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        components_layout.addWidget(header)

        self.office_status = ComponentStatusWidget("Microsoft Office")
        components_layout.addWidget(self.office_status)

        self.libreoffice_status = ComponentStatusWidget("LibreOffice")
        components_layout.addWidget(self.libreoffice_status)

        self.awb_editor_status = ComponentStatusWidget("AWB Editor")
        components_layout.addWidget(self.awb_editor_status)

        self.pdf_summary = QGroupBox("PDF")
        pdf_layout = QVBoxLayout(self.pdf_summary)
        self.pdf_status_label = QLabel("Checking...")
        self.pdf_status_label.setWordWrap(True)
        pdf_layout.addWidget(self.pdf_status_label)
        components_layout.addWidget(self.pdf_summary)

        report_group = QGroupBox("Report")
        report_layout = QVBoxLayout(report_group)
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setMinimumHeight(150)
        report_layout.addWidget(self.report_text)
        components_layout.addWidget(report_group)

        self.tab_widget.addTab(components_widget, "\u041a\u043e\u043c\u043f\u043e\u043d\u0435\u043d\u0442\u044b")

    def _init_diagnostics_tab(self):
        diagnostics_widget = QWidget()
        diagnostics_layout = QVBoxLayout(diagnostics_widget)

        header = QLabel("\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f \u0434\u0438\u0430\u0433\u043d\u043e\u0441\u0442\u0438\u043a\u0430")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        diagnostics_layout.addWidget(header)

        self.full_report_text = QTextEdit()
        self.full_report_text.setReadOnly(True)
        self.full_report_text.setFontFamily("Consolas, Courier New, monospace")
        diagnostics_layout.addWidget(self.full_report_text)

        generate_btn = QPushButton("\u0421\u0444\u043e\u0440\u043c\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043f\u043e\u043b\u043d\u044b\u0439 \u043e\u0442\u0447\u0435\u0442")
        generate_btn.clicked.connect(self._generate_full_report)
        diagnostics_layout.addWidget(generate_btn)

        self.tab_widget.addTab(diagnostics_widget, "\u041f\u043e\u0434\u0440\u043e\u0431\u043d\u0430\u044f \u0434\u0438\u0430\u0433\u043d\u043e\u0441\u0442\u0438\u043a\u0430")

    def _run_checks(self):
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.refresh_btn.setEnabled(False)

        for widget in [self.office_status, self.libreoffice_status, self.awb_editor_status]:
            widget.set_status(False, "Checking...", "")

        self.pdf_status_label.setText("Checking...")
        self.report_text.clear()

        self._db_stats = None
        self._update_database_tab()

        try:
            from data.database import get_db

            self._db_stats = get_db().get_database_stats(mode="fast")
            self._update_database_tab()
        except Exception as e:
            logger.error(f"Failed to collect fast database stats: {e}", exc_info=True)
            self.db_health_label.setText("\u2717 \u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u044b")
            self.db_health_label.setStyleSheet("color: #FF0000; font-weight: bold;")
            self.db_tables_text.setPlainText(f"\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u044f \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0438 \u0411\u0414:\n{e}")

        if self._db_stats_thread and self._db_stats_thread.isRunning():
            self._db_stats_thread.quit()
            self._db_stats_thread.wait(1000)

        self._db_stats_thread = DatabaseStatsThread(
            mode="full",
            include_integrity=True,
        )
        self._db_stats_thread.finished.connect(self._on_full_db_stats_ready)
        self._db_stats_thread.failed.connect(self._on_full_db_stats_failed)
        self._db_stats_thread.start()

        self._checker_thread = CheckerThread()
        self._checker_thread.finished.connect(self._on_checks_complete)
        self._checker_thread.start()

    def _on_full_db_stats_ready(self, stats):
        self._db_stats = stats
        if stats.integrity_checked:
            self._integrity_ok = stats.integrity_ok
            self._integrity_errors = list(stats.integrity_errors)
            self._set_integrity_text(stats.integrity_ok, stats.integrity_errors)
        self._update_database_tab()

    def _on_full_db_stats_failed(self, error: str):
        logger.error(f"Failed to collect full database stats: {error}")

    def _update_database_tab(self):
        if self._db_stats is None:
            self.db_path_label.setText("\u041f\u0443\u0442\u044c \u043a \u0411\u0414: \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...")
            self.db_size_label.setText("\u0420\u0430\u0437\u043c\u0435\u0440 \u0411\u0414: \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...")
            self.db_version_label.setText("\u0412\u0435\u0440\u0441\u0438\u044f \u0441\u0445\u0435\u043c\u044b: \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...")
            self.db_health_label.setText("\u0421\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435: \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...")
            self.db_health_label.setStyleSheet("")
            self.db_tables_text.setPlainText("\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...")
            return

        stats = self._db_stats
        size_mb = stats.db_size_bytes / 1024 / 1024
        self.db_path_label.setText(f"\u041f\u0443\u0442\u044c \u043a \u0411\u0414: {stats.db_path}")
        self.db_size_label.setText(f"\u0420\u0430\u0437\u043c\u0435\u0440 \u0411\u0414: {size_mb:.2f} MB")

        if stats.schema_version is None:
            self.db_version_label.setText("\u0412\u0435\u0440\u0441\u0438\u044f \u0441\u0445\u0435\u043c\u044b: \u043d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e")
        else:
            migration = stats.last_migration if stats.last_migration else "\u043d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e"
            self.db_version_label.setText(
                f"\u0412\u0435\u0440\u0441\u0438\u044f \u0441\u0445\u0435\u043c\u044b: {stats.schema_version} (\u043f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u043c\u0438\u0433\u0440\u0430\u0446\u0438\u044f: {migration})"
            )

        if not stats.is_healthy:
            error_part = f" ({stats.error_message})" if stats.error_message else ""
            self.db_health_label.setText(f"\u2717 \u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u044b{error_part}")
            self.db_health_label.setStyleSheet("color: #FF0000; font-weight: bold;")
        elif not stats.integrity_checked:
            self.db_health_label.setText("\u26A0 \u0426\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u044c \u043d\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u0430 (\u0441\u0442\u0430\u0442\u0443\u0441 \u043d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u0435\u043d)")
            self.db_health_label.setStyleSheet("color: #CC8400; font-weight: bold;")
        elif stats.integrity_ok:
            self.db_health_label.setText("\u2713 \u0411\u0430\u0437\u0430 \u0434\u0430\u043d\u043d\u044b\u0445 \u0432 \u043f\u043e\u0440\u044f\u0434\u043a\u0435")
            self.db_health_label.setStyleSheet("color: #00AA00; font-weight: bold;")
        else:
            error_details = "; ".join(stats.integrity_errors) if stats.integrity_errors else ""
            suffix = f" ({error_details})" if error_details else ""
            self.db_health_label.setText(f"\u2717 \u041e\u0448\u0438\u0431\u043a\u0430 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438{suffix}")
            self.db_health_label.setStyleSheet("color: #FF0000; font-weight: bold;")

        table_rows = [
            ("\u041a\u043e\u043d\u0442\u0440\u0430\u0433\u0435\u043d\u0442\u044b (parties)", "parties"),
            ("\u0428\u0430\u0431\u043b\u043e\u043d\u044b (templates)", "templates"),
            ("\u041e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f (shipments)", "shipments"),
            ("\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b (documents)", "documents"),
            ("Email \u0447\u0435\u0440\u043d\u043e\u0432\u0438\u043a\u0438", "email_drafts"),
            ("\u0416\u0443\u0440\u043d\u0430\u043b \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0439", "audit_log"),
            ("\u041a\u0430\u043b\u0438\u0431\u0440\u043e\u0432\u043a\u0430 AWB", "awb_overlay_calibration"),
            ("\u0414\u0438\u0430\u0433\u043d\u043e\u0441\u0442\u0438\u043a\u0430 \u043e\u043a\u0440\u0443\u0436\u0435\u043d\u0438\u044f", "environment_diagnostics"),
            ("\u0418\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044f \u043e \u0437\u0430\u043f\u0443\u0441\u043a\u0435", "first_run_info"),
        ]

        lines = [
            "\u0422\u0430\u0431\u043b\u0438\u0446\u0430                    | \u0417\u0430\u043f\u0438\u0441\u0435\u0439",
            "----------------------------------------",
        ]
        for title, key in table_rows:
            value = stats.table_counts.get(key, 0)
            lines.append(f"{title:<26} | {value}")

        self.db_tables_text.setPlainText("\n".join(lines))

    def _on_check_integrity(self):
        self.db_integrity_btn.setEnabled(False)
        self.db_integrity_text.setPlainText("\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438...")

        if self._integrity_thread and self._integrity_thread.isRunning():
            return

        self._integrity_thread = DatabaseStatsThread(
            mode="full",
            include_integrity=True,
        )
        self._integrity_thread.finished.connect(self._on_integrity_check_complete)
        self._integrity_thread.failed.connect(self._on_integrity_check_failed)
        self._integrity_thread.start()

    def _on_integrity_check_complete(self, stats):
        self._db_stats = stats
        self._integrity_ok = stats.integrity_ok
        self._integrity_errors = list(stats.integrity_errors)
        self._set_integrity_text(stats.integrity_ok, stats.integrity_errors)
        self._update_database_tab()
        self.db_integrity_btn.setEnabled(True)

    def _on_integrity_check_failed(self, error: str):
        logger.error(f"Failed to run integrity check: {error}", exc_info=True)
        self._integrity_ok = False
        self._integrity_errors = [error]
        self.db_integrity_text.setPlainText(
            f"\u2717 \u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438:\n{error}"
        )
        self.db_integrity_btn.setEnabled(True)

    def _set_integrity_text(self, is_ok: bool | None, errors: list[str]):
        if is_ok is True:
            self.db_integrity_text.setPlainText(
                "\u2713 \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438 \u043f\u0440\u043e\u0439\u0434\u0435\u043d\u0430 \u0443\u0441\u043f\u0435\u0448\u043d\u043e"
            )
            return

        if is_ok is False:
            lines = [
                "\u2717 \u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b \u043e\u0448\u0438\u0431\u043a\u0438 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438:",
                "",
            ]
            lines.extend(f"- {error}" for error in errors)
            self.db_integrity_text.setPlainText("\n".join(lines))
            return

        self.db_integrity_text.setPlainText(
            "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438 \u043d\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u044f\u043b\u0430\u0441\u044c."
        )

    def switch_to_database_tab(self):
        if self._database_tab_index is not None:
            self.tab_widget.setCurrentIndex(self._database_tab_index)
            return

        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == self.TAB_DB_NAME:
                self.tab_widget.setCurrentIndex(i)
                return

    def _on_checks_complete(self, status: EnvironmentStatus):
        self._status = status
        self.progress.setVisible(False)
        self.refresh_btn.setEnabled(True)

        office = status.office
        if office.available:
            self.office_status.set_status(True, f"Available ({office.version or 'unknown'})", office.path or "")
        else:
            self.office_status.set_status(False, "Not found", office.message or "Microsoft Office is not available via COM")

        libre = status.libreoffice
        if libre.available:
            self.libreoffice_status.set_status(True, f"Available ({libre.version or 'unknown'})", libre.path or "")
        else:
            self.libreoffice_status.set_status(False, "Not found", libre.message or "LibreOffice is not installed")

        awb = status.awb_editor
        if awb.available:
            self.awb_editor_status.set_status(True, "Available", awb.path or "")
        else:
            self.awb_editor_status.set_status(False, "Not configured" if not awb.message else "Not found", awb.message or "AWB Editor is not configured")

        self._update_pdf_summary(status)
        self._generate_report(status)

    def _update_pdf_summary(self, status: EnvironmentStatus):
        if status.pdf_conversion_available:
            methods = []
            if status.office.available:
                methods.append("Office COM (primary)")
            if status.libreoffice.available:
                methods.append("LibreOffice (fallback)")

            self.pdf_status_label.setText("PDF conversion is available\n\nMethods:\n- " + "\n- ".join(methods))
            self.pdf_status_label.setStyleSheet("color: #00AA00;")
        else:
            self.pdf_status_label.setText(
                "PDF conversion is not available\n\n"
                "Install Microsoft Office or LibreOffice to enable DOCX/XLSX to PDF conversion."
            )
            self.pdf_status_label.setStyleSheet("color: #FF0000;")

    def _generate_report(self, status: EnvironmentStatus):
        lines = [
            "=" * 50,
            "ENVIRONMENT DIAGNOSTIC REPORT",
            "=" * 50,
            "",
            "MICROSOFT OFFICE",
            "-" * 30,
            f"  Status: {'Available' if status.office.available else 'Unavailable'}",
        ]

        if status.office.available:
            lines.append(f"  Version: {status.office.version or 'unknown'}")
            if status.office.path:
                lines.append(f"  Path: {status.office.path}")
        else:
            lines.append(f"  Reason: {status.office.message or 'not installed'}")

        lines.extend([
            "",
            "LIBREOFFICE",
            "-" * 30,
            f"  Status: {'Available' if status.libreoffice.available else 'Unavailable'}",
        ])

        if status.libreoffice.available:
            lines.append(f"  Version: {status.libreoffice.version or 'unknown'}")
            if status.libreoffice.path:
                lines.append(f"  Path: {status.libreoffice.path}")
        else:
            lines.append(f"  Reason: {status.libreoffice.message or 'not installed'}")

        lines.extend([
            "",
            "AWB EDITOR",
            "-" * 30,
            f"  Status: {'Available' if status.awb_editor.available else 'Unavailable'}",
        ])

        if status.awb_editor.available and status.awb_editor.path:
            lines.append(f"  Path: {status.awb_editor.path}")
        elif not status.awb_editor.available:
            lines.append(f"  Reason: {status.awb_editor.message or 'not configured'}")

        lines.extend([
            "",
            "CAPABILITIES",
            "-" * 30,
            f"  PDF conversion: {'Yes' if status.pdf_conversion_available else 'No'}",
            f"  AWB generation: {'AWB Editor' if status.awb_editor.available else 'Overlay (built-in)'}",
            "",
            "=" * 50,
        ])

        self.report_text.setPlainText("\n".join(lines))

    def _generate_full_report(self):
        try:
            from utils.system_info import generate_diagnostic_report

            self.full_report_text.setPlainText("\u0421\u0431\u043e\u0440 \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u0438...")
            report = generate_diagnostic_report()
            report = f"{report}\n\n{self._build_database_report_section()}"
            self.full_report_text.setPlainText(report)

        except Exception as e:
            logger.error(f"Failed to generate diagnostic report: {e}")
            self.full_report_text.setPlainText(f"\u041e\u0448\u0438\u0431\u043a\u0430 \u0444\u043e\u0440\u043c\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f \u043e\u0442\u0447\u0435\u0442\u0430:\n\n{e}")

    def _on_export_report(self):
        try:
            from utils.system_info import generate_diagnostic_report

            report = generate_diagnostic_report()
            report = f"{report}\n\n{self._build_database_report_section()}"

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"AWB_Diagnostic_Report_{timestamp}.txt"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u043e\u0442\u0447\u0435\u0442",
                default_name,
                "Text Files (*.txt);;All Files (*)",
            )

            if not file_path:
                return

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report)

            QMessageBox.information(
                self,
                "\u0423\u0441\u043f\u0435\u0445",
                f"\u041e\u0442\u0447\u0435\u0442 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d:\n{file_path}",
            )

        except Exception as e:
            logger.error(f"Failed to export diagnostic report: {e}")
            QMessageBox.critical(
                self,
                "\u041e\u0448\u0438\u0431\u043a\u0430",
                f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u043e\u0442\u0447\u0435\u0442:\n\n{e}",
            )

    def _build_database_report_section(self) -> str:
        lines = [
            "=" * 50,
            "\u0418\u041d\u0424\u041e\u0420\u041c\u0410\u0426\u0418\u042f \u041e \u0411\u0410\u0417\u0415 \u0414\u0410\u041d\u041d\u042b\u0425",
            "=" * 50,
        ]

        if self._db_stats is None:
            lines.append("\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430 \u0411\u0414 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430.")
        else:
            stats = self._db_stats
            size_mb = stats.db_size_bytes / 1024 / 1024
            schema = str(stats.schema_version) if stats.schema_version is not None else "\u043d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e"
            lines.extend([
                f"\u041f\u0443\u0442\u044c \u043a \u0411\u0414: {stats.db_path}",
                f"\u0420\u0430\u0437\u043c\u0435\u0440 \u0411\u0414: {size_mb:.2f} MB",
                f"\u0412\u0435\u0440\u0441\u0438\u044f \u0441\u0445\u0435\u043c\u044b: {schema}",
                "",
                "\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430 \u0442\u0430\u0431\u043b\u0438\u0446:",
            ])
            for key, value in stats.table_counts.items():
                lines.append(f"- {key}: {value}")

        lines.append("")
        lines.append("\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438:")
        if self._integrity_ok is True:
            lines.append("\u2713 \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438 \u043f\u0440\u043e\u0439\u0434\u0435\u043d\u0430 \u0443\u0441\u043f\u0435\u0448\u043d\u043e")
        elif self._integrity_ok is False:
            lines.append("\u2717 \u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b \u043e\u0448\u0438\u0431\u043a\u0438 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438")
            lines.extend(f"- {error}" for error in self._integrity_errors)
        else:
            lines.append("\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0446\u0435\u043b\u043e\u0441\u0442\u043d\u043e\u0441\u0442\u0438 \u043d\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u044f\u043b\u0430\u0441\u044c")

        return "\n".join(lines)

    def get_status(self) -> EnvironmentStatus | None:
        return self._status

    def closeEvent(self, event):
        if self._checker_thread and self._checker_thread.isRunning():
            self._checker_thread.wait(1000)
        if self._db_stats_thread and self._db_stats_thread.isRunning():
            self._db_stats_thread.wait(1000)
        if self._integrity_thread and self._integrity_thread.isRunning():
            self._integrity_thread.wait(1000)
        super().closeEvent(event)
