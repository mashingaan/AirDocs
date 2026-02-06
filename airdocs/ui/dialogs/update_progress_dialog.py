# AirDocs - Update Progress Dialog
# ===============================

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar


class UpdateProgressDialog(QDialog):
    """
    Non-modal dialog showing update installation progress.
    Shown during apply_pending_update() in main.py.
    """

    def __init__(self, version: str, parent=None):
        super().__init__(parent)

        self._allow_close = False

        self.setWindowTitle("Установка обновления")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        self.title_label = QLabel(f"Установка обновления v{version}...")
        layout.addWidget(self.title_label)

        self.step_label = QLabel("")
        layout.addWidget(self.step_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 3)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

    def set_step(self, text: str, value: int | None = None) -> None:
        """Update the step text and progress value."""
        self.step_label.setText(text)
        if value is not None:
            self.progress_bar.setValue(value)

    def allow_close(self) -> None:
        """Allow programmatic close after completion."""
        self._allow_close = True

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
        else:
            event.ignore()
