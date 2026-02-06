# AirDocs - Shipment Dialog
# ==================================

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QMessageBox,
    QFrame,
)

from core.constants import ShipmentType
from data.models import Shipment
from data.repositories import ShipmentRepository
from ui.widgets.shipment_form import ShipmentForm

logger = logging.getLogger("airdocs.ui")


class ShipmentDialog(QDialog):
    """Dialog for creating or editing a shipment."""

    def __init__(
        self,
        shipment: Shipment | None = None,
        shipment_type: ShipmentType = ShipmentType.LOCAL_DELIVERY,
        parent=None
    ):
        super().__init__(parent)

        self._shipment = shipment
        self._shipment_type = shipment_type
        self._shipment_repo = ShipmentRepository()
        self._is_edit_mode = shipment is not None

        self._init_ui()

        # Load existing data if editing
        if self._shipment:
            self._form.load_shipment(self._shipment)
        else:
            self._form.set_defaults()
            # Set shipment type
            index = self._form.shipment_type.findData(shipment_type)
            if index >= 0:
                self._form.shipment_type.setCurrentIndex(index)

    def _init_ui(self):
        """Initialize UI components."""
        title = "Редактировать отправку" if self._is_edit_mode else "Добавить отправку"
        self.setWindowTitle(title)
        self.setMinimumSize(600, 700)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header
        header_text = "Редактирование отправки" if self._is_edit_mode else "Новая отправка"
        header = QLabel(f"<h2>{header_text}</h2>")
        layout.addWidget(header)

        # Form in scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        self._form = ShipmentForm()
        scroll_area.setWidget(self._form)

        layout.addWidget(scroll_area)

        # Error display area (hidden by default)
        self._error_frame = QFrame()
        self._error_frame.setStyleSheet(
            "background-color: #F8D7DA; "
            "border: 1px solid #F5C6CB; "
            "border-radius: 4px; "
            "padding: 10px;"
        )
        error_layout = QVBoxLayout(self._error_frame)

        error_header = QLabel("<b>Ошибки валидации:</b>")
        error_layout.addWidget(error_header)

        self._error_label = QLabel()
        self._error_label.setWordWrap(True)
        error_layout.addWidget(self._error_label)

        self._error_frame.hide()
        layout.addWidget(self._error_frame)

        # Buttons
        button_layout = QHBoxLayout()

        save_btn = QPushButton("Сохранить")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()

        if self._is_edit_mode:
            delete_btn = QPushButton("Удалить")
            delete_btn.setStyleSheet("color: red;")
            delete_btn.clicked.connect(self._on_delete)
            button_layout.addWidget(delete_btn)

        layout.addLayout(button_layout)

    def _on_save(self):
        """Save shipment."""
        # Validate form
        result = self._form.validate()

        if not result.is_valid:
            self._show_errors(result.errors)
            return

        # Hide errors if previously shown
        self._error_frame.hide()

        # Get form data
        data = self._form.get_data()

        try:
            if self._is_edit_mode:
                # Update existing shipment
                for key, value in data.items():
                    if hasattr(self._shipment, key):
                        setattr(self._shipment, key, value)

                self._shipment_repo.update(self._shipment)
                logger.info(f"Shipment updated: {self._shipment.id}")
            else:
                # Create new shipment
                shipment = Shipment(**data)
                shipment_id = self._shipment_repo.create(shipment)
                self._shipment = self._shipment_repo.get_by_id(shipment_id)
                logger.info(f"Shipment created: {shipment_id}")

            self.accept()

        except Exception as e:
            logger.error(f"Failed to save shipment: {e}")
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось сохранить отправку:\n\n{e}"
            )

    def _on_delete(self):
        """Delete shipment."""
        if not self._shipment:
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить отправку {self._shipment.awb_number}?\n\n"
            "Это действие нельзя отменить.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self._shipment_repo.delete(self._shipment.id)
                logger.info(f"Shipment deleted: {self._shipment.id}")
                self.accept()
            except Exception as e:
                logger.error(f"Failed to delete shipment: {e}")
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось удалить отправку:\n\n{e}"
                )

    def _on_cancel(self):
        """Cancel editing."""
        # Check for unsaved changes
        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "Несохраненные изменения",
                "Есть несохраненные изменения. Вы уверены, что хотите закрыть?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

        self.reject()

    def _show_errors(self, errors: list[str]):
        """Show validation errors."""
        error_text = "<ul>"
        for error in errors:
            error_text += f"<li>{error}</li>"
        error_text += "</ul>"

        self._error_label.setText(error_text)
        self._error_frame.show()

    def _has_unsaved_changes(self) -> bool:
        """Check if form has unsaved changes."""
        if not self._is_edit_mode:
            # For new shipment, check if any field has data
            data = self._form.get_data()
            return bool(data.get('awb_number'))

        # For edit mode, compare with original
        # Simplified check - just return False for now
        return False

    def get_shipment(self) -> Shipment | None:
        """Get the saved shipment."""
        return self._shipment
