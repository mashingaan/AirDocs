# AirDocs - Data Repositories
# ===================================

import logging
from typing import Any

from core.constants import PartyType, ShipmentStatus, DocumentType, DocumentStatus
from core.exceptions import DatabaseError
from .database import get_db
from .models import (
    Party,
    Template,
    Shipment,
    Document,
    EmailDraft,
    AuditLog,
    AWBOverlayCalibration,
)

logger = logging.getLogger("airdocs.data")


class BaseRepository:
    """Base class for all repositories."""

    def __init__(self):
        self._db = get_db()


class PartyRepository(BaseRepository):
    """Repository for Party (контрагент) operations."""

    TABLE = "parties"

    def create(self, party: Party) -> int:
        """Create a new party and return its ID."""
        data = party.to_dict()
        party_id = self._db.insert(self.TABLE, data)
        logger.info(f"Created party: {party.name} (id={party_id})")
        return party_id

    def get_by_id(self, party_id: int) -> Party | None:
        """Get party by ID."""
        row = self._db.fetch_one(
            f"SELECT * FROM {self.TABLE} WHERE id = ?",
            (party_id,),
        )
        return Party.from_row(row) if row else None

    def get_all(
        self,
        party_type: PartyType | None = None,
        active_only: bool = True,
    ) -> list[Party]:
        """Get all parties, optionally filtered by type."""
        conditions = []
        params = []

        if party_type:
            conditions.append("party_type = ?")
            params.append(str(party_type))

        if active_only:
            conditions.append("is_active = 1")

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self._db.fetch_all(
            f"SELECT * FROM {self.TABLE} WHERE {where} ORDER BY name",
            tuple(params),
        )
        return [Party.from_row(row) for row in rows]

    def count(self) -> int:
        """Fast COUNT(*) without loading rows."""
        row = self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM {self.TABLE} WHERE is_active = 1"
        )
        return row["count"] if row else 0

    def count_by_type(self, party_type: PartyType) -> int:
        """Fast COUNT(*) filtered by PartyType."""
        row = self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM {self.TABLE} "
            "WHERE party_type = ? AND is_active = 1",
            (str(party_type),),
        )
        return row["count"] if row else 0

    def search(self, query: str, party_type: PartyType | None = None) -> list[Party]:
        """Search parties by name, INN, or address."""
        conditions = ["(name LIKE ? OR inn LIKE ? OR address LIKE ?)"]
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]

        if party_type:
            conditions.append("party_type = ?")
            params.append(str(party_type))

        conditions.append("is_active = 1")
        where = " AND ".join(conditions)

        rows = self._db.fetch_all(
            f"SELECT * FROM {self.TABLE} WHERE {where} ORDER BY name",
            tuple(params),
        )
        return [Party.from_row(row) for row in rows]

    def update(self, party: Party) -> bool:
        """Update an existing party."""
        if party.id is None:
            raise DatabaseError("Cannot update party without ID", operation="update", table=self.TABLE)

        data = party.to_dict()
        rows_affected = self._db.update(self.TABLE, data, "id = ?", (party.id,))
        if rows_affected > 0:
            logger.info(f"Updated party: {party.name} (id={party.id})")
        return rows_affected > 0

    def delete(self, party_id: int) -> bool:
        """Soft-delete a party (set is_active = 0)."""
        rows_affected = self._db.update(
            self.TABLE,
            {"is_active": 0},
            "id = ?",
            (party_id,),
        )
        if rows_affected > 0:
            logger.info(f"Deleted party (id={party_id})")
        return rows_affected > 0


