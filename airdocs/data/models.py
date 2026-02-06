# AirDocs - Data Models
# ============================

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
import json

from core.constants import (
    ShipmentType,
    ShipmentStatus,
    DocumentType,
    DocumentStatus,
    PartyType,
)


@dataclass
class Party:
    """Контрагент (shipper, consignee, agent, carrier)."""

    id: int | None = None
    party_type: PartyType = PartyType.SHIPPER
    name: str = ""
    address: str | None = None
    inn: str | None = None
    kpp: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "party_type": str(self.party_type),
            "name": self.name,
            "address": self.address,
            "inn": self.inn,
            "kpp": self.kpp,
            "contact_person": self.contact_person,
            "phone": self.phone,
            "email": self.email,
            "notes": self.notes,
            "is_active": 1 if self.is_active else 0,
        }

    @classmethod
    def from_row(cls, row) -> "Party":
        """Create from database row."""
        return cls(
            id=row["id"],
            party_type=PartyType(row["party_type"]),
            name=row["name"],
            address=row["address"],
            inn=row["inn"],
            kpp=row["kpp"],
            contact_person=row["contact_person"],
            phone=row["phone"],
            email=row["email"],
            notes=row["notes"] if "notes" in row.keys() else None,
            is_active=bool(row["is_active"]),
            created_at=row["created_at"] if "created_at" in row.keys() else None,
            updated_at=row["updated_at"] if "updated_at" in row.keys() else None,
        )


