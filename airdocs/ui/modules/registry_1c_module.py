# AirDocs - Registry 1C Module
# ====================================

import logging
import os
import platform
import subprocess
from datetime import date, timedelta

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QPushButton,
    QLabel,
    QGroupBox,
    QDateEdit,
    QComboBox,
    QMessageBox,
    QProgressDialog,
    QFileDialog,
)
from PySide6.QtCore import Qt, QDate

from core.constants import ShipmentType, ShipmentStatus, DocumentType
from data.repositories import ShipmentRepository
from business.document_service import DocumentService

logger = logging.getLogger("airdocs.ui")


class Registry1CModule(QWidget):
    """
    Registry for 1C (Реестр для 1С) module.

    Generates consolidated Excel registries for accounting import:
    - Period selection (date range)
    - Multi-AWB aggregation
    - Export to Excel format compatible with 1C
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._shipment_repo = ShipmentRepository()
        self._document_service = DocumentService()

        self._init_ui()
        self.refresh()

    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("<b>Реестр для выгрузки в 1С</b>")
        layout.addWidget(header)

        # Period selection
        period_group = QGroupBox("Период")
        period_layout = QHBoxLayout(period_group)

        period_layout.addWidget(QLabel("С:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.dateChanged.connect(self.refresh)
        period_layout.addWidget(self.date_from)

        period_layout.addWidget(QLabel("По:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self.refresh)
        period_layout.addWidget(self.date_to)

        # Quick period buttons
        btn_week = QPushButton("Неделя")
        btn_week.clicked.connect(lambda: self._set_period(7))
        period_layout.addWidget(btn_week)

        btn_month = QPushButton("Месяц")
        btn_month.clicked.connect(lambda: self._set_period(30))
        period_layout.addWidget(btn_month)

        btn_quarter = QPushButton("Квартал")
        btn_quarter.clicked.connect(lambda: self._set_period(90))
        period_layout.addWidget(btn_quarter)

        period_layout.addStretch()

        layout.addWidget(period_group)

        # Filter options
        filter_layout = QHBoxLayout()

        # Shipment type filter
        filter_layout.addWidget(QLabel("Тип:"))
        self.combo_shipment_type = QComboBox()
        self.combo_shipment_type.addItem("Все", None)
        self.combo_shipment_type.addItem("Авиаперевозка", ShipmentType.AIR)
        self.combo_shipment_type.addItem("Местная доставка", ShipmentType.LOCAL_DELIVERY)
        self.combo_shipment_type.setCurrentIndex(0)
        self.combo_shipment_type.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.combo_shipment_type)

        # Status filter
        filter_layout.addWidget(QLabel("Статус:"))
        self.combo_status = QComboBox()
        self.combo_status.addItem("Все", None)
        self.combo_status.addItem("Черновик", ShipmentStatus.DRAFT)
        self.combo_status.addItem("Готов", ShipmentStatus.READY)
        self.combo_status.addItem("Отправлен", ShipmentStatus.SENT)
        self.combo_status.addItem("Архив", ShipmentStatus.ARCHIVED)
        self.combo_status.setCurrentIndex(0)
        self.combo_status.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.combo_status)

        filter_layout.addStretch()

        btn_select_all = QPushButton("Выбрать все")
        btn_select_all.clicked.connect(self._select_all)
        filter_layout.addWidget(btn_select_all)

        btn_deselect = QPushButton("Снять выделение")
        btn_deselect.clicked.connect(self._deselect_all)
        filter_layout.addWidget(btn_deselect)

        layout.addLayout(filter_layout)

        # Shipment table with checkboxes
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "", "AWB", "Дата", "Отправитель", "Получатель", "Вес", "Мест", "Сумма"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 30)
        self.table.itemChanged.connect(self._update_summary)
        layout.addWidget(self.table)

        # Summary
        summary_layout = QHBoxLayout()
        self.lbl_count = QLabel("Выбрано: 0")
        summary_layout.addWidget(self.lbl_count)

        self.lbl_weight = QLabel("Вес: 0.00 кг")
        summary_layout.addWidget(self.lbl_weight)

        self.lbl_pieces = QLabel("Мест: 0")
        summary_layout.addWidget(self.lbl_pieces)

        self.lbl_amount = QLabel("Сумма: 0.00")
        summary_layout.addWidget(self.lbl_amount)

        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        # Action buttons
        btn_layout = QHBoxLayout()

        btn_generate = QPushButton("Сформировать реестр")
        btn_generate.setMinimumHeight(40)
        btn_generate.clicked.connect(self._on_generate)
        btn_layout.addWidget(btn_generate)

        btn_export = QPushButton("Экспорт в Excel...")
        btn_export.clicked.connect(self._on_export)
        btn_layout.addWidget(btn_export)

        btn_layout.addStretch()

        btn_refresh = QPushButton("Обновить")
        btn_refresh.clicked.connect(self.refresh)
        btn_layout.addWidget(btn_refresh)

        layout.addLayout(btn_layout)

    def _set_period(self, days: int):
        """Set period to last N days."""
        today = QDate.currentDate()
        self.date_to.setDate(today)
        self.date_from.setDate(today.addDays(-days))

    def refresh(self):
        """Load shipments for the selected period."""
        date_from = self.date_from.date().toPython()
        date_to = self.date_to.date().toPython()

        shipment_type = self.combo_shipment_type.currentData(Qt.UserRole)  # None если "Все"
        status = self.combo_status.currentData(Qt.UserRole)  # None если "Все"

        try:
            shipments = self._shipment_repo.get_by_period(
                date_from=date_from,
                date_to=date_to,
                shipment_type=shipment_type,
                status=status,
                load_relations=True,
            )

            self.table.blockSignals(True)
            self.table.setRowCount(len(shipments))

            for row, shipment in enumerate(shipments):
                # Checkbox
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk.setCheckState(Qt.Unchecked)
                chk.setData(Qt.UserRole, shipment.id)
                self.table.setItem(row, 0, chk)

                self.table.setItem(row, 1, QTableWidgetItem(shipment.awb_number or ""))
                self.table.setItem(row, 2, QTableWidgetItem(
                    shipment.shipment_date.strftime("%d.%m.%Y") if shipment.shipment_date else ""
                ))
                self.table.setItem(row, 3, QTableWidgetItem(shipment.shipper_name or ""))
                self.table.setItem(row, 4, QTableWidgetItem(shipment.consignee_name or ""))
                self.table.setItem(row, 5, QTableWidgetItem(
                    f"{shipment.weight_kg:.2f}" if shipment.weight_kg else ""
                ))
                self.table.setItem(row, 6, QTableWidgetItem(
                    str(shipment.pieces) if shipment.pieces else ""
                ))
                self.table.setItem(row, 7, QTableWidgetItem(
                    f"{shipment.total_amount:.2f}" if shipment.total_amount else ""
                ))

            self.table.blockSignals(False)
            self._update_summary()

        except Exception as e:
            logger.error(f"Failed to load shipments: {e}")

    def _select_all(self):
        """Select all shipments."""
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)
        self.table.blockSignals(False)
        self._update_summary()

    def _deselect_all(self):
        """Deselect all shipments."""
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)
        self.table.blockSignals(False)
        self._update_summary()

    def _get_selected_shipment_ids(self) -> list[int]:
        """Get list of selected shipment IDs."""
        selected = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                shipment_id = item.data(Qt.UserRole)
                if shipment_id:
                    selected.append(shipment_id)
        return selected

    def _update_summary(self):
        """Update summary labels."""
        selected_ids = self._get_selected_shipment_ids()
        count = len(selected_ids)

        total_weight = 0.0
        total_pieces = 0
        total_amount = 0.0

        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                # Weight
                weight_item = self.table.item(row, 5)
                if weight_item and weight_item.text():
                    try:
                        total_weight += float(weight_item.text())
                    except ValueError:
                        pass

                # Pieces
                pieces_item = self.table.item(row, 6)
                if pieces_item and pieces_item.text():
                    try:
                        total_pieces += int(pieces_item.text())
                    except ValueError:
                        pass

                # Amount
                amount_item = self.table.item(row, 7)
                if amount_item and amount_item.text():
                    try:
                        total_amount += float(amount_item.text())
                    except ValueError:
                        pass

        self.lbl_count.setText(f"Выбрано: {count}")
        self.lbl_weight.setText(f"Вес: {total_weight:.2f} кг")
        self.lbl_pieces.setText(f"Мест: {total_pieces}")
        self.lbl_amount.setText(f"Сумма: {total_amount:.2f}")

    def _on_generate(self):
        """Generate registry for selected shipments."""
        shipment_ids = self._get_selected_shipment_ids()
        if not shipment_ids:
            QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы одно отправление")
            return

        try:
            # Generate registry document
            date_from = self.date_from.date().toPython()
            date_to = self.date_to.date().toPython()

            doc = self._document_service.generate_registry(
                shipment_ids=shipment_ids,
                date_from=date_from,
                date_to=date_to,
            )

            QMessageBox.information(
                self, "Успех",
                f"Реестр создан:\n{doc.file_path}"
            )

        except Exception as e:
            logger.error(f"Failed to generate registry: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать реестр:\n{e}")

    def _on_export(self):
        """Export registry to Excel file."""
        shipment_ids = self._get_selected_shipment_ids()
        if not shipment_ids:
            QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы одно отправление")
            return

        # Ask for save location
        date_from = self.date_from.date().toPython()
        date_to = self.date_to.date().toPython()
        default_name = f"Реестр_{date_from.strftime('%d.%m.%Y')}_{date_to.strftime('%d.%m.%Y')}.xlsx"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить реестр",
            default_name,
            "Excel Files (*.xlsx)"
        )

        if not file_path:
            return

        try:
            self._document_service.export_registry_to_excel(
                shipment_ids=shipment_ids,
                output_path=file_path,
                date_from=date_from,
                date_to=date_to,
            )

            QMessageBox.information(
                self, "Успех",
                f"Реестр экспортирован и открыт:\n{file_path}\n\n"
                f"Записей: {len(shipment_ids)}"
            )

            # Открыть файл в Excel
            try:
                if platform.system() == 'Windows':
                    os.startfile(file_path)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', file_path])
                else:  # Linux
                    subprocess.run(['xdg-open', file_path])
                logger.info(f"Opened Excel file: {file_path}")
            except Exception as e:
                logger.warning(f"Could not auto-open Excel: {e}")
                # Не показывать ошибку пользователю, файл уже сохранен

        except Exception as e:
            logger.error(f"Failed to export registry: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать реестр:\n{e}")
