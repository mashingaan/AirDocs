# AirDocs - Delivery Module
# =================================

import logging
from datetime import date

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
    QComboBox,
    QMessageBox,
    QMenu,
)
from PySide6.QtCore import Qt

from core.constants import ShipmentType, ShipmentStatus, DocumentType
from data.repositories import ShipmentRepository
from business.document_service import DocumentService
from ui.widgets.shipment_form import ShipmentForm

logger = logging.getLogger("airdocs.ui")


class DeliveryModule(QWidget):
    """
    Local Delivery (Местная доставка) module.

    Manages local deliveries (non-air shipments) with:
    - CRUD operations for local delivery shipments
    - Document generation (waybill, invoice, act)
    - Status management
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._shipment_repo = ShipmentRepository()
        self._document_service = DocumentService()
        self._current_shipment_id: int | None = None

        self._init_ui()
        self.refresh()

    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        header = QLabel("<b>Местная доставка</b>")
        header_layout.addWidget(header)

        # Status filter
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Статус:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("Все", None)
        for status in ShipmentStatus:
            self.status_filter.addItem(status.label, status)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        header_layout.addWidget(self.status_filter)

        layout.addLayout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Номер", "Дата", "Отправитель", "Получатель", "Статус", "Документы"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_add = QPushButton("Добавить")
        btn_add.clicked.connect(self._on_add)
        btn_layout.addWidget(btn_add)

        btn_edit = QPushButton("Редактировать")
        btn_edit.clicked.connect(self._on_edit)
        btn_layout.addWidget(btn_edit)

        btn_delete = QPushButton("Удалить")
        btn_delete.clicked.connect(self._on_delete)
        btn_layout.addWidget(btn_delete)

        btn_layout.addStretch()

        # Generation buttons
        btn_waybill = QPushButton("Накладная")
        btn_waybill.clicked.connect(lambda: self._on_generate(DocumentType.WAYBILL))
        btn_layout.addWidget(btn_waybill)

        btn_invoice = QPushButton("Счет")
        btn_invoice.clicked.connect(lambda: self._on_generate(DocumentType.INVOICE))
        btn_layout.addWidget(btn_invoice)

        btn_act = QPushButton("Акт")
        btn_act.clicked.connect(lambda: self._on_generate(DocumentType.ACT))
        btn_layout.addWidget(btn_act)

        btn_all_docs = QPushButton("Все документы")
        btn_all_docs.clicked.connect(self._on_generate_all)
        btn_layout.addWidget(btn_all_docs)

        layout.addLayout(btn_layout)

    def refresh(self):
        """Refresh table data."""
        status_filter = self.status_filter.currentData()

        try:
            shipments = self._shipment_repo.get_all(
                shipment_type=ShipmentType.LOCAL_DELIVERY,
                status=status_filter,
                load_relations=True,
            )

            self.table.setRowCount(len(shipments))
            for row, shipment in enumerate(shipments):
                self.table.setItem(row, 0, QTableWidgetItem(str(shipment.id)))
                self.table.setItem(row, 1, QTableWidgetItem(shipment.awb_number or ""))
                self.table.setItem(row, 2, QTableWidgetItem(
                    shipment.shipment_date.strftime("%d.%m.%Y") if shipment.shipment_date else ""
                ))
                self.table.setItem(row, 3, QTableWidgetItem(shipment.shipper_name or ""))
                self.table.setItem(row, 4, QTableWidgetItem(shipment.consignee_name or ""))

                status_item = QTableWidgetItem(shipment.status.label)
                status_item.setForeground(Qt.GlobalColor.darkGreen if shipment.status == ShipmentStatus.READY else Qt.GlobalColor.darkGray)
                self.table.setItem(row, 5, status_item)

                # Document count
                docs = self._document_service.get_documents_for_shipment(shipment.id)
                self.table.setItem(row, 6, QTableWidgetItem(str(len(docs))))

                # Store ID in first column
                self.table.item(row, 0).setData(Qt.UserRole, shipment.id)

        except Exception as e:
            logger.error(f"Failed to load deliveries: {e}")

    def _get_selected_id(self) -> int | None:
        """Get selected shipment ID."""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            return self.table.item(row, 0).data(Qt.UserRole)
        return None

    def _show_context_menu(self, pos):
        """Show context menu for table."""
        shipment_id = self._get_selected_id()
        if not shipment_id:
            return

        menu = QMenu(self)

        menu.addAction("Редактировать", self._on_edit)
        menu.addSeparator()
        menu.addAction("Накладная", lambda: self._on_generate(DocumentType.WAYBILL))
        menu.addAction("Счет", lambda: self._on_generate(DocumentType.INVOICE))
        menu.addAction("Акт", lambda: self._on_generate(DocumentType.ACT))
        menu.addAction("Все документы", self._on_generate_all)
        menu.addSeparator()

        # Status submenu
        status_menu = menu.addMenu("Изменить статус")
        for status in ShipmentStatus:
            status_menu.addAction(status.label, lambda s=status: self._on_change_status(s))

        menu.addSeparator()
        menu.addAction("Удалить", self._on_delete)

        menu.exec_(self.table.mapToGlobal(pos))

    def _on_add(self):
        """Add new delivery."""
        from ui.dialogs.shipment_dialog import ShipmentDialog

        dialog = ShipmentDialog(shipment_type=ShipmentType.LOCAL_DELIVERY, parent=self)
        if dialog.exec():
            self.refresh()

    def _on_edit(self):
        """Edit selected delivery."""
        shipment_id = self._get_selected_id()
        if not shipment_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите доставку для редактирования")
            return

        from ui.dialogs.shipment_dialog import ShipmentDialog

        shipment = self._shipment_repo.get_by_id(shipment_id)
        if shipment:
            dialog = ShipmentDialog(shipment=shipment, parent=self)
            if dialog.exec():
                self.refresh()

    def _on_delete(self):
        """Delete selected delivery."""
        shipment_id = self._get_selected_id()
        if not shipment_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите доставку для удаления")
            return

        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить выбранную доставку и все связанные документы?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self._shipment_repo.delete(shipment_id)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить: {e}")

    def _on_generate(self, document_type: DocumentType):
        """Generate a specific document."""
        shipment_id = self._get_selected_id()
        if not shipment_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите доставку")
            return

        try:
            doc = self._document_service.generate_document(
                shipment_id,
                document_type,
                convert_to_pdf=True,
                action_name="Доставка",
            )
            QMessageBox.information(
                self, "Успех",
                f"Документ создан:\n{doc.file_path}"
            )
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать документ:\n{e}")

    def _on_generate_all(self):
        """Generate all documents for delivery."""
        shipment_id = self._get_selected_id()
        if not shipment_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите доставку")
            return

        try:
            docs = []
            for doc_type in [DocumentType.WAYBILL, DocumentType.INVOICE, DocumentType.ACT]:
                doc = self._document_service.generate_document(
                    shipment_id,
                    doc_type,
                    convert_to_pdf=True,
                    action_name="Доставка",
                )
                docs.append(doc)

            QMessageBox.information(
                self, "Успех",
                f"Создано документов: {len(docs)}"
            )
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка генерации:\n{e}")

    def _on_change_status(self, status: ShipmentStatus):
        """Change shipment status."""
        shipment_id = self._get_selected_id()
        if shipment_id:
            from business.shipment_service import ShipmentService
            service = ShipmentService()
            service.update_status(shipment_id, status)
            self.refresh()
