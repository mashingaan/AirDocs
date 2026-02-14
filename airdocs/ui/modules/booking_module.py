# AirDocs - Booking Module
# ================================

import logging
from datetime import date

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QMessageBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt

from business.validators import ValidationResult
from core.constants import ShipmentStatus, DocumentType
from core.exceptions import ValidationError, GenerationError
from business.shipment_service import ShipmentService
from business.document_service import DocumentService
from data.models import Shipment
from ui.widgets.shipment_form import ShipmentForm
from utils.pdf_printer import PDFPrinter
from pathlib import Path

logger = logging.getLogger("airdocs.ui")


class BookingModule(QWidget):
    """
    Booking (Бронирование) module.

    Main module for AWB creation and management.

    Layout:
    - Left: List of shipments (table)
    - Right: Shipment form (create/edit)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._shipment_service = ShipmentService()
        self._document_service = DocumentService()
        self._current_shipment: Shipment | None = None
        self._pdf_printer = PDFPrinter()

        self._init_ui()
        self._load_shipments()

    def _init_ui(self):
        """Initialize UI components."""
        layout = QHBoxLayout(self)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # === Left panel: Shipments list ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Toolbar
        toolbar_layout = QHBoxLayout()

        self.btn_new = QPushButton("Создать AWB")
        self.btn_new.clicked.connect(self.create_new_shipment)
        toolbar_layout.addWidget(self.btn_new)

        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        toolbar_layout.addWidget(self.btn_refresh)

        toolbar_layout.addStretch()

        left_layout.addLayout(toolbar_layout)

        # Shipments table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "AWB №", "Дата", "Получатель", "Статус", "Документы"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._on_double_click)

        left_layout.addWidget(self.table)

        splitter.addWidget(left_panel)

        # === Right panel: Shipment form ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Form
        self.form = ShipmentForm()
        right_layout.addWidget(self.form)

        # Action buttons
        buttons_group = QGroupBox("Действия")
        buttons_layout = QVBoxLayout(buttons_group)

        self.btn_save = QPushButton("Сохранить")
        self.btn_save.clicked.connect(self._on_save)
        buttons_layout.addWidget(self.btn_save)

        self.btn_generate_awb = QPushButton("Сформировать AWB")
        self.btn_generate_awb.clicked.connect(self._on_generate_awb)
        buttons_layout.addWidget(self.btn_generate_awb)

        self.btn_print_awb = QPushButton("Печать AWB")
        self.btn_print_awb.clicked.connect(self._on_print_awb)
        buttons_layout.addWidget(self.btn_print_awb)

        self.btn_generate_set = QPushButton("Сформировать комплект")
        self.btn_generate_set.clicked.connect(self._on_generate_set)
        buttons_layout.addWidget(self.btn_generate_set)

        self.btn_print_set = QPushButton("Печать комплекта")
        self.btn_print_set.clicked.connect(self._on_print_set)
        buttons_layout.addWidget(self.btn_print_set)

        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.clicked.connect(self._on_delete)
        buttons_layout.addWidget(self.btn_delete)

        right_layout.addWidget(buttons_group)

        splitter.addWidget(right_panel)

        # Set initial splitter sizes (40% left, 60% right)
        splitter.setSizes([400, 600])

    def _load_shipments(self):
        """Load shipments into table."""
        try:
            shipments, _ = self._shipment_service.list_shipments(page_size=100)
            self._populate_table(shipments)
        except Exception as e:
            logger.error(f"Failed to load shipments: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить отправления: {e}")

    def _populate_table(self, shipments: list[Shipment]):
        """Populate table with shipments."""
        self.table.setRowCount(len(shipments))

        for row, shipment in enumerate(shipments):
            self.table.setItem(row, 0, QTableWidgetItem(str(shipment.id)))
            self.table.setItem(row, 1, QTableWidgetItem(shipment.awb_number))

            date_str = shipment.shipment_date.strftime("%d.%m.%Y") if shipment.shipment_date else ""
            self.table.setItem(row, 2, QTableWidgetItem(date_str))

            consignee_name = shipment.consignee.name if shipment.consignee else ""
            self.table.setItem(row, 3, QTableWidgetItem(consignee_name))

            status_item = QTableWidgetItem(shipment.status.label)
            self.table.setItem(row, 4, status_item)

            # Documents count
            doc_count = len(shipment.documents) if shipment.documents else 0
            self.table.setItem(row, 5, QTableWidgetItem(str(doc_count)))

            # Store shipment ID in row
            self.table.item(row, 0).setData(Qt.UserRole, shipment.id)

    def _on_selection_changed(self):
        """Handle table selection change."""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            shipment_id = self.table.item(row, 0).data(Qt.UserRole)
            self._load_shipment(shipment_id)
        else:
            self._current_shipment = None
            self.form.clear()

    def _on_double_click(self, index):
        """Handle double-click on table row."""
        row = index.row()
        shipment_id = self.table.item(row, 0).data(Qt.UserRole)
        self._load_shipment(shipment_id)

    def _load_shipment(self, shipment_id: int):
        """Load shipment into form."""
        try:
            shipment = self._shipment_service.get_shipment(shipment_id)
            if shipment:
                self._current_shipment = shipment
                self.form.load_shipment(shipment)
                logger.debug(f"Loaded shipment: {shipment.awb_number}")
        except Exception as e:
            logger.error(f"Failed to load shipment {shipment_id}: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить отправление: {e}")

    def create_new_shipment(self):
        """Create a new shipment."""
        try:
            logger.info("Creating new shipment - clearing form")
            self._current_shipment = None
            self.table.clearSelection()
            self.form.clear()
            self.form.set_defaults()
            # Focus on AWB number field for better UX
            self.form.awb_number.setFocus()
            self.form.awb_number.selectAll()
            logger.info("New shipment form ready")
        except Exception as e:
            logger.error(f"Error creating new shipment: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать новое отправление: {e}")

    def refresh(self):
        """Refresh shipments list."""
        self._load_shipments()
        if self._current_shipment:
            self._load_shipment(self._current_shipment.id)

    def _on_save(self):
        """Handle save button click."""
        try:
            # Ensure required parties exist before validating/saving.
            # This is the ONLY place where we may show a modal "no parties" warning.
            for selector in (
                self.form.shipper_selector,
                self.form.consignee_selector,
                self.form.agent_selector,
            ):
                if not selector.ensure_parties():
                    return

            # Validate form first
            validation_result = self.form.validate()

            if not validation_result.is_valid:
                # Show detailed error message
                self._show_validation_errors(validation_result)
                return

            # Get data after validation passed
            data = self.form.get_data()

            if self._current_shipment:
                # Update existing
                shipment = self._shipment_service.update_shipment(
                    self._current_shipment.id,
                    **data
                )
                QMessageBox.information(
                    self, "Успех",
                    f"Отправление {shipment.awb_number} обновлено"
                )
            else:
                # Create new
                shipment = self._shipment_service.create_shipment(**data)
                self._current_shipment = shipment
                QMessageBox.information(
                    self, "Успех",
                    f"Отправление {shipment.awb_number} создано"
                )

            self.refresh()

        except ValidationError as e:
            QMessageBox.warning(self, "Ошибка валидации", str(e))
        except Exception as e:
            logger.error(f"Save failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    def _show_validation_errors(self, result: ValidationResult):
        """Show validation errors with field details."""
        from PySide6.QtWidgets import QMessageBox

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Ошибка валидации")
        msg.setText("Пожалуйста, исправьте следующие ошибки:")

        # Build detailed error message
        error_text = "\n".join(f"• {error}" for error in result.errors)
        msg.setInformativeText(error_text)

        # Add field-specific details if available
        if result.field_errors:
            field_labels = {
                "awb_number": "AWB номер",
                "weight_kg": "Вес",
                "pieces": "Количество мест",
                "volume_m3": "Объем",
                "goods_description": "Описание товара",
                "shipper_id": "Отправитель",
                "consignee_id": "Получатель",
                "agent_id": "Агент",
                "shipment_date": "Дата отправления",
                "shipment_type": "Тип отправления",
                "notes": "Примечания",
            }

            details = []
            for field, error in result.field_errors.items():
                label = field_labels.get(field, field)
                details.append(f"{label}: {error}")

            msg.setDetailedText("\n".join(details))

        msg.exec()

    def _on_generate_awb(self):
        """Handle generate AWB button click."""
        if not self._current_shipment:
            QMessageBox.warning(self, "Предупреждение", "Сначала сохраните отправление")
            return

        try:
            document = self._document_service.generate_document(
                self._current_shipment.id,
                DocumentType.AWB,
            )

            QMessageBox.information(
                self, "Успех",
                f"AWB сформирован:\n{document.file_path}"
            )

            # Update status
            self._shipment_service.update_status(
                self._current_shipment.id,
                ShipmentStatus.READY
            )
            self.refresh()

        except GenerationError as e:
            QMessageBox.critical(self, "Ошибка генерации", str(e))
        except Exception as e:
            logger.error(f"AWB generation failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать AWB: {e}")

    def _on_generate_set(self):
        """Handle generate document set button click."""
        if not self._current_shipment:
            QMessageBox.warning(self, "Предупреждение", "Сначала сохраните отправление")
            return

        try:
            # Generate invoice, UPD, act
            for doc_type in [DocumentType.INVOICE, DocumentType.ACT]:
                self._document_service.generate_document(
                    self._current_shipment.id,
                    doc_type,
                    convert_to_pdf=True,
                    action_name="Комплект",
                )

            QMessageBox.information(
                self, "Успех",
                "Комплект документов сформирован"
            )
            self.refresh()

        except GenerationError as e:
            QMessageBox.critical(self, "Ошибка генерации", str(e))
        except Exception as e:
            logger.error(f"Document set generation failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать комплект: {e}")

    def _on_delete(self):
        """Handle delete button click."""
        if not self._current_shipment:
            return

        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить отправление {self._current_shipment.awb_number}?\n"
            "Все связанные документы также будут удалены.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self._shipment_service.delete_shipment(self._current_shipment.id)
                self._current_shipment = None
                self.form.clear()
                self.refresh()
                QMessageBox.information(self, "Успех", "Отправление удалено")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить: {e}")

    def _get_printer_mode(self) -> str:
        """Get printer mode from config."""
        from core.app_context import get_context
        context = get_context()
        printer_config = context.config.get("printer", {})
        return printer_config.get("default_mode", "a4")

    def _on_print_awb(self):
        """Handle print AWB button click."""
        if not self._current_shipment:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите отправление")
            return

        try:
            # Get AWB documents for current shipment
            awb_docs = self._document_service.get_documents_for_shipment(
                self._current_shipment.id,
                DocumentType.AWB
            )

            if not awb_docs:
                QMessageBox.warning(
                    self, "Предупреждение",
                    "AWB не сформирован. Сначала нажмите 'Сформировать AWB'"
                )
                return

            # Get latest version
            latest_doc = max(awb_docs, key=lambda d: d.version)
            pdf_path = Path(latest_doc.file_path)

            if not pdf_path.exists():
                QMessageBox.critical(
                    self, "Ошибка",
                    f"Файл AWB не найден: {pdf_path}"
                )
                return

            # Get template info for AWB
            from generators.awb_pdf_generator import AWBPDFGenerator
            awb_generator = AWBPDFGenerator()
            template_info = awb_generator.get_template_info()
            
            # Log template info for debugging
            logger.info(f"AWB template info: {template_info}")
            
            # Get printer mode from config
            printer_mode = self._get_printer_mode()

            # Show print preview
            success = self._pdf_printer.print_with_preview(
                pdf_path,
                parent=self,
                printer_mode=printer_mode,
                template_info=template_info
            )

            if success:
                logger.info(f"Printed AWB: {pdf_path}")
            else:
                logger.debug("Print cancelled by user")

        except Exception as e:
            logger.error(f"Print AWB failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось напечатать AWB: {e}")

    def _on_print_set(self):
        """Handle print document set button click."""
        if not self._current_shipment:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите отправление")
            return

        try:
            # Get all documents for current shipment
            all_docs = self._document_service.get_documents_for_shipment(
                self._current_shipment.id
            )

            if not all_docs:
                QMessageBox.warning(
                    self, "Предупреждение",
                    "Документы не сформированы. Сначала нажмите 'Сформировать комплект'"
                )
                return

            # Filter PDF documents only
            pdf_docs = [
                doc for doc in all_docs
                if Path(doc.file_path).suffix.lower() == '.pdf'
            ]

            if not pdf_docs:
                QMessageBox.warning(
                    self, "Предупреждение",
                    "PDF документы не найдены. Убедитесь, что комплект сформирован с конвертацией в PDF"
                )
                return

            # Get file paths
            pdf_paths = [Path(doc.file_path) for doc in pdf_docs]

            # Check all files exist
            missing = [p for p in pdf_paths if not p.exists()]
            if missing:
                QMessageBox.critical(
                    self, "Ошибка",
                    f"Не найдены файлы:\n" + "\n".join(str(p) for p in missing)
                )
                return

            # Get printer mode
            printer_mode = self._get_printer_mode()

            # Get template info for AWB if available
            from generators.awb_pdf_generator import AWBPDFGenerator
            awb_generator = AWBPDFGenerator()
            template_info = awb_generator.get_template_info()
            logger.info(f"Document set template info: {template_info}")

            # Print all PDFs
            success = self._pdf_printer.print_multiple(
                pdf_paths,
                parent=self,
                printer_mode=printer_mode,
                template_info=template_info
            )

            if success:
                logger.info(f"Printed document set: {len(pdf_paths)} files")
            else:
                logger.debug("Print cancelled by user")

        except Exception as e:
            logger.error(f"Print set failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось напечатать комплект: {e}")
