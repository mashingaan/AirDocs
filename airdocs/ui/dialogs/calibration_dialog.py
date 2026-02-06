# AirDocs - AWB Overlay Calibration Dialog
# ================================================

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QComboBox,
    QScrollArea,
    QWidget,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt

from core.app_context import get_context
from data.repositories import CalibrationRepository
from data.models import AWBOverlayCalibration

logger = logging.getLogger("airdocs.ui")


class FieldCoordinateEditor(QGroupBox):
    """Editor for a single field's coordinates."""

    def __init__(self, field_name: str, label: str, parent=None):
        super().__init__(label, parent)
        self.field_name = field_name
        self._init_ui()

    def _init_ui(self):
        layout = QFormLayout(self)

        # X coordinate
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(0, 1000)
        self.x_spin.setDecimals(1)
        self.x_spin.setSuffix(" мм")
        layout.addRow("X:", self.x_spin)

        # Y coordinate
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(0, 1000)
        self.y_spin.setDecimals(1)
        self.y_spin.setSuffix(" мм")
        layout.addRow("Y:", self.y_spin)

        # Font size
        self.font_spin = QSpinBox()
        self.font_spin.setRange(6, 24)
        self.font_spin.setValue(10)
        self.font_spin.setSuffix(" pt")
        layout.addRow("Шрифт:", self.font_spin)

    def get_values(self) -> dict:
        """Get current coordinate values."""
        return {
            "x": self.x_spin.value(),
            "y": self.y_spin.value(),
            "font_size": self.font_spin.value(),
        }

    def set_values(self, x: float, y: float, font_size: int = 10):
        """Set coordinate values."""
        self.x_spin.setValue(x)
        self.y_spin.setValue(y)
        self.font_spin.setValue(font_size)


