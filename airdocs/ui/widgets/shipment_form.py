# AirDocs - Shipment Form Widget
# ======================================

import logging
from datetime import date
from typing import Any

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QTextEdit,
    QDateEdit,
    QComboBox,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Qt, QDate

from business.validators import ValidationResult, validate_shipment
from core.constants import ShipmentType
from data.models import Shipment
from data.repositories import PartyRepository, TemplateRepository
from ui.widgets.party_selector import PartySelector

logger = logging.getLogger("airdocs.ui")


class ShipmentForm(QWidget):
    """
    Form widget for entering/editing shipment data.

    Contains all fields from the canonical field mapping:
    - AWB number, date, type
    - Weight, pieces, volume
    - Shipper, consignee, agent selection
    - Goods description
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._party_repo = PartyRepository()
        self._template_repo = TemplateRepository()
        self._error_labels = {}  # field_name -> QLabel
        self._init_ui()

    def _init_ui(self):
        """Initialize form UI."""
        layout = QVBoxLayout(self)

        # === Preset selection ===
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QComboBox())  # Placeholder for preset selector
        preset_layout.addWidget(QPushButton("Сохранить как пресет"))
        preset_layout.addStretch()
        # layout.addLayout(preset_layout)  # Disabled for MVP

        # === Main data group ===
        main_group = QGroupBox("Основные данные")
        main_group.setMinimumWidth(450)
        main_layout = QFormLayout(main_group)
        main_layout.setLabelAlignment(Qt.AlignRight)
        main_layout.setFormAlignment(Qt.AlignLeft)

        self.awb_number = QLineEdit()
        self.awb_number.setPlaceholderText("12345678 или 123-12345678")
        main_layout.addRow("AWB номер:", self.awb_number)
        error_label = QLabel()
        error_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 2px;")
        error_label.hide()
        main_layout.addRow("", error_label)
        self._error_labels["awb_number"] = error_label

        self.shipment_date = QDateEdit()
        self.shipment_date.setCalendarPopup(True)
        self.shipment_date.setDate(QDate.currentDate())
        self.shipment_date.setDisplayFormat("dd.MM.yyyy")
        main_layout.addRow("Дата:", self.shipment_date)
        error_label = QLabel()
        error_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 2px;")
        error_label.hide()
        main_layout.addRow("", error_label)
        self._error_labels["shipment_date"] = error_label

        self.shipment_type = QComboBox()
        self.shipment_type.addItem("Авиаперевозка", ShipmentType.AIR)
        self.shipment_type.addItem("Местная доставка", ShipmentType.LOCAL_DELIVERY)
        main_layout.addRow("Тип:", self.shipment_type)
        error_label = QLabel()
        error_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 2px;")
        error_label.hide()
        main_layout.addRow("", error_label)
        self._error_labels["shipment_type"] = error_label

        # Weight, pieces, volume
        measures_layout = QHBoxLayout()

        self.weight_kg = QDoubleSpinBox()
        self.weight_kg.setRange(0.001, 999999.999)
        self.weight_kg.setDecimals(3)
        self.weight_kg.setSuffix(" кг")
        self.weight_kg.setMinimumWidth(80)
        measures_layout.addWidget(self.weight_kg)

        self.pieces = QSpinBox()
        self.pieces.setRange(1, 99999)
        self.pieces.setValue(1)
        self.pieces.setSuffix(" мест")
        self.pieces.setMinimumWidth(70)
        measures_layout.addWidget(self.pieces)

        self.volume_m3 = QDoubleSpinBox()
        self.volume_m3.setRange(0, 9999.999)
        self.volume_m3.setDecimals(3)
        self.volume_m3.setSuffix(" м³")
        self.volume_m3.setMinimumWidth(80)
        measures_layout.addWidget(self.volume_m3)

        main_layout.addRow("Вес / Мест / Объем:", measures_layout)
        error_label = QLabel()
        error_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 2px;")
        error_label.hide()
        main_layout.addRow("", error_label)
        self._error_labels["measures"] = error_label

        self.goods_description = QLineEdit()
        self.goods_description.setPlaceholderText("Описание товара")
        main_layout.addRow("Описание товара:", self.goods_description)
        error_label = QLabel()
        error_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 2px;")
        error_label.hide()
        main_layout.addRow("", error_label)
        self._error_labels["goods_description"] = error_label

        layout.addWidget(main_group)

        # === Shipper group ===
        shipper_group = QGroupBox("Отправитель")
        shipper_group.setMinimumWidth(450)
        shipper_layout = QVBoxLayout(shipper_group)

        self.shipper_selector = PartySelector("shipper")
        shipper_layout.addWidget(self.shipper_selector)
        error_label = QLabel()
        error_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 2px;")
        error_label.hide()
        shipper_layout.addWidget(error_label)
        self._error_labels["shipper_id"] = error_label

        layout.addWidget(shipper_group)

        # === Consignee group ===
        consignee_group = QGroupBox("Получатель")
        consignee_group.setMinimumWidth(450)
        consignee_layout = QVBoxLayout(consignee_group)

        self.consignee_selector = PartySelector("consignee")
        consignee_layout.addWidget(self.consignee_selector)
        error_label = QLabel()
        error_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 2px;")
        error_label.hide()
        consignee_layout.addWidget(error_label)
        self._error_labels["consignee_id"] = error_label

        layout.addWidget(consignee_group)

        # === Agent group ===
        agent_group = QGroupBox("Агент/Перевозчик")
        agent_group.setMinimumWidth(450)
        agent_layout = QVBoxLayout(agent_group)

        self.agent_selector = PartySelector("agent")
        self.agent_selector.set_required(False)
        agent_layout.addWidget(self.agent_selector)
        error_label = QLabel()
        error_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 2px;")
        error_label.hide()
        agent_layout.addWidget(error_label)
        self._error_labels["agent_id"] = error_label

        layout.addWidget(agent_group)

        # === Notes ===
        notes_group = QGroupBox("Примечания")
        notes_group.setMinimumWidth(450)
        notes_layout = QVBoxLayout(notes_group)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        notes_layout.addWidget(self.notes)
        error_label = QLabel()
        error_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 2px;")
        error_label.hide()
        notes_layout.addWidget(error_label)
        self._error_labels["notes"] = error_label

        layout.addWidget(notes_group)

        # Setup validation signals
        self._init_validation_signals()

        # Add stretch to push everything up
        layout.addStretch()

    def get_data(self) -> dict[str, Any]:
        """
        Get form data as dictionary.

        Returns:
            Dictionary with canonical field names
        """
        # Get shipment type
        type_index = self.shipment_type.currentIndex()
        shipment_type = self.shipment_type.itemData(type_index)

        # Get date
        qdate = self.shipment_date.date()
        shipment_date = date(qdate.year(), qdate.month(), qdate.day())

        data = {
            "awb_number": self.awb_number.text().strip(),
            "shipment_date": shipment_date,
            "shipment_type": shipment_type,
            "weight_kg": self.weight_kg.value(),
            "pieces": self.pieces.value(),
            "volume_m3": self.volume_m3.value() if self.volume_m3.value() > 0 else None,
            "goods_description": self.goods_description.text().strip() or None,
            "shipper_id": self.shipper_selector.get_selected_id(),
            "consignee_id": self.consignee_selector.get_selected_id(),
            "agent_id": self.agent_selector.get_selected_id(),
            "notes": self.notes.toPlainText().strip() or None,
        }

        return data

    def load_shipment(self, shipment: Shipment):
        """
        Load shipment data into form.

        Args:
            shipment: Shipment to load
        """
        self.awb_number.setText(shipment.awb_number)

        if shipment.shipment_date:
            qdate = QDate(
                shipment.shipment_date.year,
                shipment.shipment_date.month,
                shipment.shipment_date.day
            )
            self.shipment_date.setDate(qdate)

        # Set shipment type
        index = self.shipment_type.findData(shipment.shipment_type)
        if index >= 0:
            self.shipment_type.setCurrentIndex(index)

        self.weight_kg.setValue(shipment.weight_kg)
        self.pieces.setValue(shipment.pieces)
        self.volume_m3.setValue(shipment.volume_m3 or 0)
        self.goods_description.setText(shipment.goods_description or "")

        # Set parties
        self.shipper_selector.set_selected_id(shipment.shipper_id)
        self.consignee_selector.set_selected_id(shipment.consignee_id)
        self.agent_selector.set_selected_id(shipment.agent_id)

        self.notes.setPlainText(shipment.notes or "")

    def clear(self):
        """Clear all form fields."""
        self.awb_number.clear()
        self.shipment_date.setDate(QDate.currentDate())
        self.shipment_type.setCurrentIndex(0)
        self.weight_kg.setValue(self.weight_kg.minimum())  # Use minimum value
        self.pieces.setValue(1)
        self.volume_m3.setValue(0)
        self.goods_description.clear()
        self.shipper_selector.clear()
        self.consignee_selector.clear()
        self.agent_selector.clear()
        self.notes.clear()

    def set_defaults(self):
        """Set default values for a new shipment."""
        self.shipment_date.setDate(QDate.currentDate())
        self.shipment_type.setCurrentIndex(0)
        self.pieces.setValue(1)
        self.weight_kg.setValue(0.001)  # Minimum weight to show it's a new form
        self.volume_m3.setValue(0)
        self.awb_number.setPlaceholderText("Введите номер AWB...")

    def validate(self) -> ValidationResult:
        """Validate form data using business validators."""
        data = self.get_data()

        # Create temporary Shipment object for validation
        temp_shipment = Shipment(
            awb_number=data["awb_number"],
            shipment_date=data["shipment_date"],
            shipment_type=data["shipment_type"],
            weight_kg=data["weight_kg"],
            pieces=data["pieces"],
            volume_m3=data["volume_m3"],
            goods_description=data["goods_description"],
            shipper_id=data["shipper_id"],
            consignee_id=data["consignee_id"],
            agent_id=data["agent_id"],
            notes=data["notes"],
        )

        # Use business validator
        result = validate_shipment(temp_shipment)

        # Apply visual feedback
        self.apply_validation_result(result)

        return result

    def apply_validation_result(self, result: ValidationResult):
        """Apply visual feedback based on validation result."""
        # Clear all error styles first
        self.clear_error_styles()

        if not result.is_valid:
            # Apply error styles to fields with errors
            # NOTE: Keep this map in sync with validate_shipment() field_errors
            field_widget_map = {
                "awb_number": self.awb_number,
                "shipment_date": self.shipment_date,
                "shipment_type": self.shipment_type,
                "weight_kg": self.weight_kg,
                "pieces": self.pieces,
                "volume_m3": self.volume_m3,
                "goods_description": self.goods_description,
                "shipper_id": self.shipper_selector,
                "consignee_id": self.consignee_selector,
                "agent_id": self.agent_selector,
                "notes": self.notes,
            }

            measures_error_shown = False
            for field_name in result.field_errors.keys():
                widget = field_widget_map.get(field_name)
                if widget:
                    error_msg = result.field_errors[field_name]
                    if field_name in {"weight_kg", "pieces", "volume_m3"}:
                        if measures_error_shown:
                            continue
                        measures_error_shown = True
                    self._apply_error_style(widget, error_msg)

    def _init_validation_signals(self):
        """Connect field signals for real-time validation (NO modal dialogs)."""
        # Connect text fields
        self.awb_number.textChanged.connect(lambda: self._validate_field("awb_number"))
        self.goods_description.textChanged.connect(
            lambda: self._validate_field("goods_description")
        )

        # Notes (if QTextEdit/QPlainTextEdit)
        self.notes.textChanged.connect(lambda: self._validate_field("notes"))

        # Connect numeric fields
        self.weight_kg.valueChanged.connect(lambda: self._validate_field("weight_kg"))
        self.pieces.valueChanged.connect(lambda: self._validate_field("pieces"))
        self.volume_m3.valueChanged.connect(lambda: self._validate_field("volume_m3"))

        # Date/type fields
        self.shipment_date.dateChanged.connect(
            lambda: self._validate_field("shipment_date")
        )
        self.shipment_type.currentIndexChanged.connect(
            lambda: self._validate_field("shipment_type")
        )

        # Connect party selectors (validate() only — do NOT call ensure_parties()/show_empty_warning here)
        self.shipper_selector.party_changed.connect(
            lambda: self._validate_field("shipper_id")
        )
        self.consignee_selector.party_changed.connect(
            lambda: self._validate_field("consignee_id")
        )
        self.agent_selector.party_changed.connect(
            lambda: self._validate_field("agent_id")
        )

    def _validate_field(self, field_name: str):
        """Validate a single field and update its error state (NO modal dialogs)."""
        # Build temporary Shipment from current form data and run business validator.
        data = self.get_data()
        temp_shipment = Shipment(
            awb_number=data["awb_number"],
            shipment_date=data["shipment_date"],
            shipment_type=data["shipment_type"],
            weight_kg=data["weight_kg"],
            pieces=data["pieces"],
            volume_m3=data["volume_m3"],
            goods_description=data["goods_description"],
            shipper_id=data["shipper_id"],
            consignee_id=data["consignee_id"],
            agent_id=data["agent_id"],
            notes=data["notes"],
        )

        result = validate_shipment(temp_shipment)

        field_widget_map = {
            "awb_number": self.awb_number,
            "shipment_date": self.shipment_date,
            "shipment_type": self.shipment_type,
            "weight_kg": self.weight_kg,
            "pieces": self.pieces,
            "volume_m3": self.volume_m3,
            "goods_description": self.goods_description,
            "shipper_id": self.shipper_selector,
            "consignee_id": self.consignee_selector,
            "agent_id": self.agent_selector,
            "notes": self.notes,
        }

        widget = field_widget_map.get(field_name)
        if not widget:
            return

        measures_fields = ("weight_kg", "pieces", "volume_m3")
        if field_name in measures_fields:
            first_measures_error_field = next(
                (name for name in measures_fields if name in result.field_errors),
                None,
            )
            if first_measures_error_field:
                error_msg = result.field_errors[first_measures_error_field]
                self._apply_error_style(widget, error_msg)
            else:
                self._clear_error_style(widget)
            return

        if field_name in result.field_errors:
            error_msg = result.field_errors[field_name]
            self._apply_error_style(widget, error_msg)
        else:
            self._clear_error_style(widget)

    def _set_error_state(self, widget: QWidget, has_error: bool):
        """Toggle error state without overriding global QSS."""
        widget.setProperty("hasError", bool(has_error))
        # Force Qt to re-apply stylesheet rules
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _apply_error_style(self, widget: QWidget, error_message: str = None):
        """Apply error state to a widget."""
        if isinstance(widget, PartySelector):
            self._set_error_state(widget.combo, True)
            widget.combo.setToolTip(error_message or "Ошибка валидации")

            field_name = None
            if widget == self.shipper_selector:
                field_name = "shipper_id"
            elif widget == self.consignee_selector:
                field_name = "consignee_id"
            elif widget == self.agent_selector:
                field_name = "agent_id"

            if field_name:
                self._show_error_label(field_name, error_message)
        else:
            self._set_error_state(widget, True)
            widget.setToolTip(error_message or "Ошибка валидации")

            field_name = None
            if widget == self.awb_number:
                field_name = "awb_number"
            elif widget == self.shipment_date:
                field_name = "shipment_date"
            elif widget == self.shipment_type:
                field_name = "shipment_type"
            elif widget == self.weight_kg:
                field_name = "measures"
            elif widget == self.pieces:
                field_name = "measures"
            elif widget == self.volume_m3:
                field_name = "measures"
            elif widget == self.goods_description:
                field_name = "goods_description"
            elif widget == self.notes:
                field_name = "notes"

            if field_name:
                self._show_error_label(field_name, error_message)

    def _clear_error_style(self, widget: QWidget):
        """Clear error state from a widget."""
        if isinstance(widget, PartySelector):
            self._set_error_state(widget.combo, False)
            widget.combo.setToolTip("")

            field_name = None
            if widget == self.shipper_selector:
                field_name = "shipper_id"
            elif widget == self.consignee_selector:
                field_name = "consignee_id"
            elif widget == self.agent_selector:
                field_name = "agent_id"

            if field_name:
                self._hide_error_label(field_name)
        else:
            self._set_error_state(widget, False)
            widget.setToolTip("")

            field_name = None
            if widget == self.awb_number:
                field_name = "awb_number"
            elif widget == self.shipment_date:
                field_name = "shipment_date"
            elif widget == self.shipment_type:
                field_name = "shipment_type"
            elif widget == self.weight_kg:
                field_name = "measures"
            elif widget == self.pieces:
                field_name = "measures"
            elif widget == self.volume_m3:
                field_name = "measures"
            elif widget == self.goods_description:
                field_name = "goods_description"
            elif widget == self.notes:
                field_name = "notes"

            if field_name:
                self._hide_error_label(field_name)

    def _show_error_label(self, field_name: str, message: str):
        """Show error label for a field."""
        label = self._error_labels.get(field_name)
        if label:
            label.setText(message or "Ошибка валидации")
            label.show()

    def _hide_error_label(self, field_name: str):
        """Hide error label for a field."""
        label = self._error_labels.get(field_name)
        if label:
            label.hide()

    def clear_error_styles(self):
        """Clear error states from all fields."""
        widgets = [
            self.awb_number,
            self.shipment_date,
            self.shipment_type,
            self.weight_kg,
            self.pieces,
            self.volume_m3,
            self.goods_description,
            self.notes,
            self.shipper_selector,
            self.consignee_selector,
            self.agent_selector,
        ]
        for widget in widgets:
            self._clear_error_style(widget)

        # Hide all error labels
        for label in self._error_labels.values():
            label.hide()