@dataclass
class Template:
    """Пресет/Шаблон документа."""

    id: int | None = None
    template_name: str = ""
    template_type: str = "preset"  # preset, word, excel, pdf, email
    client_type: str | None = None  # TiA, FF, IP, all
    description: str | None = None
    field_values: dict[str, Any] = field(default_factory=dict)
    file_path: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "template_name": self.template_name,
            "template_type": self.template_type,
            "client_type": self.client_type,
            "description": self.description,
            "field_values_json": json.dumps(self.field_values, ensure_ascii=False) if self.field_values else None,
            "file_path": self.file_path,
            "is_active": 1 if self.is_active else 0,
        }

    @classmethod
    def from_row(cls, row) -> "Template":
        """Create from database row."""
        field_values = {}
        if row["field_values_json"]:
            try:
                field_values = json.loads(row["field_values_json"])
            except json.JSONDecodeError:
                pass

        return cls(
            id=row["id"],
            template_name=row["template_name"],
            template_type=row["template_type"],
            client_type=row["client_type"],
            description=row["description"] if "description" in row.keys() else None,
            field_values=field_values,
            file_path=row["file_path"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"] if "created_at" in row.keys() else None,
            updated_at=row["updated_at"] if "updated_at" in row.keys() else None,
        )


@dataclass
class Shipment:
    """Отправление (AWB или местная доставка)."""

    id: int | None = None
    awb_number: str = ""
    shipment_type: ShipmentType = ShipmentType.AIR
    shipment_date: date | None = None
    shipper_id: int | None = None
    consignee_id: int | None = None
    agent_id: int | None = None
    template_id: int | None = None
    weight_kg: float = 0.0
    pieces: int = 1
    volume_m3: float | None = None
    goods_description: str | None = None
    status: ShipmentStatus = ShipmentStatus.DRAFT
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Related objects (populated by repository)
    shipper: Party | None = None
    consignee: Party | None = None
    agent: Party | None = None
    template: Template | None = None
    documents: list["Document"] = field(default_factory=list)

    @property
    def shipper_name(self) -> str | None:
        """Get shipper name from related object."""
        return self.shipper.name if self.shipper else None

    @property
    def consignee_name(self) -> str | None:
        """Get consignee name from related object."""
        return self.consignee.name if self.consignee else None

    @property
    def agent_name(self) -> str | None:
        """Get agent name from related object."""
        return self.agent.name if self.agent else None

    @property
    def total_amount(self) -> float | None:
        """Placeholder for total amount (to be calculated from rates)."""
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "awb_number": self.awb_number,
            "shipment_type": str(self.shipment_type),
            "shipment_date": self.shipment_date.isoformat() if self.shipment_date else None,
            "shipper_id": self.shipper_id,
            "consignee_id": self.consignee_id,
            "agent_id": self.agent_id,
            "template_id": self.template_id,
            "weight_kg": self.weight_kg,
            "pieces": self.pieces,
            "volume_m3": self.volume_m3,
            "goods_description": self.goods_description,
            "status": str(self.status),
            "notes": self.notes,
        }

    @classmethod
    def from_row(cls, row) -> "Shipment":
        """Create from database row."""
        shipment_date = row["shipment_date"]
        if isinstance(shipment_date, str):
            shipment_date = date.fromisoformat(shipment_date)

        return cls(
            id=row["id"],
            awb_number=row["awb_number"],
            shipment_type=ShipmentType(row["shipment_type"]),
            shipment_date=shipment_date,
            shipper_id=row["shipper_id"],
            consignee_id=row["consignee_id"],
            agent_id=row["agent_id"],
            template_id=row["template_id"],
            weight_kg=row["weight_kg"],
            pieces=row["pieces"],
            volume_m3=row["volume_m3"],
            goods_description=row["goods_description"],
            status=ShipmentStatus(row["status"]),
            notes=row["notes"] if "notes" in row.keys() else None,
            created_at=row["created_at"] if "created_at" in row.keys() else None,
            updated_at=row["updated_at"] if "updated_at" in row.keys() else None,
        )

    def to_template_context(self) -> dict[str, Any]:
        """
        Convert to context dictionary for template rendering.
        Uses canonical field names.
        """
        context = {
            "awb_number": self.awb_number,
            "shipment_date": self.shipment_date.strftime("%d.%m.%Y") if self.shipment_date else "",
            "shipment_type": self.shipment_type.label,
            "weight_kg": f"{self.weight_kg:.3f}",
            "pieces": self.pieces,
            "volume_m3": f"{self.volume_m3:.3f}" if self.volume_m3 else "",
            "goods_description": self.goods_description or "",
            "status": self.status.label,
        }

        # Add shipper fields
        if self.shipper:
            context.update({
                "shipper_name": self.shipper.name,
                "shipper_address": self.shipper.address or "",
                "shipper_inn": self.shipper.inn or "",
                "shipper_kpp": self.shipper.kpp or "",
                "shipper_contact": self.shipper.contact_person or "",
                "shipper_phone": self.shipper.phone or "",
                "shipper_email": self.shipper.email or "",
            })

        # Add consignee fields
        if self.consignee:
            context.update({
                "consignee_name": self.consignee.name,
                "consignee_address": self.consignee.address or "",
                "consignee_inn": self.consignee.inn or "",
                "consignee_kpp": self.consignee.kpp or "",
                "consignee_contact": self.consignee.contact_person or "",
                "consignee_phone": self.consignee.phone or "",
                "consignee_email": self.consignee.email or "",
            })

        # Add agent fields
        if self.agent:
            context.update({
                "agent_name": self.agent.name,
                "agent_address": self.agent.address or "",
            })

        # Add current date fields
        today = date.today()
        context.update({
            "current_date": today.strftime("%d.%m.%Y"),
            "current_year": today.year,
        })

        return context


@dataclass
class Document:
    """Сгенерированный документ."""

    id: int | None = None
    shipment_id: int | None = None
    document_type: DocumentType = DocumentType.AWB
    file_path: str = ""
    file_name: str = ""
    file_hash: str = ""
    file_size: int | None = None
    version: int = 1
    status: DocumentStatus = DocumentStatus.GENERATED
    generated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "shipment_id": self.shipment_id,
            "document_type": str(self.document_type),
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "version": self.version,
            "status": str(self.status),
        }

    @classmethod
    def from_row(cls, row) -> "Document":
        """Create from database row."""
        return cls(
            id=row["id"],
            shipment_id=row["shipment_id"],
            document_type=DocumentType(row["document_type"]),
            file_path=row["file_path"],
            file_name=row["file_name"],
            file_hash=row["file_hash"],
            file_size=row["file_size"],
            version=row["version"],
            status=DocumentStatus(row["status"]),
            generated_at=row["generated_at"] if "generated_at" in row.keys() else None,
        )


