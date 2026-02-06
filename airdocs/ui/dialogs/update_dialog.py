# AirDocs - Update Dialog
# ===============================

import json
import logging
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QMessageBox,
)

from utils.updater import UpdateInfo

logger = logging.getLogger("airdocs.ui")


class UpdateCheckerThread(QThread):
    """Background thread for checking updates."""

    update_available = Signal(object)  # UpdateInfo
    no_update = Signal()
    check_failed = Signal(str)

    def run(self):
        from utils.updater import check_for_updates
        from core.app_context import get_context
        from core.version import VERSION

        context = get_context()
        config = context.config.get('updater', {})

        manifest_url = config.get('manifest_url')
        channel = config.get('channel', 'latest')

        if not manifest_url:
            self.check_failed.emit("Manifest URL not configured")
            return

        try:
            update_info = check_for_updates(manifest_url, VERSION, channel)
            if update_info:
                self.update_available.emit(update_info)
            else:
                self.no_update.emit()
        except Exception as e:
            self.check_failed.emit(str(e))


class UpdateDownloaderThread(QThread):
    """Background thread for downloading updates."""

    progress = Signal(int, int, int)  # percent, downloaded, total
    finished = Signal(Path)  # zip_path
    error = Signal(str)  # error_message

    def __init__(self, url: str, destination: Path):
        super().__init__()
        self.url = url
        self.destination = destination

    def run(self):
        from utils.updater import download_update

        def progress_callback(downloaded, total):
            percent = int((downloaded / total) * 100) if total > 0 else 0
            self.progress.emit(percent, downloaded, total)

        try:
            download_update(self.url, self.destination, progress_callback)
            self.finished.emit(self.destination)
        except Exception as e:
            self.error.emit(str(e))


