# AirDocs - Shipment Service
# ==================================

import logging
from datetime import date
from typing import Any

from core.constants import ShipmentStatus, ShipmentType
from core.exceptions import ValidationError, DatabaseError
from data.models import Shipment, Party
from data.repositories import (
    ShipmentRepository,
    PartyRepository,
    AuditLogRepository,
)
from .validators import validate_shipment, ValidationResult

logger = logging.getLogger("airdocs.business")


class ShipmentService:
    """
    Business logic for shipment operations.

    Handles:
    - Creating and updating shipments
    - Validation
    - Status transitions
    - Audit logging
    """

    def __init__(self):
        self._shipment_repo = ShipmentRepository()
        self._party_repo = PartyRepository()
        self._audit_repo = AuditLogRepository()

    def create_shipment(
        self,
        awb_number: str,
        shipment_date: date,
        shipper_id: int,
        consignee_id: int,
        weight_kg: float,
        pieces: int,
        shipment_type: ShipmentType = ShipmentType.AIR,
        agent_id: int | None = None,
        template_id: int | None = None,
        volume_m3: float | None = None,
        goods_description: str | None = None,
        notes: str | None = None,
    ) -> Shipment:
        """
        Create a new shipment.

        Args:
            awb_number: AWB number (must be unique)
            shipment_date: Date of shipment
            shipper_id: ID of shipper party
            consignee_id: ID of consignee party
            weight_kg: Weight in kilograms
            pieces: Number of pieces
            shipment_type: Type of shipment (air/local_delivery)
            agent_id: Optional agent party ID
            template_id: Optional template/preset ID
            volume_m3: Optional volume in cubic meters
            goods_description: Optional description of goods
            notes: Optional notes

        Returns:
            Created Shipment with ID

        Raises:
            ValidationError: If validation fails
            DatabaseError: If database operation fails
        """
        # Create shipment object
        shipment = Shipment(
            awb_number=awb_number,
            shipment_type=shipment_type,
            shipment_date=shipment_date,
            shipper_id=shipper_id,
            consignee_id=consignee_id,
            agent_id=agent_id,
            template_id=template_id,
            weight_kg=weight_kg,
            pieces=pieces,
            volume_m3=volume_m3,
            goods_description=goods_description,
            notes=notes,
            status=ShipmentStatus.DRAFT,
        )

        # Validate
        validation = validate_shipment(shipment)
        if not validation.is_valid:
            raise ValidationError(
                "; ".join(validation.errors),
                field=list(validation.field_errors.keys())[0] if validation.field_errors else None,
            )

        # Check for duplicate AWB
        if self._shipment_repo.awb_exists(awb_number):
            raise ValidationError(
                f"AWB номер {awb_number} уже существует",
                field="awb_number",
            )

        # Verify parties exist
        if not self._party_repo.get_by_id(shipper_id):
            raise ValidationError("Отправитель не найден", field="shipper_id")

        if not self._party_repo.get_by_id(consignee_id):
            raise ValidationError("Получатель не найден", field="consignee_id")

        if agent_id and not self._party_repo.get_by_id(agent_id):
            raise ValidationError("Агент не найден", field="agent_id")

        # Save to database
        shipment_id = self._shipment_repo.create(shipment)
        shipment.id = shipment_id

        # Load relations
        shipment = self._shipment_repo.get_by_id(shipment_id, load_relations=True)

        # Audit log
        self._audit_repo.log_action(
            entity_type="shipment",
            entity_id=shipment_id,
            action="created",
            new_values=shipment.to_dict(),
        )

        logger.info(f"Created shipment: {awb_number} (id={shipment_id})")
        return shipment

    def update_shipment(
        self,
        shipment_id: int,
        **updates: Any,
    ) -> Shipment:
        """
        Update an existing shipment.

        Args:
            shipment_id: ID of shipment to update
            **updates: Field values to update

        Returns:
            Updated Shipment

        Raises:
            ValidationError: If validation fails
            DatabaseError: If shipment not found or update fails
        """
        # Get existing shipment
        shipment = self._shipment_repo.get_by_id(shipment_id, load_relations=False)
        if not shipment:
            raise DatabaseError(
                f"Отправление не найдено (id={shipment_id})",
                operation="update",
                table="shipments",
            )

        old_values = shipment.to_dict()

        # Apply updates
        allowed_fields = {
            "awb_number",
            "shipment_type",
            "shipment_date",
            "shipper_id",
            "consignee_id",
            "agent_id",
            "template_id",
            "weight_kg",
            "pieces",
            "volume_m3",
            "goods_description",
            "notes",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(shipment, field, value)

        # Validate
        validation = validate_shipment(shipment)
        if not validation.is_valid:
            raise ValidationError(
                "; ".join(validation.errors),
                field=list(validation.field_errors.keys())[0] if validation.field_errors else None,
            )

        # Check AWB uniqueness if changed
        if "awb_number" in updates:
            if self._shipment_repo.awb_exists(shipment.awb_number, exclude_id=shipment_id):
                raise ValidationError(
                    f"AWB номер {shipment.awb_number} уже существует",
                    field="awb_number",
                )

        # Update
        self._shipment_repo.update(shipment)

        # Reload with relations
        shipment = self._shipment_repo.get_by_id(shipment_id, load_relations=True)

        # Calculate changes for audit
        new_values = shipment.to_dict()
        changes = []
        for key in old_values:
            if old_values[key] != new_values.get(key):
                changes.append({
                    "field": key,
                    "old": old_values[key],
                    "new": new_values.get(key),
                })

        # Audit log
        if changes:
            self._audit_repo.log_action(
                entity_type="shipment",
                entity_id=shipment_id,
                action="updated",
                old_values=old_values,
                new_values=new_values,
                changes=changes,
            )

        logger.info(f"Updated shipment: {shipment.awb_number} (id={shipment_id})")
        return shipment

    def update_status(
        self,
        shipment_id: int,
        status: ShipmentStatus,
    ) -> Shipment:
        """
        Update shipment status.

        Args:
            shipment_id: ID of shipment
            status: New status

        Returns:
            Updated Shipment
        """
        shipment = self._shipment_repo.get_by_id(shipment_id, load_relations=False)
        if not shipment:
            raise DatabaseError(
                f"Отправление не найдено (id={shipment_id})",
                operation="update_status",
                table="shipments",
            )

        old_status = shipment.status

        # Validate status transition
        valid_transitions = {
            ShipmentStatus.DRAFT: [ShipmentStatus.READY, ShipmentStatus.ARCHIVED],
            ShipmentStatus.READY: [ShipmentStatus.SENT, ShipmentStatus.DRAFT, ShipmentStatus.ARCHIVED],
            ShipmentStatus.SENT: [ShipmentStatus.ARCHIVED],
            ShipmentStatus.ARCHIVED: [ShipmentStatus.DRAFT],
        }

        if status not in valid_transitions.get(old_status, []):
            raise ValidationError(
                f"Недопустимый переход статуса: {old_status.label} -> {status.label}",
                field="status",
            )

        self._shipment_repo.update_status(shipment_id, status)

        # Audit log
        self._audit_repo.log_action(
            entity_type="shipment",
            entity_id=shipment_id,
            action="updated",
            changes=[{"field": "status", "old": str(old_status), "new": str(status)}],
        )

        return self._shipment_repo.get_by_id(shipment_id, load_relations=True)

    def get_shipment(self, shipment_id: int) -> Shipment | None:
        """Get shipment by ID with all related data."""
        return self._shipment_repo.get_by_id(shipment_id, load_relations=True)

    def get_shipment_by_awb(self, awb_number: str) -> Shipment | None:
        """Get shipment by AWB number with all related data."""
        return self._shipment_repo.get_by_awb(awb_number, load_relations=True)

    def list_shipments(
        self,
        status: ShipmentStatus | None = None,
        shipment_type: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Shipment], int]:
        """
        List shipments with pagination and filters.

        Returns:
            Tuple of (shipments list, total count)
        """
        offset = (page - 1) * page_size

        shipments = self._shipment_repo.get_all(
            status=status,
            shipment_type=shipment_type,
            from_date=from_date,
            to_date=to_date,
            search=search,
            limit=page_size,
            offset=offset,
            load_relations=True,
        )

        total = self._shipment_repo.count(status=status, shipment_type=shipment_type)

        return shipments, total

    def delete_shipment(self, shipment_id: int) -> bool:
        """
        Delete a shipment and all related documents.

        Args:
            shipment_id: ID of shipment to delete

        Returns:
            True if deleted
        """
        shipment = self._shipment_repo.get_by_id(shipment_id, load_relations=False)
        if not shipment:
            return False

        # Audit log before deletion
        self._audit_repo.log_action(
            entity_type="shipment",
            entity_id=shipment_id,
            action="deleted",
            old_values=shipment.to_dict(),
        )

        result = self._shipment_repo.delete(shipment_id)
        if result:
            logger.info(f"Deleted shipment: {shipment.awb_number} (id={shipment_id})")

        return result

    def get_statistics(self) -> dict[str, Any]:
        """Get shipment statistics for dashboard."""
        return {
            "total": self._shipment_repo.count(),
            "draft": self._shipment_repo.count(status=ShipmentStatus.DRAFT),
            "ready": self._shipment_repo.count(status=ShipmentStatus.READY),
            "sent": self._shipment_repo.count(status=ShipmentStatus.SENT),
            "archived": self._shipment_repo.count(status=ShipmentStatus.ARCHIVED),
        }
