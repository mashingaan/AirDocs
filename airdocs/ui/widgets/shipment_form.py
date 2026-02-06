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
        main_layout = QFormLayout(main_group)

        self.awb_number = QLineEdit()
        self.awb_number.setPlaceholderText("12345678 или 123-12345678")
        main_layout.addRow("AWB номер:", self.awb_number)

        self.shipment_date = QDateEdit()
        self.shipment_date.setCalendarPopup(True)
        self.shipment_date.setDate(QDate.currentDate())
        self.shipment_date.setDisplayFormat("dd.MM.yyyy")
        main_layout.addRow("Дата:", self.shipment_date)

        self.shipment_type = QComboBox()
        self.shipment_type.addItem("Авиаперевозка", ShipmentType.AIR)
        self.shipment_type.addItem("Местная доставка", ShipmentType.LOCAL_DELIVERY)
        main_layout.addRow("Тип:", self.shipment_type)

        # Weight, pieces, volume
        measures_layout = QHBoxLayout()

        self.weight_kg = QDoubleSpinBox()
        self.weight_kg.setRange(0.001, 999999.999)
        self.weight_kg.setDecimals(3)
        self.weight_kg.setSuffix(" кг")
        measures_layout.addWidget(self.weight_kg)

        self.pieces = QSpinBox()
        self.pieces.setRange(1, 99999)
        self.pieces.setValue(1)
        self.pieces.setSuffix(" мест")
        measures_layout.addWidget(self.pieces)

        self.volume_m3 = QDoubleSpinBox()
        self.volume_m3.setRange(0, 9999.999)
        self.volume_m3.setDecimals(3)
        self.volume_m3.setSuffix(" м³")
        measures_layout.addWidget(self.volume_m3)

        main_layout.addRow("Вес / Мест / Объем:", measures_layout)

        self.goods_description = QLineEdit()
        self.goods_description.setPlaceholderText("Описание товара")
        main_layout.addRow("Описание товара:", self.goods_description)

        layout.addWidget(main_group)

        # === Shipper group ===
        shipper_group = QGroupBox("Отправитель")
        shipper_layout = QVBoxLayout(shipper_group)

        self.shipper_selector = PartySelector("shipper")
        shipper_layout.addWidget(self.shipper_selector)

        layout.addWidget(shipper_group)

        # === Consignee group ===
        consignee_group = QGroupBox("Получатель")
        consignee_layout = QVBoxLayout(consignee_group)

        self.consignee_selector = PartySelector("consignee")
        consignee_layout.addWidget(self.consignee_selector)

        layout.addWidget(consignee_group)

        # === Agent group ===
        agent_group = QGroupBox("Агент/Перевозчик")
        agent_layout = QVBoxLayout(agent_group)

        self.agent_selector = PartySelector("agent")
        self.agent_selector.set_required(False)
        agent_layout.addWidget(self.agent_selector)

        layout.addWidget(agent_group)

        # === Notes ===
        notes_group = QGroupBox("Примечания")
        notes_layout = QVBoxLayout(notes_group)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        notes_layout.addWidget(self.notes)

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

            for field_name in result.field_errors.keys():
                widget = field_widget_map.get(field_name)
                if widget:
                    self._apply_error_style(widget)

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

        if field_name in result.field_errors:
            self._apply_error_style(widget)
        else:
            self._clear_error_style(widget)

    def _set_error_state(self, widget: QWidget, has_error: bool):
        """Toggle error state without overriding global QSS."""
        widget.setProperty("hasError", bool(has_error))
        # Force Qt to re-apply stylesheet rules
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _apply_error_style(self, widget: QWidget):
        """Apply error state to a widget."""
        if isinstance(widget, PartySelector):
            self._set_error_state(widget.combo, True)
        else:
            self._set_error_state(widget, True)

    def _clear_error_style(self, widget: QWidget):
        """Clear error state from a widget."""
        if isinstance(widget, PartySelector):
            self._set_error_state(widget.combo, False)
        else:
            self._set_error_state(widget, False)

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
        ]
        for widget in widgets:
            self._set_error_state(widget, False)

        # Clear party selector styles
        self._set_error_state(self.shipper_selector.combo, False)
        self._set_error_state(self.consignee_selector.combo, False)
        self._set_error_state(self.agent_selector.combo, False)
