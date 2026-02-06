# AirDocs - Constants
# ===================

from enum import Enum, auto
from typing import Final

from core.version import VERSION as APP_VERSION

# Application info
APP_NAME: Final[str] = "AirDocs"


class ShipmentType(str, Enum):
    """Types of shipments."""
    AIR = "air"
    LOCAL_DELIVERY = "local_delivery"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        """Russian label for UI."""
        labels = {
            self.AIR: "Авиаперевозка",
            self.LOCAL_DELIVERY: "Местная доставка",
        }
        return labels.get(self, self.value)


class ShipmentStatus(str, Enum):
    """Status of a shipment."""
    DRAFT = "draft"
    READY = "ready"
    SENT = "sent"
    ARCHIVED = "archived"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        """Russian label for UI."""
        labels = {
            self.DRAFT: "Черновик",
            self.READY: "Готов",
            self.SENT: "Отправлен",
            self.ARCHIVED: "Архив",
        }
        return labels.get(self, self.value)

    @property
    def color(self) -> str:
        """Color for UI display."""
        colors = {
            self.DRAFT: "#FFA500",
            self.READY: "#00AA00",
            self.SENT: "#0000FF",
            self.ARCHIVED: "#808080",
        }
        return colors.get(self, "#000000")


class DocumentType(str, Enum):
    """Types of documents that can be generated."""
    AWB = "awb"
    INVOICE = "invoice"
    UPD = "upd"
    INVOICE_TAX = "invoice_tax"
    ACT = "act"
    WAYBILL = "waybill"
    REGISTRY_1C = "registry_1c"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        """Russian label for UI."""
        labels = {
            self.AWB: "Авианакладная (AWB)",
            self.INVOICE: "Счет",
            self.UPD: "УПД",
            self.INVOICE_TAX: "Счет-фактура",
            self.ACT: "Акт выполненных работ",
            self.WAYBILL: "Накладная",
            self.REGISTRY_1C: "Реестр 1С",
        }
        return labels.get(self, self.value)

    @property
    def extension(self) -> str:
        """Default file extension for this document type."""
        extensions = {
            self.AWB: ".pdf",
            self.INVOICE: ".docx",
            self.UPD: ".docx",
            self.INVOICE_TAX: ".docx",
            self.ACT: ".docx",
            self.WAYBILL: ".docx",
            self.REGISTRY_1C: ".xlsx",
        }
        return extensions.get(self, ".pdf")


class DocumentStatus(str, Enum):
    """Status of a generated document."""
    GENERATED = "generated"
    SENT = "sent"
    ARCHIVED = "archived"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        """Russian label for UI."""
        labels = {
            self.GENERATED: "Сформирован",
            self.SENT: "Отправлен",
            self.ARCHIVED: "Архив",
        }
        return labels.get(self, self.value)


class PartyType(str, Enum):
    """Types of parties (контрагенты)."""
    SHIPPER = "shipper"
    CONSIGNEE = "consignee"
    AGENT = "agent"
    CARRIER = "carrier"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        """Russian label for UI."""
        labels = {
            self.SHIPPER: "Отправитель",
            self.CONSIGNEE: "Получатель",
            self.AGENT: "Агент",
            self.CARRIER: "Перевозчик",
        }
        return labels.get(self, self.value)


class ClientType(str, Enum):
    """Types of clients for document sets."""
    TIA = "TiA"
    FF = "FF"
    IP = "IP"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        """Russian label for UI."""
        labels = {
            self.TIA: "Транспортно-экспедиционная компания",
            self.FF: "Freight Forwarder",
            self.IP: "Индивидуальный предприниматель",
        }
        return labels.get(self, self.value)

    @property
    def document_types(self) -> list[DocumentType]:
        """Document types included in set for this client type."""
        sets = {
            self.TIA: [
                DocumentType.INVOICE,
                DocumentType.UPD,
                DocumentType.INVOICE_TAX,
                DocumentType.ACT,
                DocumentType.AWB,
            ],
            self.FF: [
                DocumentType.INVOICE,
                DocumentType.UPD,
                DocumentType.INVOICE_TAX,
                DocumentType.ACT,
                DocumentType.AWB,
            ],
            self.IP: [
                DocumentType.INVOICE,
                DocumentType.ACT,
                DocumentType.AWB,
            ],
        }
        return sets.get(self, [])


# Audit log actions
class AuditAction(str, Enum):
    """Actions logged in audit log."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    SENT = "sent"
    ARCHIVED = "archived"

    def __str__(self) -> str:
        return self.value


# PDF conversion methods
class PDFConversionMethod(str, Enum):
    """Methods for converting documents to PDF."""
    OFFICE_COM = "office_com"
    LIBREOFFICE = "libreoffice"
    NONE = "none"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        labels = {
            self.OFFICE_COM: "Microsoft Office (COM)",
            self.LIBREOFFICE: "LibreOffice",
            self.NONE: "Нет доступных методов",
        }
        return labels.get(self, self.value)


# AWB PDF generation strategies
class AWBStrategy(str, Enum):
    """Strategies for AWB PDF generation."""
    OVERLAY = "overlay"
    ACROFORM = "acroform"
    AWB_EDITOR = "awb_editor"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        labels = {
            self.OVERLAY: "Overlay (ReportLab)",
            self.ACROFORM: "AcroForm Fill",
            self.AWB_EDITOR: "AWB Editor",
        }
        return labels.get(self, self.value)


# File paths
DEFAULT_DATA_DIR: Final[str] = "data"
DEFAULT_OUTPUT_DIR: Final[str] = "data/output"
DEFAULT_LOGS_DIR: Final[str] = "data/logs"
DEFAULT_DB_NAME: Final[str] = "airdocs.db"
DEFAULT_LOG_NAME: Final[str] = "app.log"

# Date/time formats
DATE_FORMAT_DISPLAY: Final[str] = "%d.%m.%Y"
DATE_FORMAT_DB: Final[str] = "%Y-%m-%d"
DATETIME_FORMAT_DB: Final[str] = "%Y-%m-%d %H:%M:%S"

# Validation patterns
AWB_NUMBER_PATTERN: Final[str] = r"^[0-9]{3}-[0-9]{8}$|^[0-9]{8,11}$"
INN_PATTERN: Final[str] = r"^[0-9]{10}$|^[0-9]{12}$"
KPP_PATTERN: Final[str] = r"^[0-9]{9}$"
EMAIL_PATTERN: Final[str] = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
