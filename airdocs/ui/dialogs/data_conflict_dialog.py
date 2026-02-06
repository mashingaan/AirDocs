# AirDocs - Data Conflict Dialog
# ======================================

import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QMessageBox,
)

from utils.data_migrator import DataInfo

logger = logging.getLogger("airdocs.ui")


class DataConflictDialog(QDialog):
    """Dialog for resolving data location conflicts."""

    def __init__(
        self,
        app_data_info: DataInfo | None,
        user_data_info: DataInfo | None,
        parent=None
    ):
        super().__init__(parent)

        self._app_data_info = app_data_info
        self._user_data_info = user_data_info
        self._selected_source = None

        self._init_ui()

    def _init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("Обнаружен конфликт данных")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            "<h2>Обнаружен конфликт данных</h2>"
            "<p>Данные найдены в двух местах. Выберите, какие использовать:</p>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Radio button group
        self._button_group = QButtonGroup(self)

        # Option 1: User data (APPDATA)
        if self._user_data_info:
            user_group = QGroupBox()
            user_layout = QVBoxLayout(user_group)

            self._user_radio = QRadioButton("Использовать данные из %APPDATA%")
            self._user_radio.setChecked(True)
            self._button_group.addButton(self._user_radio, 1)
            user_layout.addWidget(self._user_radio)

            # Info
            info_layout = QVBoxLayout()
            info_layout.setContentsMargins(20, 0, 0, 0)

            size_mb = self._user_data_info.size_bytes / 1024 / 1024
            info_layout.addWidget(QLabel(f"Размер: {size_mb:.2f} MB"))
            info_layout.addWidget(
                QLabel(f"Записей: {self._user_data_info.record_count} отправок")
            )
            info_layout.addWidget(
                QLabel(f"Последнее изменение: {self._format_date(self._user_data_info.last_modified)}")
            )

            user_layout.addLayout(info_layout)
            layout.addWidget(user_group)

        # Option 2: App data (data folder)
        if self._app_data_info:
            app_group = QGroupBox()
            app_layout = QVBoxLayout(app_group)

            self._app_radio = QRadioButton("Использовать данные из папки приложения")
            if not self._user_data_info:
                self._app_radio.setChecked(True)
            self._button_group.addButton(self._app_radio, 2)
            app_layout.addWidget(self._app_radio)

            # Info
            info_layout = QVBoxLayout()
            info_layout.setContentsMargins(20, 0, 0, 0)

            size_mb = self._app_data_info.size_bytes / 1024 / 1024
            info_layout.addWidget(QLabel(f"Размер: {size_mb:.2f} MB"))
            info_layout.addWidget(
                QLabel(f"Записей: {self._app_data_info.record_count} отправок")
            )
            info_layout.addWidget(
                QLabel(f"Последнее изменение: {self._format_date(self._app_data_info.last_modified)}")
            )

            app_layout.addLayout(info_layout)
            layout.addWidget(app_group)

        # Note
        note = QLabel(
            "<i>Примечание: Другие данные будут сохранены в резервную копию</i>"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()

        continue_btn = QPushButton("Продолжить")
        continue_btn.clicked.connect(self._on_continue)
        button_layout.addWidget(continue_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _format_date(self, dt: datetime) -> str:
        """Format datetime for display."""
        if dt.year < 2000:
            return "Неизвестно"
        return dt.strftime("%d.%m.%Y %H:%M")

    def _on_continue(self):
        """Handle continue button click."""
        checked_id = self._button_group.checkedId()

        if checked_id == 1:
            self._selected_source = "appdata"
        elif checked_id == 2:
            self._selected_source = "data_folder"
        else:
            QMessageBox.warning(
                self,
                "Предупреждение",
                "Пожалуйста, выберите источник данных."
            )
            return

        # Confirm choice
        source_name = "%APPDATA%" if self._selected_source == "appdata" else "папки приложения"
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Вы уверены, что хотите использовать данные из {source_name}?\n\n"
            "Другие данные будут сохранены в резервную копию.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.accept()

    def get_selected_source(self) -> str | None:
        """
        Get the selected data source.

        Returns:
            "appdata" or "data_folder", or None if cancelled
        """
        return self._selected_source