class TemplateRepository(BaseRepository):
    """Repository for Template operations."""

    TABLE = "templates"

    def create(self, template: Template) -> int:
        """Create a new template and return its ID."""
        data = template.to_dict()
        template_id = self._db.insert(self.TABLE, data)
        logger.info(f"Created template: {template.template_name} (id={template_id})")
        return template_id

    def get_by_id(self, template_id: int) -> Template | None:
        """Get template by ID."""
        row = self._db.fetch_one(
            f"SELECT * FROM {self.TABLE} WHERE id = ?",
            (template_id,),
        )
        return Template.from_row(row) if row else None

    def get_by_name(self, name: str) -> Template | None:
        """Get template by name."""
        row = self._db.fetch_one(
            f"SELECT * FROM {self.TABLE} WHERE template_name = ?",
            (name,),
        )
        return Template.from_row(row) if row else None

    def get_all(
        self,
        template_type: str | None = None,
        client_type: str | None = None,
        active_only: bool = True,
    ) -> list[Template]:
        """Get all templates, optionally filtered."""
        conditions = []
        params = []

        if template_type:
            conditions.append("template_type = ?")
            params.append(template_type)

        if client_type:
            conditions.append("(client_type = ? OR client_type = 'all')")
            params.append(client_type)

        if active_only:
            conditions.append("is_active = 1")

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self._db.fetch_all(
            f"SELECT * FROM {self.TABLE} WHERE {where} ORDER BY template_name",
            tuple(params),
        )
        return [Template.from_row(row) for row in rows]

    def get_presets(self, client_type: str | None = None) -> list[Template]:
        """Get all preset templates."""
        return self.get_all(template_type="preset", client_type=client_type)

    def update(self, template: Template) -> bool:
        """Update an existing template."""
        if template.id is None:
            raise DatabaseError("Cannot update template without ID", operation="update", table=self.TABLE)

        data = template.to_dict()
        rows_affected = self._db.update(self.TABLE, data, "id = ?", (template.id,))
        if rows_affected > 0:
            logger.info(f"Updated template: {template.template_name} (id={template.id})")
        return rows_affected > 0

    def delete(self, template_id: int) -> bool:
        """Soft-delete a template."""
        rows_affected = self._db.update(
            self.TABLE,
            {"is_active": 0},
            "id = ?",
            (template_id,),
        )
        if rows_affected > 0:
            logger.info(f"Deleted template (id={template_id})")
        return rows_affected > 0