@dataclass
class EmailDraft:
    """Черновик email."""

    id: int | None = None
    shipment_id: int | None = None
    recipient_email: str = ""
    recipient_name: str | None = None
    subject: str = ""
    body_html: str | None = None
    body_text: str | None = None
    attachments: list[dict[str, str]] = field(default_factory=list)
    status: str = "draft"  # draft, sent, failed
    error_message: str | None = None
    created_at: datetime | None = None
    sent_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "shipment_id": self.shipment_id,
            "recipient_email": self.recipient_email,
            "recipient_name": self.recipient_name,
            "subject": self.subject,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "attachments_json": json.dumps(self.attachments, ensure_ascii=False) if self.attachments else None,
            "status": self.status,
            "error_message": self.error_message,
        }

    @classmethod
    def from_row(cls, row) -> "EmailDraft":
        """Create from database row."""
        attachments = []
        if row["attachments_json"]:
            try:
                attachments = json.loads(row["attachments_json"])
            except json.JSONDecodeError:
                pass

        return cls(
            id=row["id"],
            shipment_id=row["shipment_id"],
            recipient_email=row["recipient_email"],
            recipient_name=row["recipient_name"],
            subject=row["subject"],
            body_html=row["body_html"],
            body_text=row["body_text"],
            attachments=attachments,
            status=row["status"],
            error_message=row["error_message"],
            created_at=row["created_at"] if "created_at" in row.keys() else None,
            sent_at=row["sent_at"],
        )


@dataclass
class AuditLog:
    """Запись журнала изменений."""

    id: int | None = None
    entity_type: str = ""
    entity_id: int | None = None
    action: str = ""
    user_name: str = "system"
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    changes: list[dict[str, Any]] | None = None
    timestamp: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "user_name": self.user_name,
            "old_values_json": json.dumps(self.old_values, ensure_ascii=False, default=str) if self.old_values else None,
            "new_values_json": json.dumps(self.new_values, ensure_ascii=False, default=str) if self.new_values else None,
            "changes_json": json.dumps(self.changes, ensure_ascii=False, default=str) if self.changes else None,
        }

    @classmethod
    def from_row(cls, row) -> "AuditLog":
        """Create from database row."""
        old_values = None
        new_values = None
        changes = None

        if row["old_values_json"]:
            try:
                old_values = json.loads(row["old_values_json"])
            except json.JSONDecodeError:
                pass

        if row["new_values_json"]:
            try:
                new_values = json.loads(row["new_values_json"])
            except json.JSONDecodeError:
                pass

        if row["changes_json"]:
            try:
                changes = json.loads(row["changes_json"])
            except json.JSONDecodeError:
                pass

        return cls(
            id=row["id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            action=row["action"],
            user_name=row["user_name"],
            old_values=old_values,
            new_values=new_values,
            changes=changes,
            timestamp=row["timestamp"],
        )


@dataclass
class AWBOverlayCalibration:
    """Калибровка координат для overlay AWB PDF."""

    id: int | None = None
    template_name: str = ""
    field_name: str = ""
    x_coord: float = 0.0
    y_coord: float = 0.0
    font_size: float = 10.0
    font_name: str = "Helvetica"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "template_name": self.template_name,
            "field_name": self.field_name,
            "x_coord": self.x_coord,
            "y_coord": self.y_coord,
            "font_size": self.font_size,
            "font_name": self.font_name,
        }

    @classmethod
    def from_row(cls, row) -> "AWBOverlayCalibration":
        """Create from database row."""
        return cls(
            id=row["id"],
            template_name=row["template_name"],
            field_name=row["field_name"],
            x_coord=row["x_coord"],
            y_coord=row["y_coord"],
            font_size=row["font_size"],
            font_name=row["font_name"],
            created_at=row["created_at"] if "created_at" in row.keys() else None,
            updated_at=row["updated_at"] if "updated_at" in row.keys() else None,
        )