class CalibrationDialog(QDialog):
    """
    Dialog for calibrating AWB PDF overlay coordinates.

    Allows adjusting X/Y positions and font sizes for each
    field that gets overlaid on the AWB blank PDF.
    """

    # Standard AWB fields with default coordinates (in mm from bottom-left)
    AWB_FIELDS = [
        ("awb_number", "Номер AWB", 85, 770),
        ("shipper_name", "Отправитель (имя)", 30, 700),
        ("shipper_address", "Отправитель (адрес)", 30, 680),
        ("consignee_name", "Получатель (имя)", 30, 600),
        ("consignee_address", "Получатель (адрес)", 30, 580),
        ("departure_airport", "Аэропорт отправления", 30, 500),
        ("destination_airport", "Аэропорт назначения", 200, 500),
        ("flight_number", "Номер рейса", 350, 500),
        ("flight_date", "Дата рейса", 450, 500),
        ("pieces", "Количество мест", 30, 420),
        ("weight_kg", "Вес (кг)", 150, 420),
        ("volume_cbm", "Объем (м³)", 270, 420),
        ("goods_description", "Описание груза", 30, 350),
        ("declared_value", "Объявленная стоимость", 400, 350),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self._context = get_context()
        self._calibration_repo = CalibrationRepository()
        self._field_editors: dict[str, FieldCoordinateEditor] = {}

        self._init_ui()
        self._load_calibration()

    def _init_ui(self):
        """Initialize dialog UI."""
        self.setWindowTitle("Калибровка координат AWB")
        self.setMinimumSize(600, 700)

        layout = QVBoxLayout(self)

        # Header with instructions
        header = QLabel(
            "Настройка координат полей для наложения на бланк AWB.\n"
            "Координаты указываются в миллиметрах от левого нижнего угла страницы."
        )
        header.setWordWrap(True)
        header.setStyleSheet("color: #606060; margin-bottom: 10px;")
        layout.addWidget(header)

        # Template selector
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Шаблон:"))

        self.template_combo = QComboBox()
        self.template_combo.addItem("По умолчанию", "default")
        self._load_templates()
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        template_layout.addWidget(self.template_combo, 1)

        layout.addLayout(template_layout)

        # Scroll area for field editors
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Create field editors
        for field_name, label, default_x, default_y in self.AWB_FIELDS:
            editor = FieldCoordinateEditor(field_name, label)
            editor.set_values(default_x, default_y, 10)
            self._field_editors[field_name] = editor
            scroll_layout.addWidget(editor)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Buttons
        button_layout = QHBoxLayout()

        btn_reset = QPushButton("Сбросить")
        btn_reset.clicked.connect(self._on_reset)
        button_layout.addWidget(btn_reset)

        btn_test = QPushButton("Тест...")
        btn_test.clicked.connect(self._on_test)
        button_layout.addWidget(btn_test)

        btn_import = QPushButton("Импорт...")
        btn_import.clicked.connect(self._on_import)
        button_layout.addWidget(btn_import)

        btn_export = QPushButton("Экспорт...")
        btn_export.clicked.connect(self._on_export)
        button_layout.addWidget(btn_export)

        button_layout.addStretch()

        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self._on_save)
        button_layout.addWidget(btn_save)

        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_cancel)

        layout.addLayout(button_layout)

    def _load_templates(self):
        """Load available AWB templates into combo."""
        templates_dir = self._context.base_path / "templates" / "pdf"
        if templates_dir.exists():
            for pdf_file in templates_dir.glob("*.pdf"):
                self.template_combo.addItem(pdf_file.stem, pdf_file.stem)

    def _on_template_changed(self):
        """Handle template selection change."""
        self._load_calibration()

    def _load_calibration(self):
        """Load calibration data for current template."""
        template_name = self.template_combo.currentData() or "default"

        # Try to load from database (one record per field)
        calibrations = self._calibration_repo.get_all_for_template(template_name)

        if calibrations:
            # Load saved coordinates from per-field records
            for cal in calibrations:
                if cal.field_name in self._field_editors:
                    editor = self._field_editors[cal.field_name]
                    editor.set_values(cal.x_coord, cal.y_coord, int(cal.font_size))
        else:
            # Load from config or use defaults
            self._load_from_config()

    def _load_from_config(self):
        """Load coordinates from settings.yaml."""
        config = self._context.config
        awb_config = config.get("awb_overlay", {})
        coordinates = awb_config.get("coordinates", {})

        for field_name, editor in self._field_editors.items():
            if field_name in coordinates:
                coords = coordinates[field_name]
                editor.set_values(
                    coords.get("x", 0),
                    coords.get("y", 0),
                    coords.get("font_size", 10),
                )

    def _on_reset(self):
        """Reset to default coordinates."""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Сбросить все координаты к значениям по умолчанию?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            for field_name, label, default_x, default_y in self.AWB_FIELDS:
                if field_name in self._field_editors:
                    self._field_editors[field_name].set_values(default_x, default_y, 10)

    def _on_test(self):
        """Generate a test PDF with current coordinates."""
        try:
            from generators.awb_pdf_generator import AWBPDFGenerator

            # Create test data
            test_data = {
                "awb_number": "123-12345678",
                "shipper_name": "ООО ТЕСТ ОТПРАВИТЕЛЬ",
                "shipper_address": "г. Москва, ул. Тестовая, д. 1",
                "consignee_name": "ООО ТЕСТ ПОЛУЧАТЕЛЬ",
                "consignee_address": "г. Санкт-Петербург, ул. Примерная, д. 2",
                "departure_airport": "SVO",
                "destination_airport": "LED",
                "flight_number": "SU123",
                "flight_date": "01.01.2025",
                "pieces": "10",
                "weight_kg": "150.5",
                "volume_cbm": "2.5",
                "goods_description": "Тестовый груз для калибровки",
                "declared_value": "NVD",
            }

            # Get current coordinates
            coordinates = self._get_all_coordinates()

            # Generate test PDF
            output_path = self._context.base_path / "data" / "test_calibration.pdf"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            generator = AWBPDFGenerator()
            generator.generate_with_coordinates(test_data, output_path, coordinates)

            QMessageBox.information(
                self,
                "Тест",
                f"Тестовый PDF создан:\n{output_path}\n\nОткройте файл для проверки координат.",
            )

            # Try to open the file
            import os
            os.startfile(str(output_path))

        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать тестовый PDF:\n{e}")

    def _on_import(self):
        """Import coordinates from JSON file."""
        import json

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт координат",
            str(self._context.base_path),
            "JSON файлы (*.json)",
        )

        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for field_name, coords in data.items():
                    if field_name in self._field_editors:
                        editor = self._field_editors[field_name]
                        editor.set_values(
                            coords.get("x", 0),
                            coords.get("y", 0),
                            coords.get("font_size", 10),
                        )

                QMessageBox.information(self, "Импорт", "Координаты успешно импортированы")

            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать:\n{e}")

    def _on_export(self):
        """Export coordinates to JSON file."""
        import json

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт координат",
            str(self._context.base_path / "awb_coordinates.json"),
            "JSON файлы (*.json)",
        )

        if file_path:
            try:
                coordinates = self._get_all_coordinates()

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(coordinates, f, ensure_ascii=False, indent=2)

                QMessageBox.information(self, "Экспорт", f"Координаты сохранены в:\n{file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать:\n{e}")

    def _on_save(self):
        """Save calibration to database."""
        template_name = self.template_combo.currentData() or "default"
        coordinates = self._get_all_coordinates()

        try:
            # Save each field as a separate record
            for field_name, values in coordinates.items():
                calibration = AWBOverlayCalibration(
                    template_name=template_name,
                    field_name=field_name,
                    x_coord=values["x"],
                    y_coord=values["y"],
                    font_size=values["font_size"],
                )
                self._calibration_repo.save(calibration)

            QMessageBox.information(self, "Сохранение", "Калибровка сохранена")
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить:\n{e}")

    def _get_all_coordinates(self) -> dict:
        """Get all field coordinates."""
        result = {}
        for field_name, editor in self._field_editors.items():
            result[field_name] = editor.get_values()
        return result