class ShipmentRepository(BaseRepository):
    """Repository for Shipment operations."""

    TABLE = "shipments"

    def __init__(self):
        super().__init__()
        self._party_repo = PartyRepository()
        self._template_repo = TemplateRepository()
        self._document_repo = None  # Lazy init to avoid circular import

    @property
    def document_repo(self) -> "DocumentRepository":
        if self._document_repo is None:
            self._document_repo = DocumentRepository()
        return self._document_repo

    def create(self, shipment: Shipment) -> int:
        """Create a new shipment and return its ID."""
        data = shipment.to_dict()
        shipment_id = self._db.insert(self.TABLE, data)
        logger.info(f"Created shipment: {shipment.awb_number} (id={shipment_id})")
        return shipment_id

    def get_by_id(self, shipment_id: int, load_relations: bool = True) -> Shipment | None:
        """Get shipment by ID, optionally loading related entities."""
        row = self._db.fetch_one(
            f"SELECT * FROM {self.TABLE} WHERE id = ?",
            (shipment_id,),
        )
        if not row:
            return None

        shipment = Shipment.from_row(row)

        if load_relations:
            self._load_relations(shipment)

        return shipment

    def get_by_awb(self, awb_number: str, load_relations: bool = True) -> Shipment | None:
        """Get shipment by AWB number."""
        row = self._db.fetch_one(
            f"SELECT * FROM {self.TABLE} WHERE awb_number = ?",
            (awb_number,),
        )
        if not row:
            return None

        shipment = Shipment.from_row(row)

        if load_relations:
            self._load_relations(shipment)

        return shipment

    def _load_relations(self, shipment: Shipment) -> None:
        """Load related entities for a shipment."""
        if shipment.shipper_id:
            shipment.shipper = self._party_repo.get_by_id(shipment.shipper_id)
        if shipment.consignee_id:
            shipment.consignee = self._party_repo.get_by_id(shipment.consignee_id)
        if shipment.agent_id:
            shipment.agent = self._party_repo.get_by_id(shipment.agent_id)
        if shipment.template_id:
            shipment.template = self._template_repo.get_by_id(shipment.template_id)
        if shipment.id:
            shipment.documents = self.document_repo.get_by_shipment(shipment.id)

    def get_all(
        self,
        status: ShipmentStatus | None = None,
        shipment_type: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        load_relations: bool = False,
    ) -> list[Shipment]:
        """Get shipments with filters."""
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(str(status))

        if shipment_type:
            conditions.append("shipment_type = ?")
            params.append(shipment_type)

        if from_date:
            conditions.append("shipment_date >= ?")
            params.append(from_date)

        if to_date:
            conditions.append("shipment_date <= ?")
            params.append(to_date)

        if search:
            conditions.append("(awb_number LIKE ? OR goods_description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM {self.TABLE}
            WHERE {where}
            ORDER BY shipment_date DESC, id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = self._db.fetch_all(sql, tuple(params))
        shipments = [Shipment.from_row(row) for row in rows]

        if load_relations:
            for shipment in shipments:
                self._load_relations(shipment)

        return shipments

    def count(
        self,
        status: ShipmentStatus | None = None,
        shipment_type: str | None = None,
    ) -> int:
        """Count shipments with filters."""
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(str(status))

        if shipment_type:
            conditions.append("shipment_type = ?")
            params.append(shipment_type)

        where = " AND ".join(conditions) if conditions else "1=1"
        row = self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM {self.TABLE} WHERE {where}",
            tuple(params),
        )
        return row["count"] if row else 0

    def update(self, shipment: Shipment) -> bool:
        """Update an existing shipment."""
        if shipment.id is None:
            raise DatabaseError("Cannot update shipment without ID", operation="update", table=self.TABLE)

        data = shipment.to_dict()
        rows_affected = self._db.update(self.TABLE, data, "id = ?", (shipment.id,))
        if rows_affected > 0:
            logger.info(f"Updated shipment: {shipment.awb_number} (id={shipment.id})")
        return rows_affected > 0

    def update_status(self, shipment_id: int, status: ShipmentStatus) -> bool:
        """Update shipment status."""
        rows_affected = self._db.update(
            self.TABLE,
            {"status": str(status)},
            "id = ?",
            (shipment_id,),
        )
        if rows_affected > 0:
            logger.info(f"Updated shipment status: id={shipment_id}, status={status}")
        return rows_affected > 0

    def delete(self, shipment_id: int) -> bool:
        """Delete a shipment (cascade deletes documents)."""
        rows_affected = self._db.delete(self.TABLE, "id = ?", (shipment_id,))
        if rows_affected > 0:
            logger.info(f"Deleted shipment (id={shipment_id})")
        return rows_affected > 0

    def awb_exists(self, awb_number: str, exclude_id: int | None = None) -> bool:
        """Check if AWB number already exists."""
        if exclude_id:
            row = self._db.fetch_one(
                f"SELECT id FROM {self.TABLE} WHERE awb_number = ? AND id != ?",
                (awb_number, exclude_id),
            )
        else:
            row = self._db.fetch_one(
                f"SELECT id FROM {self.TABLE} WHERE awb_number = ?",
                (awb_number,),
            )
        return row is not None

    def get_by_period(
        self,
        date_from,
        date_to,
        shipment_type=None,
        status: ShipmentStatus | None = None,
        load_relations: bool = False,
    ) -> list[Shipment]:
        """Get shipments within a date period."""
        from datetime import date as date_type

        conditions = []
        params = []

        # Convert date objects to string if needed
        if isinstance(date_from, date_type):
            date_from_str = date_from.isoformat()
        else:
            date_from_str = str(date_from)

        if isinstance(date_to, date_type):
            date_to_str = date_to.isoformat()
        else:
            date_to_str = str(date_to)

        conditions.append("shipment_date >= ?")
        params.append(date_from_str)

        conditions.append("shipment_date <= ?")
        params.append(date_to_str)

        if shipment_type:
            conditions.append("shipment_type = ?")
            params.append(str(shipment_type))

        if status:
            conditions.append("status = ?")
            params.append(str(status))

        where = " AND ".join(conditions)
        rows = self._db.fetch_all(
            f"""
            SELECT * FROM {self.TABLE}
            WHERE {where}
            ORDER BY shipment_date DESC, id DESC
            """,
            tuple(params),
        )
        shipments = [Shipment.from_row(row) for row in rows]

        if load_relations:
            for shipment in shipments:
                self._load_relations(shipment)

        return shipments

    def get_by_ids(
        self,
        shipment_ids: list[int],
        load_relations: bool = False,
    ) -> list[Shipment]:
        """Get shipments by list of IDs."""
        if not shipment_ids:
            return []

        placeholders = ",".join("?" * len(shipment_ids))
        rows = self._db.fetch_all(
            f"""
            SELECT * FROM {self.TABLE}
            WHERE id IN ({placeholders})
            ORDER BY shipment_date DESC, id DESC
            """,
            tuple(shipment_ids),
        )
        shipments = [Shipment.from_row(row) for row in rows]

        if load_relations:
            for shipment in shipments:
                self._load_relations(shipment)

        return shipments


