# AirDocs - Invoice Sets Module
# =====================================

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QPushButton,
    QLabel,
    QComboBox,
    QGroupBox,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QFileDialog,
    QProgressDialog,
)
from PySide6.QtCore import Qt

from core.constants import ShipmentType, ShipmentStatus, ClientType, DocumentType
from data.repositories import ShipmentRepository
from business.document_service import DocumentService

logger = logging.getLogger("airdocs.ui")


class InvoiceSetsModule(QWidget):
    """
    Invoice Sets (Комплекты счетов) module.

    Handles document package assembly for clients with:
    - Client type selection (TiA, FF, IP)
    - Multi-shipment selection
    - Document set generation
    - ZIP packaging
    - Email draft preparation
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header = QLabel("<b>Комплекты документов для клиентов</b>")
        header.setStyleSheet("font-size: 14px; margin-bottom: 5px;")
        layout.addWidget(header)

        # Splitter for shipment selection and options
        splitter = QSplitter(Qt.Horizontal)

        # Left: Shipment selection
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)

        # Filter
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        filter_layout.addWidget(QLabel("Статус:"))
        self.status_filter = QComboBox()
        self.status_filter.setMinimumWidth(150)
        self.status_filter.addItem("Готовые к отправке", ShipmentStatus.READY)
        self.status_filter.addItem("Все", None)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.status_filter)
        filter_layout.addStretch()

        btn_select_all = QPushButton("Выбрать все")
        btn_select_all.clicked.connect(self._select_all)
        filter_layout.addWidget(btn_select_all)

        btn_deselect = QPushButton("Снять выделение")
        btn_deselect.clicked.connect(self._deselect_all)
        filter_layout.addWidget(btn_deselect)

        left_layout.addLayout(filter_layout)

        # Shipment table with checkboxes
        self.shipment_table = QTableWidget()
        self.shipment_table.setColumnCount(6)
        self.shipment_table.setHorizontalHeaderLabels([
            "", "AWB", "Дата", "Отправитель", "Получатель", "Сумма"
        ])
        self.shipment_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.shipment_table.setColumnWidth(0, 30)
        self.shipment_table.setColumnWidth(1, 120)
        self.shipment_table.setColumnWidth(2, 90)
        self.shipment_table.setColumnWidth(5, 100)
        self.shipment_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.shipment_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.shipment_table.setMinimumWidth(500)
        left_layout.addWidget(self.shipment_table)

        splitter.addWidget(left_widget)

        # Right: Options
        right_widget = QWidget()
        right_widget.setMaximumWidth(320)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)

        # Client type selection
        client_group = QGroupBox("Тип клиента")
        client_layout = QVBoxLayout(client_group)

        self.client_type = QComboBox()
        for ct in ClientType:
            self.client_type.addItem(ct.label, ct)
        self.client_type.currentIndexChanged.connect(self._update_document_list)
        client_layout.addWidget(self.client_type)

        # Documents to include
        client_layout.addWidget(QLabel("Документы в комплекте:"))
        self.doc_list = QListWidget()
        self.doc_list.setMinimumHeight(120)
        self.doc_list.setMaximumHeight(180)
        client_layout.addWidget(self.doc_list)

        right_layout.addWidget(client_group)

        # Output options
        output_group = QGroupBox("Параметры вывода")
        output_layout = QVBoxLayout(output_group)

        self.chk_convert_pdf = QCheckBox("Конвертировать в PDF")
        self.chk_convert_pdf.setChecked(True)
        output_layout.addWidget(self.chk_convert_pdf)

        self.chk_create_zip = QCheckBox("Создать ZIP архив")
        self.chk_create_zip.setChecked(True)
        output_layout.addWidget(self.chk_create_zip)

        self.chk_create_email = QCheckBox("Подготовить email")
        self.chk_create_email.setChecked(True)
        output_layout.addWidget(self.chk_create_email)

        right_layout.addWidget(output_group)

        # Generate buttons
        btn_generate = QPushButton("Сформировать комплекты")
        btn_generate.setMinimumHeight(40)
        btn_generate.clicked.connect(self._on_generate)
        right_layout.addWidget(btn_generate)

        btn_open_folder = QPushButton("Открыть папку")
        btn_open_folder.clicked.connect(self._on_open_folder)
        right_layout.addWidget(btn_open_folder)

        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)  # Left widget stretches
        splitter.setStretchFactor(1, 0)  # Right widget fixed

        layout.addWidget(splitter, 1)  # Splitter takes all available space

        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Выбрано отправлений: 0")
        self.status_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # Initialize document list
        self._update_document_list()

    def refresh(self):
        """Refresh shipment list."""
        status_filter = self.status_filter.currentData()

        try:
            shipments = self._shipment_repo.get_all(
                shipment_type=ShipmentType.AIR,
                status=status_filter,
                load_relations=True,
            )

            self.shipment_table.setRowCount(len(shipments))
            for row, shipment in enumerate(shipments):
                # Checkbox
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk.setCheckState(Qt.Unchecked)
                chk.setData(Qt.UserRole, shipment.id)
                self.shipment_table.setItem(row, 0, chk)

                self.shipment_table.setItem(row, 1, QTableWidgetItem(shipment.awb_number or ""))
                self.shipment_table.setItem(row, 2, QTableWidgetItem(
                    shipment.shipment_date.strftime("%d.%m.%Y") if shipment.shipment_date else ""
                ))
                self.shipment_table.setItem(row, 3, QTableWidgetItem(shipment.shipper_name or ""))
                self.shipment_table.setItem(row, 4, QTableWidgetItem(shipment.consignee_name or ""))
                self.shipment_table.setItem(row, 5, QTableWidgetItem(
                    f"{shipment.total_amount:.2f}" if shipment.total_amount else ""
                ))

            self._update_status()

        except Exception as e:
            logger.error(f"Failed to load shipments: {e}")

    def _update_document_list(self):
        """Update document list based on client type."""
        client_type_data = self.client_type.currentData()
        if not client_type_data:
            return

        # Convert to ClientType if it's a string (str Enum issue with Qt)
        if isinstance(client_type_data, str):
            client_type = ClientType(client_type_data)
        else:
            client_type = client_type_data

        self.doc_list.clear()
        for doc_type in client_type.document_types:
            item = QListWidgetItem(doc_type.label)
            item.setData(Qt.UserRole, doc_type)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.doc_list.addItem(item)

    def _select_all(self):
        """Select all shipments."""
        for row in range(self.shipment_table.rowCount()):
            item = self.shipment_table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)
        self._update_status()

    def _deselect_all(self):
        """Deselect all shipments."""
        for row in range(self.shipment_table.rowCount()):
            item = self.shipment_table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)
        self._update_status()

    def _get_selected_shipment_ids(self) -> list[int]:
        """Get list of selected shipment IDs."""
        selected = []
        for row in range(self.shipment_table.rowCount()):
            item = self.shipment_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                shipment_id = item.data(Qt.UserRole)
                if shipment_id:
                    selected.append(shipment_id)
        return selected

    def _get_selected_document_types(self) -> list[DocumentType]:
        """Get list of selected document types."""
        selected = []
        for i in range(self.doc_list.count()):
            item = self.doc_list.item(i)
            if item.checkState() == Qt.Checked:
                doc_type = item.data(Qt.UserRole)
                if doc_type:
                    selected.append(doc_type)
        return selected

    def _update_status(self):
        """Update status label."""
        selected = len(self._get_selected_shipment_ids())
        self.status_label.setText(f"Выбрано отправлений: {selected}")

    def _on_generate(self):
        """Generate document sets for selected shipments."""
        shipment_ids = self._get_selected_shipment_ids()
        if not shipment_ids:
            QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы одно отправление")
            return

        client_type_data = self.client_type.currentData()
        # Convert to ClientType if it's a string (str Enum issue with Qt)
        if isinstance(client_type_data, str):
            client_type = ClientType(client_type_data)
        else:
            client_type = client_type_data
        doc_types = self._get_selected_document_types()
        convert_pdf = self.chk_convert_pdf.isChecked()
        create_zip = self.chk_create_zip.isChecked()
        create_email = self.chk_create_email.isChecked()

        if not doc_types:
            QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы один тип документа")
            return

        # Progress dialog
        progress = QProgressDialog("Формирование комплектов...", "Отмена", 0, len(shipment_ids), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        results = []
        errors = []

        try:
            for i, shipment_id in enumerate(shipment_ids):
                if progress.wasCanceled():
                    break

                progress.setValue(i)
                shipment = self._shipment_repo.get_by_id(shipment_id)
                if not shipment:
                    continue

                progress.setLabelText(f"Обработка {shipment.awb_number}...")

                try:
                    result = self._document_service.generate_invoice_set_extended(
                        shipment_id=shipment_id,
                        client_type=client_type,
                        document_types=doc_types,
                        convert_to_pdf=convert_pdf,
                        create_zip=create_zip,
                        create_email=create_email,
                    )
                    results.append(result)
                except Exception as e:
                    errors.append(f"{shipment.awb_number}: {e}")
                    logger.error(f"Failed to generate set for {shipment.awb_number}: {e}")

            progress.setValue(len(shipment_ids))

        finally:
            progress.close()

        # Show results
        msg = f"Обработано отправлений: {len(results)}"
        if errors:
            msg += f"\n\nОшибки ({len(errors)}):\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... и еще {len(errors) - 5}"
            QMessageBox.warning(self, "Завершено с ошибками", msg)
        else:
            QMessageBox.information(self, "Успех", msg)

        self.refresh()

    def _on_open_folder(self):
        """Open output folder."""
        import os
        from core.app_context import get_context

        context = get_context()
        output_dir = context.get_path("output_dir")
        output_dir.mkdir(parents=True, exist_ok=True)

        if output_dir.exists():
            os.startfile(str(output_dir))