class UpdateExtractorThread(QThread):
    """Background thread for extracting updates."""

    progress = Signal(int, int)  # current, total
    finished = Signal(Path)  # extracted_path
    error = Signal(str)  # error_message

    def __init__(self, zip_path: Path, extract_to: Path):
        super().__init__()
        self.zip_path = zip_path
        self.extract_to = extract_to

    def run(self):
        from utils.updater import extract_update_with_progress

        def progress_callback(current, total):
            self.progress.emit(current, total)

        try:
            extract_update_with_progress(
                self.zip_path,
                self.extract_to,
                progress_callback
            )
            self.finished.emit(self.extract_to)
        except Exception as e:
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    """Dialog for managing application updates."""

    def __init__(self, update_info: UpdateInfo, parent=None):
        super().__init__(parent)

        self._update_info = update_info
        self._downloader_thread: UpdateDownloaderThread | None = None
        self._extractor_thread: UpdateExtractorThread | None = None
        self._download_start_time = 0

        self._init_ui()

    def _init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("Доступно обновление")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("<h2>Доступно новое обновление</h2>")
        layout.addWidget(header)

        # Version info
        version_group = QGroupBox("Информация о версии")
        version_layout = QVBoxLayout(version_group)

        from core.version import VERSION
        version_label = QLabel(f"<b>Текущая версия:</b> {VERSION}")
        version_layout.addWidget(version_label)

        new_version_label = QLabel(
            f"<b>Новая версия:</b> {self._update_info.version}"
        )
        version_layout.addWidget(new_version_label)

        if self._update_info.release_date:
            date_label = QLabel(f"<b>Дата релиза:</b> {self._update_info.release_date}")
            version_layout.addWidget(date_label)

        if self._update_info.size > 0:
            size_mb = self._update_info.size / 1024 / 1024
            size_label = QLabel(f"<b>Размер:</b> {size_mb:.1f} MB")
            version_layout.addWidget(size_label)

        layout.addWidget(version_group)

        # Release notes
        if self._update_info.release_notes:
            notes_group = QGroupBox("Примечания к релизу")
            notes_layout = QVBoxLayout(notes_group)

            notes_text = QTextEdit()
            notes_text.setReadOnly(True)
            notes_text.setPlainText(self._update_info.release_notes)
            notes_text.setMaximumHeight(150)
            notes_layout.addWidget(notes_text)

            layout.addWidget(notes_group)

        # Progress section (hidden initially)
        self.progress_group = QGroupBox("Загрузка")
        progress_layout = QVBoxLayout(self.progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("Подготовка...")
        progress_layout.addWidget(self.progress_label)

        self.progress_group.hide()
        layout.addWidget(self.progress_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.install_now_btn = QPushButton("Установить сейчас")
        self.install_now_btn.clicked.connect(self._on_install_now)
        button_layout.addWidget(self.install_now_btn)

        self.install_later_btn = QPushButton("Установить позже")
        self.install_later_btn.clicked.connect(self._on_install_later)
        button_layout.addWidget(self.install_later_btn)

        button_layout.addStretch()

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _on_install_now(self):
        """Start downloading and installing the update."""
        from utils.updater import check_disk_space_for_download
        from core.app_context import get_context
        import time

        context = get_context()

        # Check disk space
        user_dir = context.user_dir if context.user_dir else context.app_dir / "data"
        download_path = user_dir / "updates"
        download_path.mkdir(parents=True, exist_ok=True)

        if self._update_info.size > 0:
            if not check_disk_space_for_download(self._update_info.size, download_path):
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    "Недостаточно места на диске для загрузки обновления."
                )
                return

        # Hide buttons, show progress
        self.install_now_btn.hide()
        self.install_later_btn.hide()
        self.cancel_btn.setText("Отмена загрузки")
        self.progress_group.show()

        # Start download
        zip_path = download_path / f"update_{self._update_info.version}.zip"

        self._download_start_time = time.time()
        self._downloader_thread = UpdateDownloaderThread(
            self._update_info.url,
            zip_path
        )
        self._downloader_thread.progress.connect(self._on_download_progress)
        self._downloader_thread.finished.connect(self._on_download_complete)
        self._downloader_thread.error.connect(self._on_download_error)
        self._downloader_thread.start()

    def _on_download_progress(self, percent: int, downloaded: int, total: int):
        """Update progress bar."""
        self.progress_bar.setValue(percent)

        downloaded_mb = downloaded / 1024 / 1024
        total_mb = total / 1024 / 1024 if total > 0 else 0

        self.progress_label.setText(
            f"Загрузка... {downloaded_mb:.1f} MB / {total_mb:.1f} MB"
        )

    def _on_download_complete(self, zip_path: Path):
        """Handle successful download."""
        from utils.updater import verify_update
        from core.app_context import get_context

        self.progress_label.setText("Проверка целостности...")

        # Verify SHA256 (skip if hash is not provided)
        if self._update_info.sha256:
            try:
                verify_update(zip_path, self._update_info.sha256)
            except Exception as e:
                self._on_download_error(str(e))
                return
        else:
            logger.warning("SHA256 not provided for update; skipping integrity check")

        context = get_context()
        user_dir = context.user_dir if context.user_dir else context.app_dir / "data"
        extract_path = user_dir / "updates" / f"extracted_v{self._update_info.version}"

        self.progress_label.setText("Извлечение файлов...")
        self.progress_bar.setValue(0)

        self._extractor_thread = UpdateExtractorThread(zip_path, extract_path)
        self._extractor_thread.progress.connect(self._on_extract_progress)
        self._extractor_thread.finished.connect(self._on_extract_complete)
        self._extractor_thread.error.connect(self._on_extract_error)
        self._extractor_thread.start()

    def _on_extract_progress(self, current: int, total: int):
        """Update extraction progress."""
        percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.progress_label.setText(
            f"Извлечение... {current}/{total} файлов"
        )

    def _on_extract_complete(self, extracted_path: Path):
        """Handle successful extraction."""
        import time
        from utils.updater import record_update_attempt
        from core.version import VERSION
        from PySide6.QtWidgets import QApplication

        self._save_pending_update(extracted_path)

        download_duration = int(time.time() - self._download_start_time)

        try:
            record_update_attempt(
                version=self._update_info.version,
                previous_version=VERSION,
                channel=self._update_info.channel,
                install_method="manual",
                download_size=self._update_info.size,
                download_duration=download_duration,
                success=True
            )
        except Exception as e:
            logger.warning(f"Failed to record update attempt: {e}")

        reply = QMessageBox.question(
            self,
            "Перезапустить приложение",
            "Обновление готово к установке.\n\n"
            "Перезапустить приложение?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            QApplication.quit()
        else:
            self.accept()

    def _on_extract_error(self, error: str):
        """Handle extraction error."""
        self._on_download_error(error)

    def _on_download_error(self, error: str):
        """Handle download error."""
        import time
        from utils.updater import record_update_attempt
        from core.version import VERSION

        download_duration = int(time.time() - self._download_start_time)

        # Record failed attempt
        try:
            record_update_attempt(
                version=self._update_info.version,
                previous_version=VERSION,
                channel=self._update_info.channel,
                install_method="manual",
                download_size=self._update_info.size,
                download_duration=download_duration,
                success=False,
                error_message=error
            )
        except Exception as e:
            logger.warning(f"Failed to record update attempt: {e}")

        QMessageBox.critical(
            self,
            "Ошибка загрузки",
            f"Не удалось загрузить обновление:\n\n{error}"
        )

        # Restore buttons
        self.progress_group.hide()
        self.install_now_btn.show()
        self.install_later_btn.show()
        self.cancel_btn.setText("Отмена")

    def _on_install_later(self):
        """Close and defer update."""
        QMessageBox.information(
            self,
            "Отложено",
            "Обновление будет предложено при следующем запуске приложения."
        )
        self.accept()

    def _save_pending_update(self, extracted_path: Path):
        """Save pending update marker to disk."""
        from core.app_context import get_context

        context = get_context()
        if not context.user_dir:
            return

        marker_path = context.user_dir / '.pending_update'

        from datetime import datetime

        update_data = {
            'version': self._update_info.version,
            'extracted_path': str(extracted_path),
            'url': self._update_info.url,
            'sha256': self._update_info.sha256,
            'size': self._update_info.size,
            'release_date': self._update_info.release_date,
            'release_notes': self._update_info.release_notes,
            'channel': self._update_info.channel,
            'download_timestamp': datetime.utcnow().isoformat() + "Z",
        }

        try:
            with open(marker_path, 'w', encoding='utf-8') as f:
                json.dump(update_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save pending update marker: {e}")
