# AirDocs - Document Service
# ==================================

import logging
from pathlib import Path
from typing import Any

from core.constants import DocumentType, DocumentStatus, ClientType
from core.exceptions import GenerationError, ValidationError
from core.app_context import get_context
from data.models import Shipment, Document
from data.repositories import (
    ShipmentRepository,
    DocumentRepository,
    AuditLogRepository,
)
from utils.path_builder import PathBuilder
from utils.file_utils import calculate_file_hash, get_file_size

logger = logging.getLogger("airdocs.business")


class DocumentService:
    """
    Orchestration service for document generation.

    Coordinates:
    - Document generation (Word, Excel, PDF)
    - File storage and versioning
    - PDF conversion
    - Document packaging

    Generation strategies:
    - Word/Excel: docxtpl/openpyxl (template-based)
    - AWB PDF: AWB Editor (if available) -> Overlay fallback
    - PDF Conversion: Office COM (primary) -> LibreOffice (fallback)
    """

    def __init__(self):
        self._shipment_repo = ShipmentRepository()
        self._document_repo = DocumentRepository()
        self._audit_repo = AuditLogRepository()
        self._context = get_context()
        self._path_builder = PathBuilder()

        # Lazy-loaded generators
        self._word_generator = None
        self._excel_generator = None
        self._awb_generator = None
        self._pdf_converter = None
        self._awb_editor = None

    @property
    def word_generator(self):
        """Lazy load Word generator."""
        if self._word_generator is None:
            from generators.word_generator import WordGenerator
            self._word_generator = WordGenerator()
        return self._word_generator

    @property
    def excel_generator(self):
        """Lazy load Excel generator."""
        if self._excel_generator is None:
            from generators.excel_generator import ExcelGenerator
            self._excel_generator = ExcelGenerator()
        return self._excel_generator

    @property
    def awb_generator(self):
        """Lazy load AWB PDF generator."""
        if self._awb_generator is None:
            from generators.awb_pdf_generator import AWBPDFGenerator
            self._awb_generator = AWBPDFGenerator()
        return self._awb_generator

    @property
    def pdf_converter(self):
        """Lazy load PDF converter."""
        if self._pdf_converter is None:
            from generators.pdf_converter import PDFConverter
            self._pdf_converter = PDFConverter()
        return self._pdf_converter

    @property
    def awb_editor(self):
        """Lazy load AWB Editor integration."""
        if self._awb_editor is None:
            from integrations.awb_editor import AWBEditorIntegration
            self._awb_editor = AWBEditorIntegration()
        return self._awb_editor

    def generate_document(
        self,
        shipment_id: int,
        document_type: DocumentType,
        convert_to_pdf: bool = False,
        action_name: str = "Создание",
    ) -> Document:
        """
        Generate a single document for a shipment.

        Args:
            shipment_id: ID of shipment
            document_type: Type of document to generate
            convert_to_pdf: Whether to convert to PDF after generation
            action_name: Name for folder structure (e.g., "Создание", "Корректировка")

        Returns:
            Generated Document record

        Raises:
            GenerationError: If generation fails
        """
        # Get shipment with relations
        shipment = self._shipment_repo.get_by_id(shipment_id, load_relations=True)
        if not shipment:
            raise GenerationError(
                f"Отправление не найдено (id={shipment_id})",
                document_type=str(document_type),
            )

        # Build output directory
        output_dir = self._path_builder.build_shipment_path(
            shipment.awb_number,
            action_name,
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get next version
        version = self._document_repo.get_next_version(shipment_id, document_type)

        # Build template context from shipment
        context = shipment.to_template_context()

        # Add document-specific context
        context["document_type"] = document_type.label
        context["document_version"] = version

        # Generate based on document type
        if document_type == DocumentType.AWB:
            output_path = self._generate_awb(shipment, context, output_dir, version)
        elif document_type in (DocumentType.INVOICE, DocumentType.UPD, DocumentType.ACT, DocumentType.INVOICE_TAX, DocumentType.WAYBILL):
            output_path = self._generate_word_document(
                document_type, context, output_dir, version, convert_to_pdf
            )
        elif document_type == DocumentType.REGISTRY_1C:
            output_path = self._generate_excel_document(
                document_type, context, output_dir, version, convert_to_pdf
            )
        else:
            raise GenerationError(
                f"Неподдерживаемый тип документа: {document_type}",
                document_type=str(document_type),
            )

        # Create document record
        document = Document(
            shipment_id=shipment_id,
            document_type=document_type,
            file_path=str(output_path),
            file_name=output_path.name,
            file_hash=calculate_file_hash(output_path),
            file_size=get_file_size(output_path),
            version=version,
            status=DocumentStatus.GENERATED,
        )

        doc_id = self._document_repo.create(document)
        document.id = doc_id

        # Audit log
        self._audit_repo.log_action(
            entity_type="document",
            entity_id=doc_id,
            action="created",
            new_values={
                "shipment_id": shipment_id,
                "document_type": str(document_type),
                "file_path": str(output_path),
                "version": version,
            },
        )

        logger.info(
            f"Generated document: {document_type} for AWB {shipment.awb_number} "
            f"(v{version}, path={output_path})"
        )

        return document

    def _generate_awb(
        self,
        shipment: Shipment,
        context: dict[str, Any],
        output_dir: Path,
        version: int,
    ) -> Path:
        """
        Generate AWB PDF.

        Strategy:
        1. Try AWB Editor (if enabled and available)
        2. Fall back to overlay strategy (ReportLab + PyPDF)
        """
        # Build filename
        if version > 1:
            filename = f"AWB-{shipment.awb_number}_v{version}.pdf"
        else:
            filename = f"AWB-{shipment.awb_number}.pdf"

        output_path = output_dir / filename

        # Strategy 1: Try AWB Editor (if available)
        if self.awb_editor.is_available():
            logger.info(f"AWB generation: attempting AWB Editor strategy for {shipment.awb_number}")
            success, awb_path, message = self.awb_editor.generate_awb(context, output_dir)

            if success and awb_path and awb_path.exists():
                # Rename to expected filename if different
                if awb_path != output_path:
                    awb_path.rename(output_path)
                logger.info(f"AWB generation: SUCCESS via AWB Editor - {output_path}")
                return output_path
            else:
                logger.warning(f"AWB Editor failed: {message}. Falling back to overlay strategy.")

        # Strategy 2: Overlay (ReportLab + PyPDF merge)
        logger.info(f"AWB generation: using overlay strategy for {shipment.awb_number}")
        self.awb_generator.generate(context, output_path)
        logger.info(f"AWB generation: SUCCESS via overlay - {output_path}")

        return output_path

    def _generate_word_document(
        self,
        document_type: DocumentType,
        context: dict[str, Any],
        output_dir: Path,
        version: int,
        convert_to_pdf: bool,
    ) -> Path:
        """
        Generate Word document from template.

        Strategy: docxtpl (Jinja2-based template filling)
        PDF conversion: Office COM (primary) -> LibreOffice (fallback)
        """
        # Determine template
        template_mapping = {
            DocumentType.INVOICE: "invoice",
            DocumentType.UPD: "upd",
            DocumentType.ACT: "act",
            DocumentType.INVOICE_TAX: "invoice",  # Uses same template as invoice
            DocumentType.WAYBILL: "waybill",
        }
        template_name = template_mapping.get(document_type, "invoice")

        # Build filename
        type_names = {
            DocumentType.INVOICE: "Счет",
            DocumentType.UPD: "УПД",
            DocumentType.ACT: "Акт",
            DocumentType.INVOICE_TAX: "Счет-фактура",
            DocumentType.WAYBILL: "Накладная",
        }
        base_name = type_names.get(document_type, str(document_type))
        awb = context.get("awb_number", "000")

        if version > 1:
            filename = f"{base_name}_{awb}_v{version}"
        else:
            filename = f"{base_name}_{awb}"

        # Generate Word using docxtpl strategy
        docx_path = output_dir / f"{filename}.docx"
        logger.info(f"Word generation: using docxtpl strategy for {document_type}")
        self.word_generator.generate(template_name, context, docx_path)
        logger.info(f"Word generation: SUCCESS via docxtpl - {docx_path}")

        # Convert to PDF if requested
        if convert_to_pdf:
            pdf_path = output_dir / f"{filename}.pdf"
            conversion_result = self.pdf_converter.convert(docx_path, pdf_path)
            if conversion_result.success:
                logger.info(
                    f"PDF conversion: SUCCESS via {conversion_result.method} - {pdf_path}"
                )
                return pdf_path
            else:
                logger.warning(
                    f"PDF conversion failed ({conversion_result.error}), returning DOCX"
                )

        return docx_path

    def _generate_excel_document(
        self,
        document_type: DocumentType,
        context: dict[str, Any],
        output_dir: Path,
        version: int,
        convert_to_pdf: bool,
    ) -> Path:
        """
        Generate Excel document from template.

        Strategy: openpyxl (placeholder-based template filling)
        PDF conversion: Office COM (primary) -> LibreOffice (fallback)
        """
        # Build filename
        awb = context.get("awb_number", "000")

        if version > 1:
            filename = f"Реестр_{awb}_v{version}"
        else:
            filename = f"Реестр_{awb}"

        # Generate Excel using openpyxl strategy
        xlsx_path = output_dir / f"{filename}.xlsx"
        logger.info(f"Excel generation: using openpyxl strategy for {document_type}")
        self.excel_generator.generate("registry_1c", context, xlsx_path)
        logger.info(f"Excel generation: SUCCESS via openpyxl - {xlsx_path}")

        # Convert to PDF if requested
        if convert_to_pdf:
            pdf_path = output_dir / f"{filename}.pdf"
            conversion_result = self.pdf_converter.convert(xlsx_path, pdf_path)
            if conversion_result.success:
                logger.info(
                    f"PDF conversion: SUCCESS via {conversion_result.method} - {pdf_path}"
                )
                return pdf_path
            else:
                logger.warning(
                    f"PDF conversion failed ({conversion_result.error}), returning XLSX"
                )

        return xlsx_path

    def generate_invoice_set(
        self,
        shipment_id: int,
        client_type: ClientType,
        convert_to_pdf: bool = True,
        action_name: str = "Комплект",
    ) -> list[Document]:
        """
        Generate a complete set of documents for a client type.

        Args:
            shipment_id: ID of shipment
            client_type: Type of client (determines which documents)
            convert_to_pdf: Convert all documents to PDF
            action_name: Name for folder structure

        Returns:
            List of generated Document records
        """
        # Get document types for client
        doc_types = client_type.document_types

        documents = []
        for doc_type in doc_types:
            try:
                doc = self.generate_document(
                    shipment_id,
                    doc_type,
                    convert_to_pdf=convert_to_pdf,
                    action_name=f"{action_name}_{client_type}",
                )
                documents.append(doc)
            except GenerationError as e:
                logger.error(f"Failed to generate {doc_type}: {e}")
                # Continue with other documents

        return documents

    def get_documents_for_shipment(
        self,
        shipment_id: int,
        document_type: DocumentType | None = None,
    ) -> list[Document]:
        """Get all documents for a shipment."""
        return self._document_repo.get_by_shipment(shipment_id, document_type)

    def get_document(self, document_id: int) -> Document | None:
        """Get document by ID."""
        return self._document_repo.get_by_id(document_id)

    def update_document_status(
        self,
        document_id: int,
        status: DocumentStatus,
    ) -> bool:
        """Update document status."""
        result = self._document_repo.update_status(document_id, status)
        if result:
            self._audit_repo.log_action(
                entity_type="document",
                entity_id=document_id,
                action="updated",
                changes=[{"field": "status", "new": str(status)}],
            )
        return result

    def regenerate_document(
        self,
        document_id: int,
        convert_to_pdf: bool = False,
    ) -> Document:
        """
        Regenerate a document (creates new version).

        Args:
            document_id: ID of document to regenerate

        Returns:
            New Document record with incremented version
        """
        old_doc = self._document_repo.get_by_id(document_id)
        if not old_doc:
            raise GenerationError(f"Документ не найден (id={document_id})")

        return self.generate_document(
            old_doc.shipment_id,
            old_doc.document_type,
            convert_to_pdf=convert_to_pdf,
            action_name="Корректировка",
        )

    def generate_invoice_set_extended(
        self,
        shipment_id: int,
        client_type: ClientType,
        document_types: list[DocumentType],
        convert_to_pdf: bool = True,
        create_zip: bool = True,
        create_email: bool = True,
    ) -> dict[str, Any]:
        """
        Generate extended invoice set with ZIP packaging and email draft.

        Args:
            shipment_id: ID of shipment
            client_type: Type of client
            document_types: List of document types to generate
            convert_to_pdf: Convert documents to PDF
            create_zip: Create ZIP archive
            create_email: Create email draft

        Returns:
            Dictionary with generated documents, ZIP path, and email draft
        """
        import zipfile
        from datetime import datetime

        shipment = self._shipment_repo.get_by_id(shipment_id, load_relations=True)
        if not shipment:
            raise GenerationError(f"Отправление не найдено (id={shipment_id})")

        # Build output directory
        output_dir = self._path_builder.build_shipment_path(
            shipment.awb_number,
            f"Комплект_{client_type}",
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate documents
        documents = []
        for doc_type in document_types:
            try:
                doc = self.generate_document(
                    shipment_id,
                    doc_type,
                    convert_to_pdf=convert_to_pdf,
                    action_name=f"Комплект_{client_type}",
                )
                documents.append(doc)
            except GenerationError as e:
                logger.error(f"Failed to generate {doc_type}: {e}")

        result = {
            "shipment_id": shipment_id,
            "awb_number": shipment.awb_number,
            "client_type": client_type,
            "documents": documents,
            "zip_path": None,
            "email_draft_id": None,
        }

        # Create ZIP if requested
        if create_zip and documents:
            zip_filename = f"Комплект_{shipment.awb_number}_{client_type}.zip"
            zip_path = output_dir / zip_filename

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for doc in documents:
                    doc_path = Path(doc.file_path)
                    if doc_path.exists():
                        zf.write(doc_path, doc_path.name)

            result["zip_path"] = str(zip_path)
            logger.info(f"Created ZIP archive: {zip_path}")

        # Create email draft if requested
        if create_email and documents:
            from data.repositories import EmailDraftRepository
            from data.models import EmailDraft

            email_repo = EmailDraftRepository()

            # Build email subject and body
            subject = f"Документы по AWB {shipment.awb_number}"
            body_lines = [
                f"Добрый день,",
                f"",
                f"Направляем документы по отправлению AWB {shipment.awb_number}:",
                f"",
            ]
            for doc in documents:
                body_lines.append(f"- {doc.document_type.label}")
            body_lines.extend([
                f"",
                f"С уважением,",
                f"Отдел логистики",
            ])

            # Determine recipient email
            recipient = ""
            if shipment.consignee and hasattr(shipment.consignee, "email"):
                recipient = shipment.consignee.email or ""

            # Collect attachment paths
            attachments = [doc.file_path for doc in documents]
            if result["zip_path"]:
                attachments = [result["zip_path"]]

            draft = EmailDraft(
                shipment_id=shipment_id,
                recipient=recipient,
                subject=subject,
                body="\n".join(body_lines),
                attachments=attachments,
                status="draft",
            )

            draft_id = email_repo.create(draft)
            result["email_draft_id"] = draft_id
            logger.info(f"Created email draft: id={draft_id}")

        return result

    def generate_registry(
        self,
        shipment_ids: list[int],
        date_from=None,
        date_to=None,
    ) -> Document:
        """
        Generate a registry Excel document for multiple shipments.

        Args:
            shipment_ids: List of shipment IDs to include
            date_from: Start date of period (optional)
            date_to: End date of period (optional)

        Returns:
            Generated Document record
        """
        from datetime import date, datetime

        if not shipment_ids:
            raise GenerationError("Не выбрано ни одного отправления")

        # Get shipments
        shipments = self._shipment_repo.get_by_ids(shipment_ids, load_relations=True)
        if not shipments:
            raise GenerationError("Отправления не найдены")

        # Build output directory
        output_dir = self._context.get_path("output_dir") / "Реестры"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build filename
        if date_from and date_to:
            if isinstance(date_from, date):
                date_from_str = date_from.strftime("%d.%m.%Y")
            else:
                date_from_str = str(date_from)
            if isinstance(date_to, date):
                date_to_str = date_to.strftime("%d.%m.%Y")
            else:
                date_to_str = str(date_to)
            filename = f"Реестр_{date_from_str}_{date_to_str}"
        else:
            filename = f"Реестр_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        xlsx_path = output_dir / f"{filename}.xlsx"

        # Build data for registry
        registry_data = []
        for shipment in shipments:
            registry_data.append({
                "awb_number": shipment.awb_number or "",
                "shipment_date": shipment.shipment_date.strftime("%d.%m.%Y") if shipment.shipment_date else "",
                "shipper_name": shipment.shipper_name or "",
                "consignee_name": shipment.consignee_name or "",
                "weight_kg": shipment.weight_kg or 0,
                "pieces": shipment.pieces or 0,
                "goods_description": shipment.goods_description or "",
                "total_amount": shipment.total_amount or 0,
            })

        # Generate Excel using excel generator
        self.excel_generator.generate_registry(registry_data, xlsx_path)

        # Create document record (registry is not linked to a single shipment)
        document = Document(
            shipment_id=None,  # Registry spans multiple shipments
            document_type=DocumentType.REGISTRY_1C,
            file_path=str(xlsx_path),
            file_name=xlsx_path.name,
            file_hash=calculate_file_hash(xlsx_path),
            file_size=get_file_size(xlsx_path),
            version=1,
            status=DocumentStatus.GENERATED,
        )

        doc_id = self._document_repo.create(document)
        document.id = doc_id

        # Audit log
        self._audit_repo.log_action(
            entity_type="document",
            entity_id=doc_id,
            action="created",
            new_values={
                "document_type": str(DocumentType.REGISTRY_1C),
                "file_path": str(xlsx_path),
                "shipment_count": len(shipments),
            },
        )

        logger.info(f"Generated registry: {xlsx_path} ({len(shipments)} shipments)")
        return document

    def export_registry_to_excel(
        self,
        shipment_ids: list[int],
        output_path: str | Path,
        date_from=None,
        date_to=None,
    ) -> Path:
        """
        Export registry directly to a specified Excel file.

        Args:
            shipment_ids: List of shipment IDs to include
            output_path: Path where to save the Excel file
            date_from: Start date of period (optional)
            date_to: End date of period (optional)

        Returns:
            Path to the generated Excel file
        """
        from datetime import date

        output_path = Path(output_path)

        if not shipment_ids:
            raise GenerationError("Не выбрано ни одного отправления")

        # Get shipments
        shipments = self._shipment_repo.get_by_ids(shipment_ids, load_relations=True)
        if not shipments:
            raise GenerationError("Отправления не найдены")

        # Build data for registry
        registry_data = []
        for shipment in shipments:
            registry_data.append({
                "awb_number": shipment.awb_number or "",
                "shipment_date": shipment.shipment_date.strftime("%d.%m.%Y") if shipment.shipment_date else "",
                "shipper_name": shipment.shipper_name or "",
                "consignee_name": shipment.consignee_name or "",
                "weight_kg": shipment.weight_kg or 0,
                "pieces": shipment.pieces or 0,
                "goods_description": shipment.goods_description or "",
                "total_amount": shipment.total_amount or 0,
            })

        # Define columns with Russian headers
        columns = [
            ("awb_number", "AWB №"),
            ("shipment_date", "Дата"),
            ("shipper_name", "Отправитель"),
            ("consignee_name", "Получатель"),
            ("weight_kg", "Вес (кг)"),
            ("pieces", "Мест"),
            ("goods_description", "Описание"),
            ("total_amount", "Сумма"),
        ]

        # Generate Excel
        self.excel_generator.generate_registry(registry_data, output_path, columns)

        logger.info(f"Exported registry to: {output_path} ({len(shipments)} shipments)")
        return output_path