class DocumentRepository(BaseRepository):
    """Repository for Document operations."""

    TABLE = "documents"

    def create(self, document: Document) -> int:
        """Create a new document and return its ID."""
        data = document.to_dict()
        doc_id = self._db.insert(self.TABLE, data)
        logger.info(f"Created document: {document.file_name} (id={doc_id})")
        return doc_id

    def get_by_id(self, doc_id: int) -> Document | None:
        """Get document by ID."""
        row = self._db.fetch_one(
            f"SELECT * FROM {self.TABLE} WHERE id = ?",
            (doc_id,),
        )
        return Document.from_row(row) if row else None

    def get_by_shipment(
        self,
        shipment_id: int,
        document_type: DocumentType | None = None,
    ) -> list[Document]:
        """Get all documents for a shipment."""
        conditions = ["shipment_id = ?"]
        params = [shipment_id]

        if document_type:
            conditions.append("document_type = ?")
            params.append(str(document_type))

        where = " AND ".join(conditions)
        rows = self._db.fetch_all(
            f"SELECT * FROM {self.TABLE} WHERE {where} ORDER BY generated_at DESC",
            tuple(params),
        )
        return [Document.from_row(row) for row in rows]

    def get_latest_version(
        self,
        shipment_id: int,
        document_type: DocumentType,
    ) -> Document | None:
        """Get the latest version of a document type for a shipment."""
        row = self._db.fetch_one(
            f"""
            SELECT * FROM {self.TABLE}
            WHERE shipment_id = ? AND document_type = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (shipment_id, str(document_type)),
        )
        return Document.from_row(row) if row else None

    def get_next_version(
        self,
        shipment_id: int,
        document_type: DocumentType,
    ) -> int:
        """Get the next version number for a document type."""
        latest = self.get_latest_version(shipment_id, document_type)
        return (latest.version + 1) if latest else 1

    def update(self, document: Document) -> bool:
        """Update an existing document."""
        if document.id is None:
            raise DatabaseError("Cannot update document without ID", operation="update", table=self.TABLE)

        data = document.to_dict()
        rows_affected = self._db.update(self.TABLE, data, "id = ?", (document.id,))
        if rows_affected > 0:
            logger.info(f"Updated document: {document.file_name} (id={document.id})")
        return rows_affected > 0

    def update_status(self, doc_id: int, status: DocumentStatus) -> bool:
        """Update document status."""
        rows_affected = self._db.update(
            self.TABLE,
            {"status": str(status)},
            "id = ?",
            (doc_id,),
        )
        return rows_affected > 0

    def delete(self, doc_id: int) -> bool:
        """Delete a document."""
        rows_affected = self._db.delete(self.TABLE, "id = ?", (doc_id,))
        if rows_affected > 0:
            logger.info(f"Deleted document (id={doc_id})")
        return rows_affected > 0


class EmailDraftRepository(BaseRepository):
    """Repository for EmailDraft operations."""

    TABLE = "email_drafts"

    def create(self, draft: EmailDraft) -> int:
        """Create a new email draft and return its ID."""
        data = draft.to_dict()
        draft_id = self._db.insert(self.TABLE, data)
        logger.info(f"Created email draft: {draft.subject} (id={draft_id})")
        return draft_id

    def get_by_id(self, draft_id: int) -> EmailDraft | None:
        """Get email draft by ID."""
        row = self._db.fetch_one(
            f"SELECT * FROM {self.TABLE} WHERE id = ?",
            (draft_id,),
        )
        return EmailDraft.from_row(row) if row else None

    def get_by_shipment(self, shipment_id: int) -> list[EmailDraft]:
        """Get all email drafts for a shipment."""
        rows = self._db.fetch_all(
            f"SELECT * FROM {self.TABLE} WHERE shipment_id = ? ORDER BY created_at DESC",
            (shipment_id,),
        )
        return [EmailDraft.from_row(row) for row in rows]

    def update(self, draft: EmailDraft) -> bool:
        """Update an existing email draft."""
        if draft.id is None:
            raise DatabaseError("Cannot update draft without ID", operation="update", table=self.TABLE)

        data = draft.to_dict()
        rows_affected = self._db.update(self.TABLE, data, "id = ?", (draft.id,))
        return rows_affected > 0

    def mark_sent(self, draft_id: int) -> bool:
        """Mark email draft as sent."""
        rows_affected = self._db.update(
            self.TABLE,
            {"status": "sent", "sent_at": "CURRENT_TIMESTAMP"},
            "id = ?",
            (draft_id,),
        )
        return rows_affected > 0


class AuditLogRepository(BaseRepository):
    """Repository for AuditLog operations."""

    TABLE = "audit_log"

    def create(self, log: AuditLog) -> int:
        """Create a new audit log entry."""
        data = log.to_dict()
        log_id = self._db.insert(self.TABLE, data)
        return log_id

    def log_action(
        self,
        entity_type: str,
        entity_id: int | None,
        action: str,
        user_name: str = "system",
        old_values: dict | None = None,
        new_values: dict | None = None,
        changes: list[dict] | None = None,
    ) -> int:
        """Convenience method to log an action."""
        log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_name=user_name,
            old_values=old_values,
            new_values=new_values,
            changes=changes,
        )
        return self.create(log)

    def get_by_entity(
        self,
        entity_type: str,
        entity_id: int,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Get audit logs for an entity."""
        rows = self._db.fetch_all(
            f"""
            SELECT * FROM {self.TABLE}
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (entity_type, entity_id, limit),
        )
        return [AuditLog.from_row(row) for row in rows]

    def get_recent(self, limit: int = 100) -> list[AuditLog]:
        """Get recent audit log entries."""
        rows = self._db.fetch_all(
            f"SELECT * FROM {self.TABLE} ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [AuditLog.from_row(row) for row in rows]


class CalibrationRepository(BaseRepository):
    """Repository for AWB overlay calibration data."""

    TABLE = "awb_overlay_calibration"

    def save(self, calibration: AWBOverlayCalibration) -> int:
        """Save or update calibration data."""
        # Try to get existing
        existing = self.get(calibration.template_name, calibration.field_name)

        if existing:
            calibration.id = existing.id
            self._db.update(
                self.TABLE,
                calibration.to_dict(),
                "id = ?",
                (existing.id,),
            )
            return existing.id
        else:
            return self._db.insert(self.TABLE, calibration.to_dict())

    def get(self, template_name: str, field_name: str) -> AWBOverlayCalibration | None:
        """Get calibration for a specific field."""
        row = self._db.fetch_one(
            f"SELECT * FROM {self.TABLE} WHERE template_name = ? AND field_name = ?",
            (template_name, field_name),
        )
        return AWBOverlayCalibration.from_row(row) if row else None

    def get_all_for_template(self, template_name: str) -> list[AWBOverlayCalibration]:
        """Get all calibration data for a template."""
        rows = self._db.fetch_all(
            f"SELECT * FROM {self.TABLE} WHERE template_name = ? ORDER BY field_name",
            (template_name,),
        )
        return [AWBOverlayCalibration.from_row(row) for row in rows]

    def get_as_dict(self, template_name: str) -> dict[str, tuple[float, float]]:
        """Get calibration as dictionary of field_name -> (x, y)."""
        calibrations = self.get_all_for_template(template_name)
        return {c.field_name: (c.x_coord, c.y_coord) for c in calibrations}

    def delete(self, template_name: str, field_name: str) -> bool:
        """Delete calibration for a specific field."""
        rows_affected = self._db.delete(
            self.TABLE,
            "template_name = ? AND field_name = ?",
            (template_name, field_name),
        )
        return rows_affected > 0

    def delete_all_for_template(self, template_name: str) -> int:
        """Delete all calibration for a template."""
        rows_affected = self._db.delete(
            self.TABLE,
            "template_name = ?",
            (template_name,),
        )
        return rows_affected
